"""
论文术语检测模块

功能：
1. 智能提取多词术语（使用N-gram + C-value算法）
2. 检测作者新提出的术语
3. 检测术语使用规范性（是否混用相似词）
4. 使用SciBERT模型进行科学术语NER检测

算法：
- SpaCy英文NLP：精准的英文分词和词性标注
- N-gram提取：提取2-5词的短语组合
- C-value算法：经典的多词术语自动抽取算法
- 词性过滤：只保留名词、专有名词、形容词等
- SciBERT NER：基于深度学习的科学术语识别
- 命名实体识别：利用SpaCy的NER辅助术语提取
"""

import re
import json
import math
import os
import numpy as np
from typing import List, Dict, Tuple, Set, Any
from collections import Counter, defaultdict
from docx import Document
import logging

logger = logging.getLogger(__name__)

# 延迟导入 sklearn（避免启动时加载过慢）
_sklearn_available = False
try:
    from sklearn.neighbors import NearestNeighbors
    from sklearn.metrics.pairwise import cosine_similarity
    _sklearn_available = True
except ImportError:
    logger.warning("sklearn not available, semantic similarity will be limited")

# 延迟导入深度学习相关库（避免启动时加载过慢）
_transformers_available = False
_spacy_available = False
_nlp_english = None  # SpaCy英文模型

try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    import torch
    _transformers_available = True
except ImportError:
    logger.warning("transformers or torch not available, SciBERT detection will be disabled")

try:
    import spacy
    _spacy_available = True
    # 加载英文模型
    try:
        _nlp_english = spacy.load("en_core_web_sm")
        logger.info("SpaCy English model loaded successfully")
    except Exception as e:
        logger.warning(f"Failed to load SpaCy English model: {e}")
        _spacy_available = False
except ImportError:
    logger.warning("spacy not available, term extraction will be limited")


class TermDetector:
    """智能术语检测器"""
    
    # 定义性触发词
    NEW_TERM_TRIGGERS = [
        "we propose", "we introduce", "we define", "is defined as", 
        "is termed", "we call", "we term", "referred to as",
        "novel", "new approach", "new method", "introduce a new",
        "first proposed", "first introduced", "innovative", "we present",
        "a novel", "newly developed", "termed as", "called the",
        "introduce the concept", "we coin", "we name", "known as"
    ]
    
    # 英文停用词（学术论文扩展版）
    STOP_WORDS = {
        # 基础停用词
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "can", "this", "that",
        "these", "those", "it", "its", "which", "who", "what", "where", "when",
        "why", "how", "we", "our", "they", "their", "them", "there", "then",
        # 学术论文常见词（非术语）
        "etc", "such", "also", "thus", "therefore", "however", "moreover",
        "furthermore", "additionally", "consequently", "hence", "nevertheless",
        "using", "used", "use", "based", "shown", "shows", "show",
        "proposed", "propose", "proposes", "paper", "study", "research",
        "method", "methods", "results", "result", "data", "analysis",
        "experiment", "experiments", "approach", "approaches", "technique",
        "work", "works", "section", "figure", "table", "described",
        "obtained", "observed", "presented", "demonstrate", "demonstrated",
        "via", "versus", "vs", "e.g.", "i.e.", "cf.", "et", "al"
    }
    
    # 有效词性标签（SpaCy英文）
    VALID_POS = {'NOUN', 'PROPN', 'ADJ', 'VERB'}
    
    # 术语核心词性（必须包含）
    CORE_POS = {'NOUN', 'PROPN'}
    
    # 语义相似度配置参数
    SEMANTIC_SIM_THRESHOLD = 0.70  # 语义相似度阈值
    FINAL_SIM_THRESHOLD = 0.70     # 最终融合相似度阈值
    SEMANTIC_WEIGHT = 0.7          # 语义相似度权重（α）
    MAX_NEIGHBORS = 10             # 每个术语的最大近邻数
    
    def __init__(self):
        """初始化术语检测器"""
        
        # SciBERT模型相关
        self.model = None
        self.tokenizer = None
        self.nlp = _nlp_english  # SciBERT使用的spacy模型
        self.id2label = None
        self._model_loaded = False
        
        # 术语向量缓存
        self._term_embeddings_cache = {}
    
    def extract_keywords_from_doc(self, doc: Document) -> List[str]:
        """
        从文档Keywords部分提取关键词
        
        Args:
            doc: python-docx Document对象
            
        Returns:
            关键词列表
        """
        keywords = []
        
        for para in doc.paragraphs:
            text = para.text.strip()
            
            # 检测Keywords行
            if re.match(r'^Keywords?\s*[:：]', text, re.IGNORECASE):
                match = re.search(r'[:：]\s*(.+)', text, re.IGNORECASE)
                if match:
                    keyword_text = match.group(1)
                    # 按分号或逗号分割
                    terms = re.split(r'[;；,，]', keyword_text)
                    keywords.extend([t.strip() for t in terms if t.strip()])
                    break
        
        return keywords
    
    def extract_quoted_terms(self, doc: Document) -> List[Tuple[str, str]]:
        """
        提取引号括起来的术语（高置信度）
        
        Args:
            doc: python-docx Document对象
            
        Returns:
            [(术语, 上下文), ...] 列表
        """
        quoted_terms = []
        
        for para in doc.paragraphs:
            text = para.text
            
            # 只匹配英文引号格式
            patterns = [
                r'"([^"]{2,50})"',  # 双引号
                r"'([^']{2,50})'",  # 单引号
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    term = match.group(1).strip()
                    # 获取上下文（前后各50字符）
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]
                    quoted_terms.append((term, context))
        
        return quoted_terms
    
    def get_all_text(self, doc: Document) -> str:
        """获取文档所有文本"""
        return ' '.join([para.text for para in doc.paragraphs])
    
    def preprocess_document(self, doc: Document) -> str:
        """
        论文预处理：去除无关内容，只保留正文和摘要
        
        去除以下部分：
        - 参考文献（References, Bibliography）
        - 图题（Figure 1:, Fig. 1:）
        - 表题（Table 1:, Tab. 1:）
        - 目录（Table of Contents, Contents）
        - 致谢（Acknowledgements, Acknowledgments）
        - 附录（Appendix, Appendices）
        
        Args:
            doc: python-docx Document对象
            
        Returns:
            预处理后的纯文本
        """
        logger.info("开始预处理论文，去除无关内容...")
        
        # 定义需要跳过的章节标题模式（开始跳过的标志）
        skip_section_patterns = [
            # 参考文献
            r'^references?\s*$',
            r'^bibliography\s*$',
            r'^cited\s+references?\s*$',
            r'^literature\s+cited\s*$',
            # 目录
            r'^table\s+of\s+contents?\s*$',
            r'^contents?\s*$',
            # 致谢
            r'^acknowledge?ments?\s*$',
            r'^acknowledgement\s*$',
            # 附录
            r'^appendi(x|ces)\s*',
            r'^supplementary\s+(material|information)\s*$',
            # 作者信息
            r'^author\s+(information|contributions?)\s*$',
            r'^conflict\s+of\s+interest\s*$',
            r'^competing\s+interests?\s*$',
            # 资金声明
            r'^funding\s*$',
            r'^financial\s+support\s*$',
        ]
        
        # 定义图题和表题的模式（单独段落跳过）
        figure_table_patterns = [
            # 图题
            r'^fig(?:ure)?\.?\s*\d+',
            r'^figure\s+\d+',
            # 表题
            r'^tab(?:le)?\.?\s*\d+',
            r'^table\s+\d+',
            # 图表说明
            r'^note\s*[:：]',
            r'^source\s*[:：]',
        ]
        
        # 定义恢复正文的标志（结束跳过的标志）
        resume_patterns = [
            r'^abstract\s*$',
            r'^\d+\.?\s*(introduction|background)',
            r'^introduction\s*$',
            r'^\d+\.?\s*methods?\s*$',
            r'^\d+\.?\s*results?\s*$',
            r'^\d+\.?\s*discussion\s*$',
            r'^\d+\.?\s*conclusion\s*$',
        ]
        
        # 编译正则表达式
        skip_patterns_compiled = [re.compile(p, re.IGNORECASE) for p in skip_section_patterns]
        figure_table_compiled = [re.compile(p, re.IGNORECASE) for p in figure_table_patterns]
        resume_compiled = [re.compile(p, re.IGNORECASE) for p in resume_patterns]
        
        # 处理段落
        filtered_paragraphs = []
        skip_mode = False  # 是否处于跳过模式
        skip_reason = ""   # 跳过原因
        
        stats = {
            'total_paragraphs': 0,
            'kept_paragraphs': 0,
            'skipped_references': 0,
            'skipped_figures': 0,
            'skipped_tables': 0,
            'skipped_others': 0
        }
        
        for para in doc.paragraphs:
            text = para.text.strip()
            stats['total_paragraphs'] += 1
            
            # 跳过空段落
            if not text:
                continue
            
            # 检查是否是图题或表题（单独段落跳过）
            is_figure_table = False
            for pattern in figure_table_compiled:
                if pattern.match(text):
                    is_figure_table = True
                    if 'fig' in text.lower():
                        stats['skipped_figures'] += 1
                        logger.info(f"跳过图题: {text}...")
                    else:
                        stats['skipped_tables'] += 1
                        logger.info(f"跳过表题: {text}...")
                    break
            
            if is_figure_table:
                continue
            
            # 检查是否进入跳过章节
            if not skip_mode:
                for pattern in skip_patterns_compiled:
                    if pattern.match(text):
                        skip_mode = True
                        skip_reason = text[:30]
                        logger.info(f"进入跳过模式: {text}...")
                        
                        # 特殊处理：参考文献通常到文档结尾
                        if 'reference' in text.lower() or 'bibliography' in text.lower():
                            stats['skipped_references'] += 1
                        else:
                            stats['skipped_others'] += 1
                        break
            
            # 如果处于跳过模式，检查是否恢复
            if skip_mode:
                # 检查是否遇到恢复标志
                for pattern in resume_compiled:
                    if pattern.match(text):
                        skip_mode = False
                        logger.info(f"恢复正文: {text}...")
                        break
                
                # 如果仍在跳过模式，跳过当前段落
                if skip_mode:
                    continue
            
            # 额外过滤：去除页眉页脚类内容
            # 通常是很短的、纯数字、或特定格式的内容
            if self._is_header_footer(text):
                logger.info(f"跳过页眉页脚: {text}...")
                continue
            
            # 保留段落
            filtered_paragraphs.append(text)
            stats['kept_paragraphs'] += 1
        
        # 统计日志
        logger.info(f"预处理完成:")
        logger.info(f"  - 总段落数: {stats['total_paragraphs']}")
        logger.info(f"  - 保留段落: {stats['kept_paragraphs']}")
        logger.info(f"  - 跳过参考文献: {stats['skipped_references']}")
        logger.info(f"  - 跳过图题: {stats['skipped_figures']}")
        logger.info(f"  - 跳过表题: {stats['skipped_tables']}")
        logger.info(f"  - 跳过其他: {stats['skipped_others']}")
        
        # 合并段落
        processed_text = ' '.join(filtered_paragraphs)
        
        logger.info(f"预处理后文本长度: {len(processed_text)} 字符")
        
        return processed_text
    
    def _is_header_footer(self, text: str) -> bool:
        """
        判断是否是页眉页脚内容
        
        Args:
            text: 段落文本
            
        Returns:
            是否是页眉页脚
        """
        text = text.strip()
        
        # 纯数字（页码）
        if text.isdigit():
            return True
        
        # 非常短且包含页码模式
        if len(text) < 20:
            # "Page 1", "1 of 10", "- 1 -" 等
            if re.match(r'^(page\s*)?\d+(\s*(of|/)\s*\d+)?$', text, re.IGNORECASE):
                return True
            if re.match(r'^[-–—]\s*\d+\s*[-–—]$', text):
                return True
        
        # 版权声明
        if re.match(r'^©|copyright', text, re.IGNORECASE):
            return True
        
        # DOI
        if re.match(r'^doi\s*[:：]', text, re.IGNORECASE):
            return True
        
        # 期刊信息行（通常很短，包含年份和卷号）
        if len(text) < 50 and re.search(r'\d{4}.*vol\.?\s*\d+', text, re.IGNORECASE):
            return True
        
        return False
    
    def normalize_term(self, term: str) -> str:
        """
        术语标准化（词形还原）
        
        将术语中的每个词还原为基本形式，用于术语去重和聚合
        例如：
        - "sound absorbing materials" -> "sound absorb material"
        - "neural networks" -> "neural network"
        
        Args:
            term: 原始术语
            
        Returns:
            标准化后的术语
        """
        if not self.nlp:
            return term.lower()
        
        doc = self.nlp(term)
        lemmatized_words = []
        
        for token in doc:
            # 跳过标点和空格
            if token.is_punct or token.is_space:
                continue
            
            # 使用词形还原
            lemma = token.lemma_.lower()
            lemmatized_words.append(lemma)

        return ' '.join(lemmatized_words)
    
    def aggregate_term_variants(self, ngrams: Dict[str, int]) -> Tuple[Dict[str, int], Dict[str, str]]:
        """
        聚合术语变体
        
        将词形变体（单复数、动名词等）聚合到同一个标准形式下
        例如：
        - "sound absorbing material" (5次) + "sound absorption material" (3次) 
          -> "sound absorbing material" (8次)
        
        Args:
            ngrams: {原始术语: 频率} 字典
            
        Returns:
            (聚合后的ngrams, {标准形式: 最常见的原始形式})
        """
        logger.info("开始聚合术语变体...")
        
        # 1. 构建映射：标准形式 -> [(原始形式, 频率), ...]
        normalized_to_originals = defaultdict(list)
        
        for term, freq in ngrams.items():
            normalized = self.normalize_term(term)
            normalized_to_originals[normalized].append((term, freq))
        
        # 2. 为每个标准形式选择最常见的原始形式
        aggregated_ngrams = {}
        normalized_to_representative = {}
        
        for normalized, variants in normalized_to_originals.items():
            # 按频率排序，选择最常见的原始形式作为代表
            variants.sort(key=lambda x: x[1], reverse=True)
            representative_term = variants[0][0]  # 最常见的原始形式
            
            # 聚合频率
            total_freq = sum(freq for _, freq in variants)
            
            aggregated_ngrams[representative_term] = total_freq
            normalized_to_representative[normalized] = representative_term
            
            # 如果有多个变体，记录日志
            if len(variants) > 1:
                logger.info(f"聚合术语变体: {representative_term} (总频率: {total_freq})")
                for variant_term, variant_freq in variants:
                    if variant_term != representative_term:
                        logger.info(f"  - {variant_term} ({variant_freq}次) -> {representative_term}")
        
        logger.info(f"聚合前: {len(ngrams)} 个术语，聚合后: {len(aggregated_ngrams)} 个术语")
        
        return aggregated_ngrams, normalized_to_representative
    
    def aggregate_candidate_terms(self, terms: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        聚合候选术语列表（使用词形还原去重变体）
        
        将词形变体（单复数、动名词等）聚合到同一个代表术语下，返回去重后的术语列表
        
        例如：
        - ["sound absorbing material", "sound absorbing materials", "neural network", "neural networks"]
          -> (["sound absorbing material", "neural network"], 
              {"sound absorb material": ["sound absorbing material", "sound absorbing materials"],
               "neural network": ["neural network", "neural networks"]})
        
        Args:
            terms: 原始术语列表
            
        Returns:
            (去重后的术语列表, {标准形式: [原始形式列表]})
        """
        if not terms:
            return [], {}
        
        logger.info(f"开始聚合候选术语列表，共 {len(terms)} 个术语...")
        
        # 构建映射：标准形式 -> [原始形式列表]
        normalized_to_originals = defaultdict(list)
        
        for term in terms:
            normalized = self.normalize_term(term)
            normalized_to_originals[normalized].append(term)
        
        # 为每个标准形式选择代表（优先选择较短的、更常见的表达）
        aggregated_terms = []
        variants_map = {}
        
        for normalized, variants in normalized_to_originals.items():
            # 去重
            unique_variants = list(set(variants))
            
            # 按长度排序，选择最短的作为代表（通常是单数形式）
            unique_variants.sort(key=lambda x: (len(x), x))
            representative = unique_variants[0]
            
            aggregated_terms.append(representative)
            
            # 记录有多个变体的情况
            if len(unique_variants) > 1:
                variants_map[normalized] = unique_variants
                logger.info(f"聚合候选术语变体: {unique_variants} -> {representative}")
        
        logger.info(f"候选术语聚合完成: {len(terms)} -> {len(aggregated_terms)} 个")
        
        return aggregated_terms, variants_map
    
    def extract_ngrams(self, text: str, min_n: int = 2, max_n: int = 5) -> Dict[str, int]:
        """
        提取N-gram短语
        
        使用SpaCy进行英文分词和词性标注，提取有意义的多词术语候选
        
        Args:
            text: 文本
            min_n: 最小词数（默认2）
            max_n: 最大词数（默认5）
            
        Returns:
            {n-gram: 出现次数} 字典
        """
        if not self.nlp:
            logger.error("SpaCy English model not available")
            return {}
        
        logger.info("开始使用SpaCy提取英文N-gram短语...")
        
        # 使用SpaCy处理文本
        doc = self.nlp(text)
        
        # 构建有效词序列（带词性标注）
        tokens_with_pos = []
        for token in doc:
            # 跳过标点、空格、数字
            if token.is_punct or token.is_space or token.like_num:
                tokens_with_pos.append(None)  # 作为分隔符
                continue
            
            # 跳过停用词
            if token.lower_ in self.STOP_WORDS:
                tokens_with_pos.append(None)
                continue
            
            # 只保留有效词性
            if token.pos_ in self.VALID_POS:
                # 保留原始形式（不词形还原，保持术语的原始表达）
                tokens_with_pos.append((token.text, token.pos_))
        
        # 提取N-gram（考虑词性模式）
        ngram_counter = Counter()
        
        # 滑动窗口提取
        i = 0
        while i < len(tokens_with_pos):
            # 跳过None（分隔符）
            if tokens_with_pos[i] is None:
                i += 1
                continue
            
            # 从当前位置开始提取N-gram
            for n in range(min_n, max_n + 1):
                # 收集n个有效词
                ngram_tokens = []
                j = i
                while len(ngram_tokens) < n and j < len(tokens_with_pos):
                    if tokens_with_pos[j] is not None:
                        ngram_tokens.append(tokens_with_pos[j])
                    else:
                        # 遇到分隔符，终止当前N-gram
                        break
                    j += 1
                
                # 检查是否收集到足够的词
                if len(ngram_tokens) == n:
                    # 词性验证：至少包含一个核心词性（名词或专有名词）
                    pos_list = [pos for _, pos in ngram_tokens]
                    if any(pos in self.CORE_POS for pos in pos_list):
                        # 构建N-gram字符串
                        ngram = ' '.join([word for word, _ in ngram_tokens])
                        
                        # 额外过滤：
                        # 1. 不以动词或形容词结尾（术语通常以名词结尾）
                        if ngram_tokens[-1][1] in self.CORE_POS:
                            # 2. 长度合理（2-80字符）
                            if 4 <= len(ngram) <= 80:
                                ngram_counter[ngram] += 1

                        ngram_counter[ngram] += 1
            
            i += 1
        
        logger.info(f"SpaCy提取到 {len(ngram_counter)} 个不同的N-gram短语")
        
        return dict(ngram_counter)
    
    def calculate_cvalue(self, ngrams: Dict[str, int]) -> List[Tuple[str, float]]:
        """
        计算C-value值（术语提取专用算法）
        
        C-value考虑：
        1. 短语长度（词数）
        2. 出现频率
        3. 是否是其他短语的子串
        
        Args:
            ngrams: {n-gram: 频率} 字典
            
        Returns:
            [(术语, C-value分数), ...] 列表，按分数降序
        """
        logger.info("开始计算C-value分数...")
        
        # 构建嵌套关系
        nested_in = defaultdict(list)  # 记录每个短语被包含在哪些更长的短语中
        
        sorted_ngrams = sorted(ngrams.keys(), key=lambda x: len(x.split()), reverse=True)
        
        for i, ngram1 in enumerate(sorted_ngrams):
            for ngram2 in sorted_ngrams[i+1:]:
                # 如果ngram2是ngram1的子串
                if ngram2 in ngram1:
                    nested_in[ngram2].append(ngram1)
        
        # 计算C-value
        cvalue_scores = []
        
        for ngram, freq in ngrams.items():
            length = len(ngram.split())  # 词数
            
            if ngram not in nested_in:
                # 不被其他短语包含
                cvalue = math.log2(length + 1) * freq
            else:
                # 被其他短语包含
                t_nested = len(nested_in[ngram])  # 包含它的短语数量
                p_t_nested = sum(ngrams[parent] for parent in nested_in[ngram])  # 包含它的短语总频率
                cvalue = math.log2(length + 1) * (freq - p_t_nested / t_nested)
            
            cvalue_scores.append((ngram, max(0, cvalue)))  # C-value不能为负
        
        # 按C-value降序排序
        cvalue_scores.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"C-value计算完成，前10个术语: {cvalue_scores[:10]}")
        
        return cvalue_scores
    
    def filter_by_patterns(self, candidates: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """
        基于模式过滤术语候选
        
        保留的模式：
        - 英文术语（2-6个词）
        - 包含连字符的复合词
        
        过滤规则：
        - 排除全是单字母的组合
        - 排除包含太多数字的
        - 排除相同单词重复的短语（如"Hz Hz Hz"）
        - 排除纯停用词组合
        - 排除过短的术语（少于4个字符）
        
        Args:
            candidates: [(术语, 分数), ...] 列表
            
        Returns:
            过滤后的候选列表
        """
        filtered = []
        filtered_out = {
            'length': 0,
            'single_char': 0,
            'repeated_word': 0,
            'too_many_digits': 0,
            'too_short': 0,
            'invalid_pattern': 0
        }
        
        for term, score in candidates:
            words = term.split()
            word_count = len(words)
            
            # 基本长度过滤（2-6个词）
            if not (2 <= word_count <= 6):
                filtered_out['length'] += 1
                continue
            
            # # 术语太短（总字符数 < 4）
            # if len(term) < 4:
            #     filtered_out['too_short'] += 1
            #     continue
            
            # 排除全是单字母的组合
            if all(len(w) == 1 for w in words):
                filtered_out['single_char'] += 1
                continue
            
            # 排除相同单词重复的短语（如"Hz Hz Hz"）
            if word_count >= 2 and len(set(w.lower() for w in words)) == 1:
                filtered_out['repeated_word'] += 1
                continue
            
            # 排除包含太多数字的（超过30%）
            digit_ratio = sum(1 for c in term if c.isdigit()) / len(term)
            if digit_ratio > 0.3:
                filtered_out['too_many_digits'] += 1
                continue
            
            # 检查是否包含字母（必须是文本术语）
            if not re.search(r'[a-zA-Z]', term):
                filtered_out['invalid_pattern'] += 1
                continue
            
            # 排除全是停用词的组合
            if all(w.lower() in self.STOP_WORDS for w in words):
                filtered_out['invalid_pattern'] += 1
                continue
            
            filtered.append((term, score))
        
        logger.info(f"模式过滤完成: 保留 {len(filtered)} 个，过滤 {sum(filtered_out.values())} 个")
        logger.info(f"  - 长度不符: {filtered_out['length']}")
        # logger.info(f"  - 过短: {filtered_out['too_short']}")
        logger.info(f"  - 单字母组合: {filtered_out['single_char']}")
        logger.info(f"  - 重复单词: {filtered_out['repeated_word']}")
        logger.info(f"  - 数字过多: {filtered_out['too_many_digits']}")
        logger.info(f"  - 无效模式: {filtered_out['invalid_pattern']}")
        
        return filtered
    
    def extract_multi_word_terms(self, doc: Document, top_k: int = 30, 
                                   preprocessed_text: str = None) -> List[Dict[str, Any]]:
        """
        提取多词术语
        
        使用N-gram + C-value算法提取英文多词术语，并应用词形还原聚合变体
        
        Args:
            doc: python-docx Document对象
            top_k: 返回前k个术语（默认30）
            preprocessed_text: 预处理后的文本（可选，如果提供则使用此文本）
            
        Returns:
            术语列表，包含术语、分数、频率等信息
        """
        logger.info("开始提取多词术语...")
        
        # 1. 获取文本（优先使用预处理后的文本）
        if preprocessed_text:
            text = preprocessed_text
            logger.info(f"使用预处理后的文本，字符数: {len(text)}")
        else:
            text = self.get_all_text(doc)
            logger.info(f"使用原始文档文本，字符数: {len(text)}")
        
        # 2. 提取N-gram（2-5词）
        ngrams = self.extract_ngrams(text, min_n=2, max_n=5)
        
        if not ngrams:
            logger.warning("未提取到任何N-gram短语")
            return []
        
        logger.info(f"提取到 {len(ngrams)} 个原始N-gram")
        
        # 3. 聚合术语变体（词形还原）
        aggregated_ngrams, _ = self.aggregate_term_variants(ngrams)
        
        if not aggregated_ngrams:
            logger.warning("聚合后无有效术语")
            return []
        
        # 4. 计算C-value（使用聚合后的频率）
        cvalue_scores = self.calculate_cvalue(aggregated_ngrams)
        
        # 5. 基于模式过滤
        filtered_candidates = self.filter_by_patterns(cvalue_scores)
        
        if not filtered_candidates:
            logger.warning("过滤后无有效术语候选")
            return []
        
        # 6. 取Top K
        top_terms = filtered_candidates[:top_k]
        
        # 7. 构建返回结果
        results = []
        for term, score in top_terms:
            results.append({
                'term': term, # 术语（最常见的原始形式）
                'cvalue_score': round(score, 2), # C-value
                'frequency': aggregated_ngrams[term], # 聚合后的频率
                'word_count': len(term.split()) # 术语词数
            })
        
        logger.info(f"✓ 最终提取到 {len(results)} 个高质量多词术语（已聚合变体）")
        
        return results
    
    def get_term_contexts(self, doc: Document, term: str, 
                         context_window: int = 50) -> List[str]:
        """
        获取术语在文档中所有出现位置的上下文
        
        Args:
            doc: python-docx Document对象
            term: 要查找的术语
            context_window: 上下文窗口大小（字符数）
            
        Returns:
            上下文列表
        """
        contexts = []
        
        # 将术语中的空格替换为灵活匹配（可能中间有标点）
        pattern_str = re.escape(term).replace(r'\ ', r'[\s\u3000]{0,2}')
        pattern = re.compile(pattern_str, re.IGNORECASE)
        
        for para in doc.paragraphs:
            text = para.text
            
            for match in pattern.finditer(text):
                start = max(0, match.start() - context_window)
                end = min(len(text), match.end() + context_window)
                context = text[start:end]
                contexts.append(context)
        
        return contexts
    
    def is_new_term(self, term: str, contexts: List[str]) -> Tuple[bool, str]:
        """
        判断术语是否为新提出的术语
        
        Args:
            term: 术语
            contexts: 该术语的上下文列表
            
        Returns:
            (是否为新术语, 触发词或证据)
        """
        for context in contexts:
            # 检查是否包含定义性触发词
            for trigger in self.NEW_TERM_TRIGGERS:
                if trigger in context:
                    return True, trigger
        
        return False, ""
    
    def levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        计算编辑距离（Levenshtein距离）
        
        Args:
            s1: 字符串1
            s2: 字符串2
            
        Returns:
            编辑距离
        """
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def compute_lexical_similarity(self, term1: str, term2: str) -> float:
        """
        计算词汇层面的相似度（基于编辑距离）
        
        将编辑距离转换为0-1的相似度分数
        
        Args:
            term1: 术语1
            term2: 术语2
            
        Returns:
            词汇相似度 (0-1)
        """
        distance = self.levenshtein_distance(term1.lower(), term2.lower())
        max_len = max(len(term1), len(term2))
        if max_len == 0:
            return 1.0
        # 相似度 = 1 - (编辑距离 / 最大长度)
        return max(0, 1 - distance / max_len)
    
    def find_similar_terms(self, terms: List[str], threshold: int = 2) -> List[Dict[str, Any]]:
        """
        查找相似的术语对（融合语义相似度和编辑距离）
        
        使用SciBERT模型计算术语的语义相似度，并与编辑距离相似度加权融合，
        以发现"字面不同但语义相近"的术语对
        
        Args:
            terms: 术语列表
            threshold: 编辑距离阈值（用于传统方法的兜底）
            
        Returns:
            [{'term1': str, 'term2': str, 'semantic_score': float, 
              'lexical_score': float, 'final_score': float, 'distance': int,
              'severity': str}, ...] 列表
        """
        if not terms or len(terms) < 2:
            return []
        
        logger.info(f"开始查找相似术语，共 {len(terms)} 个候选术语...")
        
        similar_pairs = []
        seen_pairs = set()  # 用于去重
        
        # 尝试使用语义相似度方法
        use_semantic = _sklearn_available and _transformers_available and self._model_loaded
        
        if use_semantic:
            logger.info("使用语义相似度 + 编辑距离融合方法")
            
            try:
                # 1. 对所有术语进行向量化
                term_embeddings = self.encode_terms(terms)
                
                if term_embeddings.size > 0 and len(term_embeddings) == len(terms):
                    # 2. 使用最近邻搜索找到每个术语的相似候选
                    n_neighbors = min(self.MAX_NEIGHBORS + 1, len(terms))  # +1 因为会包含自己
                    
                    # 归一化向量（用于余弦相似度）
                    norms = np.linalg.norm(term_embeddings, axis=1, keepdims=True)
                    norms[norms == 0] = 1  # 避免除零
                    normalized_embeddings = term_embeddings / norms
                    
                    # 使用余弦相似度进行近邻搜索
                    nn_model = NearestNeighbors(
                        n_neighbors=n_neighbors,
                        metric='cosine',
                        algorithm='brute'  # 对于小规模数据，brute更快
                    )
                    nn_model.fit(normalized_embeddings)
                    
                    # 查找近邻
                    distances, indices = nn_model.kneighbors(normalized_embeddings)
                    
                    # 3. 处理近邻结果
                    for i in range(len(terms)):
                        term1 = terms[i]
                        
                        for j_idx in range(1, len(indices[i])):  # 跳过自己（索引0）
                            j = indices[i][j_idx]
                            term2 = terms[j]
                            
                            # 去重：确保每对只处理一次
                            pair_key = tuple(sorted([term1.lower(), term2.lower()]))
                            if pair_key in seen_pairs:
                                continue
                            seen_pairs.add(pair_key)
                            
                            # 计算语义相似度（cosine距离转相似度）
                            semantic_score = 1 - distances[i][j_idx]
                            
                            # 过滤：语义相似度低于阈值的跳过
                            if semantic_score < self.SEMANTIC_SIM_THRESHOLD:
                                continue
                            
                            # 计算词汇相似度
                            lexical_score = self.compute_lexical_similarity(term1, term2)
                            
                            # 计算编辑距离（用于显示）
                            edit_distance = self.levenshtein_distance(term1.lower(), term2.lower())
                            
                            # 加权融合
                            final_score = (self.SEMANTIC_WEIGHT * semantic_score + 
                                         (1 - self.SEMANTIC_WEIGHT) * lexical_score)
                            
                            # 过滤：最终相似度低于阈值的跳过
                            if final_score < self.FINAL_SIM_THRESHOLD:
                                continue
                            
                            # 确定严重程度
                            if final_score >= 0.9:
                                severity = 'high'
                            elif final_score >= 0.8:
                                severity = 'medium'
                            else:
                                severity = 'low'
                            
                            similar_pairs.append({
                                'term1': term1,
                                'term2': term2,
                                'semantic_score': round(float(semantic_score), 3),
                                'lexical_score': round(float(lexical_score), 3),
                                'final_score': round(float(final_score), 3),
                                'distance': edit_distance,
                                'severity': severity
                            })
                    
                    # 按最终相似度排序
                    similar_pairs.sort(key=lambda x: x['final_score'], reverse=True)
                    
                    logger.info(f"语义相似度方法找到 {len(similar_pairs)} 对相似术语")
                    
                else:
                    logger.warning("术语向量化失败，回退到编辑距离方法")
                    use_semantic = False
                    
            except Exception as e:
                logger.error(f"语义相似度计算失败: {e}", exc_info=True)
                use_semantic = False
        
        # 如果语义方法不可用或失败，使用传统编辑距离方法
        if not use_semantic:
            logger.info("使用传统编辑距离方法")
            
            for i in range(len(terms)):
                for j in range(i + 1, len(terms)):
                    term1 = terms[i]
                    term2 = terms[j]
                    
                    # 长度差异太大，跳过
                    if abs(len(term1) - len(term2)) > threshold * 2:
                        continue
                    
                    distance = self.levenshtein_distance(term1.lower(), term2.lower())
                    
                    if 0 < distance <= threshold:
                        lexical_score = self.compute_lexical_similarity(term1, term2)
                        
                        # 确定严重程度
                        if distance == 1:
                            severity = 'high'
                        elif distance == 2:
                            severity = 'medium'
                        else:
                            severity = 'low'
                        
                        similar_pairs.append({
                            'term1': term1,
                            'term2': term2,
                            'semantic_score': None,  # 语义方法不可用
                            'lexical_score': round(lexical_score, 3),
                            'final_score': round(lexical_score, 3),  # 仅使用词汇相似度
                            'distance': distance,
                            'severity': severity
                        })
            
            # 按编辑距离排序
            similar_pairs.sort(key=lambda x: x['distance'])
            
            logger.info(f"编辑距离方法找到 {len(similar_pairs)} 对相似术语")
        
        return similar_pairs
    
    def load_scibert_model(self) -> bool:
        """
        加载SciBERT模型（延迟加载）
        
        Returns:
            是否加载成功
        """
        if self._model_loaded:
            return True
        
        if not _transformers_available or not _spacy_available:
            logger.warning("Dependencies not available for SciBERT model")
            return False
        
        try:
            logger.info("Loading SciBERT model...")
            
            # 模型路径（相对于当前文件）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, 'scibert-NER-finetuned-improved')
            
            if not os.path.exists(model_path):
                logger.error(f"Model not found at: {model_path}")
                return False
            
            # 加载tokenizer和model
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            self.model = AutoModelForTokenClassification.from_pretrained(model_path, local_files_only=True)
            self.id2label = self.model.config.id2label
            
            self._model_loaded = True
            logger.info("SciBERT model loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load SciBERT model: {e}", exc_info=True)
            return False
    
    def encode_terms(self, terms: List[str]) -> np.ndarray:
        """
        使用SciBERT模型对术语列表进行向量化编码
        
        利用SciBERT的[CLS]token输出作为术语的语义向量表示
        
        Args:
            terms: 术语列表
            
        Returns:
            np.ndarray: 形状为 (len(terms), hidden_size) 的向量矩阵
        """
        if not terms:
            return np.array([])
        
        # 确保模型已加载
        if not self._model_loaded:
            if not self.load_scibert_model():
                logger.warning("SciBERT模型不可用，无法进行术语向量化")
                return np.array([])
        
        logger.info(f"开始对 {len(terms)} 个术语进行向量化编码...")
        
        embeddings = []
        batch_size = 32  # 批量处理
        
        for i in range(0, len(terms), batch_size):
            batch_terms = terms[i:i+batch_size]
            
            try:
                # 使用tokenizer编码
                inputs = self.tokenizer(
                    batch_terms,
                    padding=True,
                    truncation=True,
                    max_length=64,  # 术语通常较短
                    return_tensors="pt"
                )
                
                # 获取模型输出（使用最后一层hidden states）
                with torch.no_grad():
                    outputs = self.model.base_model(**inputs)
                    # 使用[CLS]token的输出作为术语的向量表示
                    # outputs.last_hidden_state: (batch_size, seq_len, hidden_size)
                    cls_embeddings = outputs.last_hidden_state[:, 0, :].numpy()
                    embeddings.append(cls_embeddings)
                    
            except Exception as e:
                logger.error(f"术语向量化失败: {e}")
                # 如果失败，填充零向量
                hidden_size = self.model.config.hidden_size
                zero_embeddings = np.zeros((len(batch_terms), hidden_size))
                embeddings.append(zero_embeddings)
        
        if embeddings:
            all_embeddings = np.vstack(embeddings)
            logger.info(f"术语向量化完成，向量维度: {all_embeddings.shape}")
            return all_embeddings
        
        return np.array([])
    
    def predict_scibert_labels(self, sentence: str) -> List[Tuple[str, str]]:
        """
        使用SciBERT模型预测句子中的科学术语
        
        Args:
            sentence: 输入句子
            
        Returns:
            [(词, 标签), ...] 列表
        """
        if not self._model_loaded:
            if not self.load_scibert_model():
                return []
        
        try:
            # Step 1: SpaCy tokenization
            words = [token.text for token in self.nlp(sentence) if not token.is_space]
            
            if not words:
                return []
            
            # Step 2: Tokenize with SciBERT
            inputs = self.tokenizer(
                words,
                is_split_into_words=True,
                return_tensors="pt",
                truncation=True,
                padding=True
            )
            
            with torch.no_grad():
                outputs = self.model(**inputs).logits
            
            predictions = torch.argmax(outputs, dim=-1).squeeze().tolist()
            
            # 处理单个词的情况
            if isinstance(predictions, int):
                predictions = [predictions]
            
            word_ids = inputs.word_ids()
            
            # Step 3: Align predictions to original words (skip subwords)
            final_tokens = []
            final_labels = []
            
            previous_word_idx = None
            for i, word_idx in enumerate(word_ids):
                if word_idx is None or word_idx == previous_word_idx:
                    continue
                label = self.id2label[predictions[i]]
                final_tokens.append(words[word_idx])
                final_labels.append(label)
                previous_word_idx = word_idx
            
            return list(zip(final_tokens, final_labels))
            
        except Exception as e:
            logger.error(f"Error in SciBERT prediction: {e}", exc_info=True)
            return []
    
    def extract_scibert_terms(self, doc: Document, preprocessed_text: str = None) -> List[Dict[str, Any]]:
        """
        使用SciBERT模型从文档中提取科学术语
        
        Args:
            doc: python-docx Document对象
            preprocessed_text: 预处理后的文本（可选，如果提供则使用此文本）
            
        Returns:
            术语列表，包含术语和上下文信息
        """
        if not self._model_loaded:
            if not self.load_scibert_model():
                logger.warning("SciBERT model not available")
                return []
        
        logger.info("开始使用SciBERT模型提取术语...")
        
        # 使用预处理后的文本或从文档中获取
        if preprocessed_text:
            all_text = preprocessed_text
            logger.info(f"使用预处理后的文本，字符数: {len(all_text)}")
        else:
            all_text = ' '.join([para.text for para in doc.paragraphs if para.text.strip()])
            logger.info(f"使用原始文档文本，字符数: {len(all_text)}")
        
        # 按句子分割
        sentences = [s.strip() for s in all_text.split('.') if s.strip()]
        
        # 存储检测到的术语
        detected_terms = []
        term_counter = Counter()
        
        for sentence in sentences:
            if not sentence:
                continue
            
            predictions = self.predict_scibert_labels(sentence)
            
            # 提取科学术语（B-Scns 和 I-Scns），相邻的术语（没有O标签间隔）合并为一个完整术语
            current_term = []
            for word, label in predictions:
                if label.startswith('B-Scns') or label.startswith('I-Scns'):
                    # 科学术语标签（B-Scns 或 I-Scns）
                    # 直接添加到当前术语中，实现相邻术语的自动拼接
                    current_term.append(word)
                else:
                    # 遇到非术语标签（O）时，才结束当前术语
                    if current_term:
                        term_text = ' '.join(current_term)
                        term_counter[term_text] += 1
                        current_term = []
            
            # 处理句子末尾的术语
            if current_term:
                term_text = ' '.join(current_term)
                term_counter[term_text] += 1
        
        logger.info(f"SciBERT提取到 {len(term_counter)} 个原始术语")
        
        # 为SciBERT检测到的术语计算C-value分数
        if term_counter:
            # 聚合术语变体（词形还原）
            logger.info("开始聚合SciBERT术语变体...")
            aggregated_terms, _ = self.aggregate_term_variants(dict(term_counter))
            
            logger.info(f"聚合后剩余 {len(aggregated_terms)} 个唯一术语")
            
            # 计算C-value分数
            logger.info("开始为SciBERT术语计算C-value分数...")
            cvalue_scores = self.calculate_cvalue(aggregated_terms)
            
            # 整理结果（按C-value排序）
            for term, cvalue in cvalue_scores:  
                # 返回C-value分数大于10的术语
                if cvalue >= 10:
                    freq = aggregated_terms[term]
                    detected_terms.append({
                        'term': term,
                        'frequency': freq,
                        'cvalue_score': round(cvalue, 2),
                    })
        
        logger.info(f"SciBERT最终检测到 {len(detected_terms)} 个科学术语（已聚合变体并计算C-value）")
        
        return detected_terms
    
    def detect_terms(self, docx_path: str) -> Dict[str, Any]:
        """
        执行完整的术语检测（改进版）
        
        Args:
            docx_path: Word文档路径
            
        Returns:
            检测结果字典
        """
        try:
            logger.info(f"开始智能术语检测: {docx_path}")
            
            # 加载文档
            doc = Document(docx_path)
            
            # ========== 0. 预处理文档 ==========
            # 去除参考文献、图题、表题、目录、致谢、附录等无关内容
            preprocessed_text = self.preprocess_document(doc)
            logger.info(f"✓ 文档预处理完成，正文字符数: {len(preprocessed_text)}")
            
            # 1. 提取关键词（从原始文档提取，因为关键词通常在摘要附近）
            keywords = self.extract_keywords_from_doc(doc)
            logger.info(f"✓ 提取到 {len(keywords)} 个关键词")
            print("关键词：",keywords)
            
            # 2. 提取引号术语（从原始文档提取）
            quoted_terms_with_context = self.extract_quoted_terms(doc)
            quoted_terms = list(set([term for term, _ in quoted_terms_with_context]))
            logger.info(f"✓ 提取到 {len(quoted_terms)} 个引号术语")
            print("引号术语：",quoted_terms)

            # 3. 使用N-gram + C-value提取多词术语（使用预处理后的文本）
            multi_word_terms = self.extract_multi_word_terms(doc, top_k=20, preprocessed_text=preprocessed_text)
            logger.info(f"✓ 提取到 {len(multi_word_terms)} 个多词术语")
            print("多词术语：",multi_word_terms)
            
            # 4. 使用SciBERT模型提取科学术语（使用预处理后的文本）
            scibert_terms = []
            try:
                scibert_terms = self.extract_scibert_terms(doc, preprocessed_text=preprocessed_text)
                logger.info(f"✓ SciBERT检测到 {len(scibert_terms)} 个科学术语")
                print("SciBERT术语：",scibert_terms)
            except Exception as e:
                logger.warning(f"SciBERT检测失败: {e}")
                print("SciBERT检测失败，跳过此步骤")

            # 6. 合并所有候选术语（带词形还原聚合）
            all_candidate_terms_raw = []
            all_candidate_terms_raw.extend(keywords)
            all_candidate_terms_raw.extend(quoted_terms)
            all_candidate_terms_raw.extend([t['term'] for t in multi_word_terms])
            all_candidate_terms_raw.extend([t['term'] for t in scibert_terms])
            
            # 先简单去重
            all_candidate_terms_raw = list(set(all_candidate_terms_raw))
            logger.info(f"合并前共 {len(all_candidate_terms_raw)} 个候选术语（简单去重）")
            
            # 使用词形还原进一步聚合（处理 materials/material, networks/network 等变体）
            candidate_terms, term_variants_map = self.aggregate_candidate_terms(all_candidate_terms_raw)
            logger.info(f"✓ 词形还原聚合后共 {len(candidate_terms)} 个候选术语")
            print("候选术语：", candidate_terms)
            
            # 记录被聚合的变体信息（用于调试）
            if term_variants_map:
                print(f"术语变体映射: {len(term_variants_map)} 组")
                for normalized, variants in list(term_variants_map.items())[:5]:
                    print(f"  {normalized}: {variants}")

            # 7. 检测新术语
            new_terms = []
            for term in candidate_terms:
                contexts = self.get_term_contexts(doc, term, context_window=80)
                if contexts:  # 确保有上下文
                    is_new, trigger = self.is_new_term(term, contexts)
                    if is_new:
                        new_terms.append({
                            'term': term,
                            'trigger': trigger,
                            'contexts': contexts[:2],  # 只保留前2个上下文(*可能出现问题)
                            'confirmed': False  # 需要用户确认
                        })
            
            logger.info(f"✓ 检测到 {len(new_terms)} 个疑似新术语")
            print("疑似新术语：",new_terms)
            
            # 8. 检测相似术语（可能的混用）- 使用语义+编辑距离融合方法
            similar_pairs_raw = self.find_similar_terms(candidate_terms, threshold=3)
            logger.info(f"✓ 检测到 {len(similar_pairs_raw)} 对相似术语")
            print("相似术语：", similar_pairs_raw)

            # 9. 组装结果
            result = {
                'success': True,
                'data': {
                    'total_terms': len(candidate_terms),
                    'keywords': keywords,
                    'quoted_terms': quoted_terms,
                    'multi_word_terms': multi_word_terms,  # N-gram + C-value多词术语
                    'scibert_terms': scibert_terms,  # SciBERT检测的科学术语
                    'all_candidate_terms': sorted(list(candidate_terms)),
                    'new_terms': new_terms,
                    'similar_pairs': similar_pairs_raw[:20]  # 只返回前20对，已经是正确格式
                },
                'message': '术语检测完成'
            }
            
            logger.info("✓ 术语检测全部完成")
            
            return result
            
        except Exception as e:
            logger.error(f"✗ 术语检测失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'术语检测失败: {str(e)}'
            }


# 便捷函数
def detect_terms_from_file(docx_path: str) -> Dict[str, Any]:
    """
    从Word文档检测术语（便捷函数）
    
    Args:
        docx_path: Word文档路径
        
    Returns:
        检测结果字典
    """
    detector = TermDetector()
    return detector.detect_terms(docx_path)
