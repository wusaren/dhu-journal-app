"""
论文术语检测模块（改进版）

功能：
1. 智能提取多词术语（使用N-gram + C-value算法）
2. 检测作者新提出的术语
3. 检测术语使用规范性（是否混用相似词）
4. 使用SciBERT模型进行科学术语NER检测

算法：
- N-gram提取：提取2-5词的短语组合
- C-value算法：经典的多词术语自动抽取算法
- 词性过滤：只保留名词性短语
- PMI（点互信息）：评估词组结合强度
- SciBERT NER：基于深度学习的科学术语识别
"""

import re
import json
import math
import os
from typing import List, Dict, Tuple, Set, Any
from collections import Counter, defaultdict
from docx import Document
import jieba
import jieba.posseg as pseg
import logging

logger = logging.getLogger(__name__)

# 延迟导入深度学习相关库（避免启动时加载过慢）
_transformers_available = False
_spacy_available = False
_model_cache = None

try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    import torch
    _transformers_available = True
except ImportError:
    logger.warning("transformers or torch not available, SciBERT detection will be disabled")

try:
    import spacy
    _spacy_available = True
except ImportError:
    logger.warning("spacy not available, SciBERT detection will be disabled")


class TermDetector:
    """智能术语检测器"""
    
    # 定义性触发词（中英文）
    NEW_TERM_TRIGGERS = [
        "我们提出", "本文提出", "本文定义", "引入了", "定义为", "称为", 
        "新颖的", "一种新的", "首次提出", "创新性地", "本研究提出",
        "we propose", "we introduce", "we define", "is defined as", 
        "we call", "novel", "new approach", "introduce a new",
        "first proposed", "innovative", "we present"
    ]
    
    # 停用词（扩展版）
    STOP_WORDS = {
        # 中文停用词
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", 
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "那", "里", "个", "们", "能", "对", "可以", "但是", "然而", "因此",
        "所以", "如果", "虽然", "或者", "以及", "等", "等等", "通过", "由于", "关于",
        "进行", "提出", "研究", "方法", "结果", "本文", "实验", "数据", "分析",
        # 英文停用词
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "can", "this", "that",
        "these", "those", "it", "its", "which", "who", "what", "where", "when",
        "why", "how", "we", "our", "they", "their", "etc", "such", "also",
        "using", "used", "based", "proposed", "paper", "study", "method",
        "results", "data", "analysis", "experiment"
    }
    
    def __init__(self):
        """初始化术语检测器"""
        # 初始化jieba（添加学术领域常见词）
        jieba.initialize()
        
        # SciBERT模型相关
        self.model = None
        self.tokenizer = None
        self.nlp = None
        self.id2label = None
        self._model_loaded = False
    
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
            
            # 匹配各种引号格式
            patterns = [
                r'"([^"]{2,30})"',  # 双引号
                r"'([^']{2,30})'",  # 英文单引号
                r"‘([^‘’]{2,30})’",  # 中文双引号
                r"“([^“”]{2,30})”",  # 中文双引号
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
    
    def extract_ngrams(self, text: str, min_n: int = 2, max_n: int = 5) -> Dict[str, int]:
        """
        提取N-gram短语
        
        Args:
            text: 文本
            min_n: 最小词数
            max_n: 最大词数
            
        Returns:
            {n-gram: 出现次数} 字典
        """
        logger.info("开始提取N-gram短语...")
        
        # 使用jieba分词和词性标注
        words_with_pos = pseg.cut(text)
        
        # 只保留名词、动词、形容词、英文词
        valid_pos = {'n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn', 'a', 'eng'}
        
        # 构建词序列
        word_list = []
        for word, pos in words_with_pos:
            word = word.strip()
            # 过滤停用词和单字符
            if (len(word) >= 2 and 
                word.lower() not in self.STOP_WORDS and
                not re.match(r'^[\d\s\W]+$', word)):  # 排除纯数字、空格、标点
                word_list.append(word)
        
        logger.info(f"分词后有效词数: {len(word_list)}")
        # print("分词后有效词数：",word_list)
        
        # 提取N-gram
        ngram_counter = Counter()
        
        for n in range(min_n, max_n + 1):
            for i in range(len(word_list) - n + 1):
                ngram = ' '.join(word_list[i:i+n])
                # 再次过滤：不能全是停用词
                words_in_ngram = ngram.split()
                if not all(w.lower() in self.STOP_WORDS for w in words_in_ngram):
                    ngram_counter[ngram] += 1
        
        logger.info(f"提取到 {len(ngram_counter)} 个不同的N-gram短语")
        
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
            if ngram == 'sound absorption' or ngram == 'sound absorption coefficient':
                print(ngram,len(nested_in[ngram]))
                print(ngram,sum(ngrams[parent] for parent in nested_in[ngram]))
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
        - 全中文（2-8个词）
        - 全英文（2-5个词）
        - 中英混合（2-6个词）
        
        过滤规则：
        - 排除全是单字的组合
        - 排除包含太多数字的
        - 排除相同单词重复的短语（如"Hz Hz Hz"）
        
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
            'too_many_digits': 0
        }
        
        for term, score in candidates:
            words = term.split()
            word_count = len(words)
            
            # 基本长度过滤
            if not (2 <= word_count <= 8):
                filtered_out['length'] += 1
                continue
            
            # 检查是否是有意义的组合
            # 排除全是单字的组合
            if all(len(w) == 1 for w in words):
                filtered_out['single_char'] += 1
                continue
            
            # 排除相同单词重复的短语（如"Hz Hz Hz Hz Hz"）
            if word_count >= 2 and len(set(w.lower() for w in words)) == 1:
                print(f"过滤重复单词短语: {term}")
                filtered_out['repeated_word'] += 1
                continue
            
            # 排除包含太多数字的
            digit_ratio = sum(1 for c in term if c.isdigit()) / len(term)
            if digit_ratio > 0.3:
                filtered_out['too_many_digits'] += 1
                continue
            
            filtered.append((term, score))
        
        logger.info(f"模式过滤完成: 保留 {len(filtered)} 个，过滤 {sum(filtered_out.values())} 个")
        logger.info(f"  - 长度不符: {filtered_out['length']}")
        logger.info(f"  - 单字组合: {filtered_out['single_char']}")
        logger.info(f"  - 重复单词: {filtered_out['repeated_word']}")
        logger.info(f"  - 数字过多: {filtered_out['too_many_digits']}")
        
        return filtered
    
    def extract_multi_word_terms(self, doc: Document, top_k: int = 20) -> List[Dict[str, Any]]:
        """
        提取多词术语（核心方法）
        
        Args:
            doc: python-docx Document对象
            top_k: 返回前k个术语
            
        Returns:
            术语列表，包含术语、分数、频率等信息
        """
        logger.info("开始提取多词术语...")
        
        # 1. 获取全文
        text = self.get_all_text(doc)
        
        # 2. 提取N-gram
        ngrams = self.extract_ngrams(text, min_n=2, max_n=5)
        
        # 3. 计算C-value
        cvalue_scores = self.calculate_cvalue(ngrams)
        
        # 4. 基于模式过滤
        filtered_candidates = self.filter_by_patterns(cvalue_scores)
        
        # 5. 取Top K
        top_terms = filtered_candidates[:top_k]
        
        # 6. 构建返回结果
        results = []
        for term, score in top_terms:
            results.append({
                'term': term, # 术语
                'cvalue_score': round(score, 2), # C-value
                'frequency': ngrams[term], # 频率
                'word_count': len(term.split()) # 术语次数
            })
        
        logger.info(f"提取到 {len(results)} 个多词术语")
        
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
    
    def find_similar_terms(self, terms: List[str], threshold: int = 2) -> List[Tuple[str, str, int]]:
        """
        查找相似的术语对（可能是误用或不规范使用）
        
        Args:
            terms: 术语列表
            threshold: 编辑距离阈值
            
        Returns:
            [(术语1, 术语2, 编辑距离), ...] 列表
        """
        similar_pairs = []
        
        for i in range(len(terms)):
            for j in range(i + 1, len(terms)):
                term1 = terms[i]
                term2 = terms[j]
                
                # 长度差异太大，跳过
                if abs(len(term1) - len(term2)) > threshold * 2:
                    continue
                
                distance = self.levenshtein_distance(term1.lower(), term2.lower())
                
                if 0 < distance <= threshold:
                    similar_pairs.append((term1, term2, distance))
        
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
            
            # 加载spacy
            self.nlp = spacy.load("en_core_web_sm")
            
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
    
    def extract_scibert_terms(self, doc: Document) -> List[Dict[str, Any]]:
        """
        使用SciBERT模型从文档中提取科学术语
        
        Args:
            doc: python-docx Document对象
            
        Returns:
            术语列表，包含术语和上下文信息
        """
        if not self._model_loaded:
            if not self.load_scibert_model():
                logger.warning("SciBERT model not available")
                return []
        
        logger.info("开始使用SciBERT模型提取术语...")
        
        # 收集所有句子
        all_text = ' '.join([para.text for para in doc.paragraphs if para.text.strip()])
        
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
        
        # 整理结果
        for term, freq in term_counter.most_common(50):  # 返回前50个
            detected_terms.append({
                'term': term,
                'frequency': freq,
                'source': 'SciBERT-NER',
                'confidence': 'high' if freq >= 10 else 'medium'
            })
        
        logger.info(f"SciBERT检测到 {len(detected_terms)} 个科学术语")
        
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
            
            # 1. 提取关键词（高置信度术语）
            keywords = self.extract_keywords_from_doc(doc)
            logger.info(f"✓ 提取到 {len(keywords)} 个关键词")
            print("关键词：",keywords)
            
            # 2. 提取引号术语（高置信度术语）
            quoted_terms_with_context = self.extract_quoted_terms(doc)
            quoted_terms = list(set([term for term, _ in quoted_terms_with_context]))
            logger.info(f"✓ 提取到 {len(quoted_terms)} 个引号术语")
            print("引号术语：",quoted_terms)

            # 3. 使用N-gram + C-value提取多词术语（核心改进）
            multi_word_terms = self.extract_multi_word_terms(doc, top_k=20)
            logger.info(f"✓ 提取到 {len(multi_word_terms)} 个多词术语")
            print("多词术语：",multi_word_terms)
            
            # 4. 使用SciBERT模型提取科学术语（新增）
            scibert_terms = []
            try:
                scibert_terms = self.extract_scibert_terms(doc)
                logger.info(f"✓ SciBERT检测到 {len(scibert_terms)} 个科学术语")
                print("SciBERT术语：",scibert_terms)
            except Exception as e:
                logger.warning(f"SciBERT检测失败: {e}")
                print("SciBERT检测失败，跳过此步骤")

            # 6. 合并所有候选术语
            all_candidate_terms = set()
            all_candidate_terms.update(keywords)
            all_candidate_terms.update(quoted_terms)
            all_candidate_terms.update([t['term'] for t in multi_word_terms])
            all_candidate_terms.update([t['term'] for t in scibert_terms])
            
            candidate_terms = list(all_candidate_terms)
            logger.info(f"✓ 合并后共 {len(candidate_terms)} 个候选术语")            
            print("候选术语：",candidate_terms)

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
            
            # 8. 检测相似术语（可能的混用）
            similar_pairs = self.find_similar_terms(candidate_terms, threshold=3)
            logger.info(f"✓ 检测到 {len(similar_pairs)} 对相似术语")
            print("相似术语：",similar_pairs)

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
                    'similar_pairs': [
                        {
                            'term1': t1,
                            'term2': t2,
                            'distance': dist,
                            'severity': 'high' if dist <= 2 else 'medium'
                        }
                        for t1, t2, dist in similar_pairs[:20]  # 只返回前20对
                    ]
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
