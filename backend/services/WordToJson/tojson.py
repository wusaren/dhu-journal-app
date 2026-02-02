import re
import json
import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FormatProperty:
    """格式属性定义"""
    name: str
    patterns: List[str]  # 正则表达式模式
    data_type: str = "string"
    default_value: Any = None
    mapping: Dict[str, Any] = field(default_factory=dict)
    unit: str = ""
    
    def extract(self, text: str) -> Any:
        """从文本中提取属性值"""
        for pattern in self.patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1) if match.groups() else match.group(0)
                return self._normalize(value)
        return None
    
    def _normalize(self, value: str) -> Any:
        """规范化提取的值"""
        if self.data_type == "int":
            try:
                return int(float(value))
            except:
                return self.default_value
        elif self.data_type == "float":
            try:
                return float(value)
            except:
                return self.default_value
        elif self.data_type == "boolean":
            return bool(value)
        elif self.data_type == "enum":
            return self.mapping.get(value, self.default_value)
        return value


class FormatRuleExtractor:
    """格式规则提取器"""
    
    def __init__(self):
        self.properties = self._init_properties()
        self.template = self._init_template()
    
    def _init_properties(self) -> Dict[str, FormatProperty]:
        """初始化所有属性定义"""
        return {
            # 字体相关
            "font_name": FormatProperty(
                name="font_name",
                patterns=[
                    r"([黑宋楷仿微雅])体",  # 简写匹配
                    r"字体[：:]\s*([^，。\s]+)体",
                    r"([^，。\s]+体)(?:字|字体)",
                    r"中文字体[：:]\s*([^，。\s]+)",
                    r"([黑体|宋体|楷体|仿宋|微软雅黑])"
                ],
                data_type="enum",
                default_value="宋体",
                mapping={
                    "黑": "黑体", "黑体": "黑体",
                    "宋": "宋体", "宋体": "宋体", 
                    "楷": "楷体", "楷体": "楷体",
                    "仿": "仿宋", "仿宋": "仿宋",
                    "微": "微软雅黑", "微软雅黑": "微软雅黑",
                    "雅黑": "微软雅黑"
                }
            ),
            
            "english_font": FormatProperty(
                name="english_font",
                patterns=[
                    r"英文字体[：:]\s*([^，。\s]+)",
                    r"英文[：:]\s*([^，。\s]+)",
                    r"([Tt]imes [Nn]ew [Rr]oman|[Aa]rial|[Cc]alibri|[Cc]ambria)"
                ],
                data_type="enum",
                default_value="Times New Roman",
                mapping={
                    "times": "Times New Roman",
                    "times new roman": "Times New Roman",
                    "arial": "Arial",
                    "calibri": "Calibri",
                    "cambria": "Cambria"
                }
            ),
            
            # 字号相关
            "font_size": FormatProperty(
                name="font_size",
                patterns=[
                    r"(\d+(?:\.\d+)?)[号磅]",
                    r"(\d+(?:\.\d+)?)pt",
                    r"字号[：:]\s*(\d+(?:\.\d+)?)",
                    r"([小一二三四五]{1,2})号",  # 中文号数
                    r"字体大小[：:]\s*(\d+)"
                ],
                data_type="float",
                default_value=12.0
            ),
            
            "font_size_name": FormatProperty(
                name="font_size_name",
                patterns=[
                    r"(小?[一二三四五]号)",
                    r"([小一二三四五]{1,2})号字"
                ],
                data_type="enum",
                mapping={
                    "一号": 26, "小一": 24,
                    "二号": 22, "小二": 18,
                    "三号": 16, "小三": 15,
                    "四号": 14, "小四": 12,
                    "五号": 10.5, "小五": 9
                }
            ),
            
            # 行距相关
            "line_spacing": FormatProperty(
                name="line_spacing",
                patterns=[
                    r"(\d+(?:\.\d+)?)倍行距",
                    r"行距[：:]\s*(\d+(?:\.\d+)?)(?:倍)?",
                    r"(单倍|双倍|1\.5倍)行距",
                    r"行间距[：:]\s*(\d+(?:\.\d+)?)"
                ],
                data_type="float",
                default_value=1.0,
                mapping={
                    "单倍": 1.0,
                    "双倍": 2.0,
                    "1.5倍": 1.5
                }
            ),
            
            # 间距相关
            "space_before": FormatProperty(
                name="space_before",
                patterns=[
                    r"段前\s*(\d+(?:\.\d+)?)\s*(?:厘米|cm|行|磅|pt)?",
                    r"段前间距[：:]\s*(\d+(?:\.\d+)?)",
                    r"前间距[：:]\s*(\d+(?:\.\d+)?)"
                ],
                data_type="float",
                default_value=0.0
            ),
            
            "space_after": FormatProperty(
                name="space_after",
                patterns=[
                    r"段后\s*(\d+(?:\.\d+)?)\s*(?:厘米|cm|行|磅|pt)?",
                    r"段后间距[：:]\s*(\d+(?:\.\d+)?)",
                    r"后间距[：:]\s*(\d+(?:\.\d+)?)"
                ],
                data_type="float",
                default_value=0.0
            ),
            
            # 对齐相关
            "alignment": FormatProperty(
                name="alignment",
                patterns=[
                    r"(居中|左对齐|右对齐|两端对齐)",
                    r"对齐[：:]\s*(居中|左|右|两端)",
                    r"对齐方式[：:]\s*(居中|左对齐|右对齐)"
                ],
                data_type="enum",
                default_value="left",
                mapping={
                    "居中": "center", "中间": "center", "center": "center",
                    "左对齐": "left", "左": "left", "left": "left",
                    "右对齐": "right", "右": "right", "right": "right",
                    "两端对齐": "justify", "justify": "justify"
                }
            ),
            
            # 缩进相关
            "first_line_indent": FormatProperty(
                name="first_line_indent",
                patterns=[
                    r"首行缩进\s*(\d+)\s*字符",
                    r"缩进\s*(\d+)\s*字符",
                    r"首行[：:]\s*(\d+)字符",
                    r"缩进[：:]\s*(\d+)"
                ],
                data_type="int",
                default_value=2
            ),
            
            # 特殊规则
            "abstract_space_between": FormatProperty(
                name="abstract_space_between",
                patterns=[
                    r"摘要二字中间空一格",
                    r"摘\s+要",
                    r"摘要中间有空格"
                ],
                data_type="boolean",
                default_value=False
            ),
            
            "abstract_content_gap": FormatProperty(
                name="abstract_content_gap",
                patterns=[
                    r"摘要与内容之间空一行",
                    r"摘要后空一行",
                    r"摘要和内容间隔"
                ],
                data_type="boolean",
                default_value=False
            ),
            
            # 长度限制
            "min_length": FormatProperty(
                name="min_length",
                patterns=[
                    r"不少于\s*(\d+)\s*字符",
                    r"最少\s*(\d+)\s*字",
                    r"至少\s*(\d+)\s*字符",
                    r"最小长度[：:]\s*(\d+)"
                ],
                data_type="int",
                default_value=300
            ),
            
            "max_length": FormatProperty(
                name="max_length",
                patterns=[
                    r"不超过\s*(\d+)\s*字符",
                    r"最多\s*(\d+)\s*字",
                    r"至多\s*(\d+)\s*字符",
                    r"最大长度[：:]\s*(\d+)"
                ],
                data_type="int",
                default_value=2000
            )
        }
    
    def _init_template(self) -> Dict:
        """初始化JSON模板框架"""
        return {
            "abstract_rule": "",
            "structure_rules": {
                "header_pattern": "",
                "no_paragraph_breaks": False,
                "min_content_length": 300,
                "max_content_length": 2000,
                "content_start_line": 2
            },
            "format_rules": {
                "title": {},
                "abstract": {},
                "content": {}
            },
            "check_rules": {
                "font_size_mapping": {},
                "line_spacing_mapping": {},
                "alignment_mapping": {},
                "indent_mapping": {}
            },
            "messages": {},
            "notes": [],
            "metadata": {
                "source_text": "",
                "parsed_at": "",
                "confidence": 0.0
            }
        }
    
    def extract_all(self, text: str) -> Dict[str, Any]:
        """从文本中提取所有属性"""
        results = {}
        text_lower = text.lower()
        
        for prop_name, prop in self.properties.items():
            value = prop.extract(text)
            if value is not None:
                results[prop_name] = value
                logger.debug(f"提取到属性 {prop_name}: {value}")
        
        # 特殊处理：如果没有明确指定字号，但指定了字号名称
        if 'font_size' not in results and 'font_size_name' in results:
            results['font_size'] = results['font_size_name']
        
        # 计算置信度
        confidence = self._calculate_confidence(results, text)
        results['_confidence'] = confidence
        
        return results
    
    def _calculate_confidence(self, results: Dict, text: str) -> float:
        """计算解析置信度"""
        total_props = len(self.properties)
        extracted_props = len([v for v in results.values() if v is not None])
        
        # 基础置信度：提取到的属性比例
        base_confidence = extracted_props / total_props if total_props > 0 else 0
        
        # 文本质量加分：文本长度适中
        text_length = len(text)
        if 50 <= text_length <= 500:
            length_confidence = 0.2
        elif text_length > 500:
            length_confidence = 0.1
        else:
            length_confidence = 0
        
        # 关键属性加分
        key_props = ['font_name', 'font_size', 'line_spacing']
        key_extracted = sum(1 for prop in key_props if prop in results)
        key_confidence = (key_extracted / len(key_props)) * 0.3
        
        return min(base_confidence + length_confidence + key_confidence, 1.0)
    
    def parse_to_template(self, text: str) -> Dict:
        """将文本解析为完整的JSON模板"""
        # 提取所有属性
        extracted = self.extract_all(text)
        
        # 克隆模板
        template = json.loads(json.dumps(self.template))
        
        # 更新元数据
        template['metadata']['source_text'] = text
        template['metadata']['parsed_at'] = datetime.datetime.now().isoformat()
        template['metadata']['confidence'] = extracted.get('_confidence', 0.0)
        
        # 构建abstract_rule
        abstract_rules = []
        if extracted.get('abstract_space_between'):
            abstract_rules.append('摘要二字中间空一格')
        if extracted.get('abstract_content_gap'):
            abstract_rules.append('摘要与内容中间隔一行')
        if abstract_rules:
            template['abstract_rule'] = '，'.join(abstract_rules)
        
        # 填充格式规则
        self._fill_format_rules(template, extracted)
        
        # 填充结构规则
        self._fill_structure_rules(template, extracted)
        
        # 填充检查规则映射
        self._fill_check_rules(template)
        
        # 生成提示消息
        self._generate_messages(template)
        
        # 生成注意事项
        self._generate_notes(template)
        
        return template
    
    def _fill_format_rules(self, template: Dict, extracted: Dict):
        """填充格式规则部分"""
        # 标题格式
        template['format_rules']['title'] = {
            'font_name': extracted.get('font_name', '黑体'),
            'font_size_pt': extracted.get('font_size', 16.0),
            'bold': True,
            'italic': False,
            'line_spacing': extracted.get('line_spacing', 1.0),
            'space_before': extracted.get('space_before', 0.0),
            'space_after': extracted.get('space_after', 0.0),
            'alignment': extracted.get('alignment', 'center'),
            'first_line_indent': 0,
            'left_indent': 0,
            'right_indent': 0
        }
        
        # 摘要格式
        template['format_rules']['abstract'] = {
            'font_name': extracted.get('font_name', '黑体'),
            'font_size_pt': extracted.get('font_size', 16.0),
            'bold': True,
            'italic': False,
            'line_spacing': extracted.get('line_spacing', 1.0),
            'space_before': 0,
            'space_after': 0,
            'alignment': 'center',
            'first_line_indent': 0,
            'left_indent': 0,
            'right_indent': 0
        }
        
        # 正文格式
        template['format_rules']['content'] = {
            'chinese_font': extracted.get('font_name', '宋体'),
            'english_font': extracted.get('english_font', 'Times New Roman'),
            'font_size_pt': extracted.get('font_size', 12.0),
            'bold': False,
            'italic': False,
            'line_spacing': extracted.get('line_spacing', 1.25),
            'space_before': 0,
            'space_after': 0,
            'alignment': 'left',
            'first_line_indent': extracted.get('first_line_indent', 2),
            'left_indent': 0,
            'right_indent': 0
        }
    
    def _fill_structure_rules(self, template: Dict, extracted: Dict):
        """填充结构规则"""
        # 只在提取到长度限制时才设置，否则不包含该检测项
        if 'min_length' in extracted:
            template['structure_rules']['min_content_length'] = extracted['min_length']
        else:
            # 如果没有提取到最小长度，删除该字段
            template['structure_rules'].pop('min_content_length', None)
        
        if 'max_length' in extracted:
            template['structure_rules']['max_content_length'] = extracted['max_length']
        else:
            # 如果没有提取到最大长度，删除该字段
            template['structure_rules'].pop('max_content_length', None)
        
        # 设置正则表达式模式
        if extracted.get('abstract_space_between'):
            template['structure_rules']['header_pattern'] = "^\\\\s*摘\\\\s要\\\\s*$"
    
    def _fill_check_rules(self, template: Dict):
        """填充检查规则映射"""
        template['check_rules'] = {
            "font_size_mapping": {
                "9": "小五",
                "10.5": "五号", 
                "12": "小四",
                "14": "四号",
                "16": "三号",
                "18": "小二",
                "22": "二号",
                "24": "小一",
                "26": "一号"
            },
            "line_spacing_mapping": {
                "1.0": "单倍行距",
                "1.15": "1.15倍行距",
                "1.5": "1.5倍行距",
                "2.0": "双倍行距"
            },
            "alignment_mapping": {
                "left": "左对齐",
                "center": "居中对齐", 
                "right": "右对齐",
                "justify": "两端对齐"
            },
            "indent_mapping": {
                "0": "无缩进",
                "2": "缩进2字符",
                "4": "缩进4字符",
                "8": "缩进8字符"
            }
        }
    
    def _generate_messages(self, template: Dict):
        """生成提示消息"""
        template['messages'] = {
            "structure_header_ok": "摘要标题格式正确",
            "structure_header_error": "摘要标题格式错误",
            "structure_no_paragraph_ok": "摘要段落符合要求",
            "structure_paragraph_error": "摘要段落格式错误",
            "format_abstract_issue_header": "摘要格式问题：",
            "format_abstract_ok": "摘要格式检查通过",
            "format_content_ok": "正文格式检查通过"
        }
        
        # 只在有长度限制时才生成长度相关的消息
        has_min_length = 'min_content_length' in template['structure_rules']
        has_max_length = 'max_content_length' in template['structure_rules']
        
        if has_min_length or has_max_length:
            template['messages']["structure_length_ok"] = "摘要长度适中"
            
            if has_min_length:
                template['messages']["structure_length_short"] = f"摘要内容过短（少于{template['structure_rules']['min_content_length']}字符）"
            
            if has_max_length:
                template['messages']["structure_length_long"] = f"摘要内容过长（超过{template['structure_rules']['max_content_length']}字符）"
    
    def _generate_notes(self, template: Dict):
        """生成注意事项"""
        notes = [
            "请检查所有格式设置是否符合要求",
            "如果发现解析有误，请手动调整对应字段"
        ]
        
        # 添加特定格式的注意事项
        if template['abstract_rule']:
            notes.append(f"特殊规则：{template['abstract_rule']}")
        
        notes.append(f"解析置信度：{template['metadata']['confidence']:.2f}")
        
        template['notes'] = notes


# 使用示例
def main():
    # 创建提取器
    extractor = FormatRuleExtractor()
    
    # 测试文本
    test_texts = [
        "摘要二字中间空一格：黑体3号字，段前段后0行，单倍行距。摘要与内容之间空一行。摘要内容宋体小四号字，英文字体TimesNewRome，1.25倍行距。",
        # "标题用黑体二号居中，正文宋体小四1.25倍行距，首行缩进2字符",
        # "英文字体用Times New Roman，中文字体用宋体，字号12pt，1.5倍行距"
    ]
    
    for i, text in enumerate(test_texts):
        print(f"\n{'='*60}")
        print(f"测试文本 {i+1}:")
        print(f"{text}")
        print(f"{'='*60}")
        
        # 提取属性
        extracted = extractor.extract_all(text)
        print(f"\n提取到的属性:")
        for key, value in extracted.items():
            if not key.startswith('_'):
                print(f"  {key}: {value}")
        
        # 生成完整模板
        template = extractor.parse_to_template(text)
        
        # 保存到文件
        filename = f"template_{i+1}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 已生成模板并保存到 {filename}")
        print(f"📊 解析置信度: {template['metadata']['confidence']:.2%}")


if __name__ == "__main__":
    main()