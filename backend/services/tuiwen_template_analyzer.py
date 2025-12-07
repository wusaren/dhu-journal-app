"""
简化版推文模板识别器
只识别占位符和文本标签，不进行复杂的格式识别
"""
import re
import logging
from typing import Dict, List, Tuple, Optional
from docx import Document
from docx.shared import RGBColor

logger = logging.getLogger(__name__)

# 系统字段映射表
FIELD_KEYWORDS = {
    'title': ['标题', 'title', 'Title', 'TITLE'],
    'chinese_title': ['中文标题', 'chinese title', 'Chinese Title'],
    'authors': ['作者', 'author', 'Author', 'authors', 'Authors', 'AUTHORS'],
    'chinese_authors': ['中文作者', 'chinese author', 'Chinese Author'],
    'doi': ['DOI', 'doi', 'Doi'],
    'citation': ['引用', 'citation', 'Citation', 'CITATION', '引用信息'],
    'first_image': ['作者说', 'OSID', '二维码', 'QR', 'qr code'],
    'second_image': ['配图', '图片', '图', 'figure', 'Figure', 'illustration']
}

def analyze_word_template(template_path: str, paper_data: Optional[Dict] = None) -> Dict:
    """
    分析 Word 模板文件，识别字段和格式
    
    Args:
        template_path: Word 模板文件路径
        paper_data: 可选的论文数据字典，用于智能匹配无标签字段
            
        Returns:
            {
            'fields': [
                {
                    'field': 'title',
                    'label': '标题',
                    'type': 'placeholder' | 'text_label' | 'numbered' | 'content_based',
                    'location': 'paragraph_0',
                    'prefix_type': '序号' | '标签' | None,  # 前缀类型
                    'prefix': '1. ' | '标题：' | '',  # 前缀文本（自动填充到前端）
                    'prefix_format': {  # 前缀的格式信息
                        'font_name': 'Arial',
                        'font_size': 12,
                        'font_color': '#000000',
                        'font_bold': False
                    },
                    'format': {  # 字段内容的格式信息
                        'font_name': 'Arial',
                        'font_size': 12,
                        'font_color': '#000000'
                    },
                    'order': 0,
                    'required': False
                }
            ],
            'image_fields': [
                {
                    'location': 'paragraph_5',
                    'detected_type': 'first_image' | 'second_image' | None
                }
            ]
            }
        """
    try:
        doc = Document(template_path)
        fields = []
        image_fields = []
        
        # 使用集合记录已识别的段落，避免重复识别
        identified_paragraphs = set()
        
        # 1. 优先识别占位符字段（如 {title}, {authors}），并检查前面是否有标签
        placeholder_fields = _extract_placeholder_fields(doc, identified_paragraphs)
        fields.extend(placeholder_fields)
        
        # 2. 识别序号字段（如 "1. 中文标题"、"2. 标题"）
        numbered_fields = _extract_numbered_fields(doc, identified_paragraphs)
        fields.extend(numbered_fields)
        
        # 3. 识别文本标签字段（如 "标题：", "作者："），排除已识别的段落
        text_label_fields = _extract_text_label_fields(doc, identified_paragraphs)
        fields.extend(text_label_fields)
        
        # 4. 识别内容特征字段（无前缀但特征明显，如 "中文作者"）
        content_based_fields = _extract_content_based_fields(doc, identified_paragraphs, paper_data=paper_data)
        fields.extend(content_based_fields)
        
        # 5. 识别图片字段（需要与字段关联）
        image_field_configs = _extract_image_fields(doc, identified_paragraphs)
        fields.extend(image_field_configs)
        
        # 6. 按段落顺序排序所有字段，确保与Word文件顺序一致
        fields.sort(key=lambda x: x.get('order', 999))

        # 6.1 去重：同一个逻辑字段只保留第一个（图片字段除外）
        unique_fields: List[Dict] = []
        seen_field_keys = set()
        for field in fields:
            # 图片字段允许有多个（多张图片）
            if field.get('type') == 'image':
                unique_fields.append(field)
                continue

            field_key = field.get('field')
            if not field_key:
                unique_fields.append(field)
                continue

            if field_key in seen_field_keys:
                logger.debug(f"跳过重复字段: {field_key} at {field.get('location')}")
                continue

            seen_field_keys.add(field_key)
            unique_fields.append(field)

        fields = unique_fields
        
        # 7. 提取图片字段信息（用于image_fields返回，保持向后兼容）
        image_fields_list = []
        for field in fields:
            if field.get('type') == 'image':
                detected_type = field.get('detected_type')
                field_key = field.get('field')
                if not detected_type and field_key in ['first_image', 'second_image']:
                    detected_type = field_key
                image_fields_list.append({
                    'location': field.get('location'),
                    'detected_type': detected_type,
                    'field_key': field_key
                })
        image_fields = image_fields_list
        
        logger.info(f"模板分析完成: 占位符 {len(placeholder_fields)} 个, 序号字段 {len(numbered_fields)} 个, 文本标签 {len(text_label_fields)} 个, 内容特征 {len(content_based_fields)} 个, 图片字段 {len(image_fields)} 个")
        
        return {
            'success': True,
            'fields': fields,
            'image_fields': image_fields
        }
        
    except Exception as e:
        logger.error(f"分析Word模板失败: {str(e)}")
        return {
            'success': False,
            'message': f'分析模板失败: {str(e)}',
            'fields': [],
            'image_fields': []
        }

def _extract_placeholder_fields(doc: Document, identified_paragraphs: set = None) -> List[Dict]:
    """
    基于段落提取占位符字段（如 {title}, {authors}），并检查前面是否有标签
    
    每个段落作为一个字段候选，段落内的\n视为字段内容的一部分
    """
    if identified_paragraphs is None:
        identified_paragraphs = set()
    
    fields = []
    placeholder_pattern = re.compile(r'\{(\w+)\}')
    
    for para_idx, para in enumerate(doc.paragraphs):
        # 跳过已识别的段落
        if para_idx in identified_paragraphs:
            continue
            
        text = para.text  # 保留原始文本，不strip，以保留段落内的换行
        
        # 查找占位符
        for match_obj in placeholder_pattern.finditer(text):
            field_key = match_obj.group(1).lower()
            # 检查是否是系统字段
            if field_key in FIELD_KEYWORDS:
                # 提取占位符的格式信息
                format_info = _extract_format_from_paragraph(para)
                
                # 检查占位符前面是否有标签文本
                placeholder_start = match_obj.start()
                prefix_text = None
                prefix_format_info = None
                
                if placeholder_start > 0:
                    # 检查占位符前面的文本（去掉前后空格）
                    before_text = text[:placeholder_start].strip()
                    
                    # 检查是否包含字段关键词作为标签（必须在段落开头或前面只有空格）
                    for field_key_check, keywords in FIELD_KEYWORDS.items():
                        for keyword in keywords:
                            # 匹配模式：关键词 + 冒号/空格，且紧邻占位符
                            # 允许前面有空格，但标签必须在段落开头部分
                            pattern = rf'^\s*{re.escape(keyword)}[：:\s]+$'
                            label_match = re.match(pattern, before_text, re.IGNORECASE)
                            if label_match:
                                prefix_text = label_match.group(0).strip()  # 去掉前后空格
                                # 提取标签格式
                                prefix_start = text.find(prefix_text)
                                if prefix_start >= 0:
                                    prefix_format_info = _extract_prefix_format_from_paragraph(
                                        para, 
                                        prefix_start, 
                                        prefix_start + len(prefix_text)
                                    )
                                break
                        if prefix_text:
                            break
                
                field_data = {
                    'field': field_key,
                    'label': _get_field_label(field_key),
                    'type': 'placeholder',
                    'location': f'paragraph_{para_idx}',
                    'format': format_info,
                    'order': para_idx,
                    'required': False
                }
                
                # 如果有标签，添加到字段数据中（自动填充到前端的前缀栏）
                if prefix_text:
                    # 判断前缀类型（确保只能是"序号"或"标签"）
                    prefix_type = _detect_prefix_type(prefix_text)
                    if not prefix_type:
                        prefix_type = '标签'  # 默认为标签
                    field_data['prefix_type'] = prefix_type  # 前缀类型：序号 或 标签（不能是None）
                    field_data['prefix'] = prefix_text  # 自动填充到前端的前缀栏
                    field_data['prefix_format'] = prefix_format_info  # 自动填充到前端的格式配置
                else:
                    field_data['prefix_type'] = None  # 无前缀时可以为None
                    field_data['prefix'] = ''
                    field_data['prefix_format'] = {}
                
                fields.append(field_data)
                # 标记该段落已识别
                identified_paragraphs.add(para_idx)
                break  # 一个段落只识别一个占位符字段
    
    return fields

def _extract_text_label_fields(doc: Document, identified_paragraphs: set = None) -> List[Dict]:
    """
    基于段落提取文本标签字段（如 "标题：", "作者："）
    
    每个段落作为一个字段候选，段落内的\n视为字段内容的一部分
    排除已通过占位符识别的段落，避免重复识别
    """
    if identified_paragraphs is None:
        identified_paragraphs = set()
    
    fields = []
    
    for para_idx, para in enumerate(doc.paragraphs):
        # 跳过已识别的段落
        if para_idx in identified_paragraphs:
            continue
        
        text = para.text  # 保留原始文本，不strip，以保留段落内的换行
        
        # 检查段落是否包含字段关键词（作为标签）
        # 按字段顺序检查，确保优先匹配更具体的字段
        for field_key, keywords in FIELD_KEY_KEYWORDS.items():
            # 跳过图片字段（图片字段单独处理）
            if field_key in ['first_image', 'second_image']:
                continue
            for keyword in keywords:
                # 匹配模式：关键词 + 冒号 + 可选空格（必须在段落开头或前面只有空格）
                # 这样可以匹配 "作者：内容" 或 "  作者：内容" 或 "DOI: 内容" 或 "作者: 内容"
                # 改进：支持中英文冒号，冒号后可以有0个或多个空格
                pattern = rf'^\s*{re.escape(keyword)}[：:]\s*'
                match = re.match(pattern, text, re.IGNORECASE)
                if match:
                    # 检查标签后面是否有占位符（如果有，说明已经被占位符字段识别了）
                    after_label = text[match.end():].strip()
                    # 如果后面有对应字段的占位符，跳过（避免重复）
                    if re.search(r'\{' + re.escape(field_key) + r'\}', after_label, re.IGNORECASE):
                        continue
                    
                    # 提取标签文本（关键词及其后的冒号/空格）
                    # 保留原始格式，包括冒号后的空格
                    label_text = match.group(0).rstrip()  # 只去掉右侧空格，保留左侧空格和冒号后的格式
                    # 确保标签文本包含冒号（中文或英文）
                    if not label_text or not any(c in label_text for c in ['：', ':']):
                        # 如果匹配到了关键词但没有冒号，说明模式有问题，跳过
                        continue
                    
                    # 调试日志：记录识别到的标签
                    logger.debug(f"识别到标签字段: 段落{para_idx}, 字段={field_key}, 标签文本='{label_text}', 原文='{text[:50]}'")
                    
                    # 提取标签文本的格式信息
                    # 使用匹配位置来提取格式
                    label_start = match.start()
                    label_end = match.end()
                    prefix_format_info = _extract_prefix_format_from_paragraph(
                        para, label_start, label_end
                    )
                    
                    # 提取字段内容的格式信息（标签后的内容，可能包含\n）
                    format_info = _extract_format_after_label(para, match.end())
                    
                    # 判断前缀类型（确保只能是"序号"或"标签"）
                    prefix_type = _detect_prefix_type(label_text)
                    # 如果无法判断，默认为"标签"（因为这是文本标签字段）
                    if not prefix_type:
                        prefix_type = '标签'
                    
                    field_data = {
                        'field': field_key,
                        'label': _get_field_label(field_key),
                        'type': 'text_label',
                        'location': f'paragraph_{para_idx}',
                        'prefix_type': prefix_type,  # 前缀类型：序号 或 标签（不能是None）
                        'prefix': label_text,  # 保存标签文本（自动填充到前端的前缀栏）
                        'prefix_format': prefix_format_info,  # 保存标签格式（自动填充到前端的格式配置）
                        'format': format_info,  # 字段内容的格式
                        'order': para_idx,  # 使用段落索引作为默认顺序
                        'required': False  # 默认非必填
                    }
                    fields.append(field_data)
                    # 标记该段落已识别
                    identified_paragraphs.add(para_idx)
                    break  # 一个段落只识别一个字段
            else:
                continue
            break  # 找到匹配就跳出外层循环
    
    return fields

def _extract_format_after_label(para, label_end_pos: int) -> Dict:
    """提取标签后的内容格式信息"""
    format_info = {
        'font_name': '',
        'font_size': 12,
        'font_color': '#000000'
    }
    
    if not para.runs:
        return format_info
    
    # 计算标签结束位置在哪个run中
    current_pos = 0
    target_run = None
    
    for run in para.runs:
        run_length = len(run.text)
        if current_pos <= label_end_pos < current_pos + run_length:
            # 标签结束位置在这个run中，使用这个run的格式
            target_run = run
            break
        elif label_end_pos < current_pos:
            # 已经过了标签位置，使用第一个run
            break
        current_pos += run_length
    
    # 如果没找到，尝试使用标签后的第一个run，或者使用第一个run
    if target_run is None:
        if para.runs:
            # 找到标签结束位置之后的第一个run
            current_pos = 0
            for run in para.runs:
                run_length = len(run.text)
                if current_pos >= label_end_pos:
                    target_run = run
                    break
                current_pos += run_length
            
            # 如果还是没找到，使用最后一个run或第一个run
            if target_run is None:
                target_run = para.runs[-1] if para.runs else None
    
    if target_run:
        font = target_run.font
        
        if font and font.name:
            format_info['font_name'] = font.name
        
        if font and font.size:
            try:
                if hasattr(font.size, 'pt'):
                    format_info['font_size'] = int(font.size.pt)
                elif isinstance(font.size, (int, float)):
                    format_info['font_size'] = int(font.size)
            except:
                format_info['font_size'] = 12
        
        if font and font.color:
            try:
                if font.color.rgb:
                    rgb = font.color.rgb
                    if isinstance(rgb, RGBColor):
                        format_info['font_color'] = f'#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}'
            except:
                pass
    
    return format_info

def _extract_image_fields(doc: Document, identified_paragraphs: set = None) -> List[Dict]:
    """
    提取图片字段，并创建对应的字段配置
    
    检查段落中是否有图片，如果有则创建对应的字段配置
    """
    if identified_paragraphs is None:
        identified_paragraphs = set()
    
    image_fields = []
    fields = []
    
    try:
        # 检查每个段落是否有图片
        for para_idx, para in enumerate(doc.paragraphs):
            # 跳过已识别的段落
            if para_idx in identified_paragraphs:
                continue
            
            has_image = False
            
            # 方法1: 检查段落XML中是否有图片对象（更严格的检查）
            try:
                para_xml = str(para._element.xml)
                # 检查多种图片标签，但需要确保是真正的图片元素
                # 避免误识别其他包含这些关键词的元素
                xml_lower = para_xml.lower()
                # 必须包含drawing相关的标签，且不是其他用途
                if ('<w:drawing' in xml_lower or '<pic:pic' in xml_lower or 
                    '<a:blip' in xml_lower or 'r:embed' in xml_lower):
                    has_image = True
            except:
                pass
            
            # 方法2: 检查runs中是否有图片（更严格的检查）
            if not has_image:
                try:
                    for run in para.runs:
                        try:
                            run_xml = str(run._element.xml)
                            # 必须包含明确的图片标签
                            if ('<w:drawing' in run_xml.lower() or '<pic:pic' in run_xml.lower() or 
                                '<a:blip' in run_xml.lower()):
                                has_image = True
                                break
                        except:
                            continue
                except:
                    pass
            
            # 方法3: 检查相邻段落（图片可能在单独的段落中）- 更严格的条件
            if not has_image and para_idx > 0:
                try:
                    prev_para = doc.paragraphs[para_idx - 1]
                    prev_para_xml = str(prev_para._element.xml)
                    # 更严格的检查：必须同时满足：前一段有明确的图片标签 AND 当前段有明确的图片相关文本
                    if ('<w:drawing' in prev_para_xml.lower() or '<pic:pic' in prev_para_xml.lower() or 
                        '<a:blip' in prev_para_xml.lower()):
                        context_text = para.text.strip().lower()
                        # 必须有明确的图片相关关键词，且文本不能太长（避免误识别）
                        # 文本长度限制更严格，且必须有明确的图片标识
                        if len(context_text) < 30 and any(keyword in context_text for keyword in ['作者说', 'osid', '二维码', 'qr', '配图', '图片', '图', 'figure']):
                            has_image = True
                except:
                    pass
            
            if has_image:
                # 尝试从上下文判断图片类型
                context_text = para.text.lower()
                # 也检查前一个和后一个段落
                if para_idx > 0:
                    context_text += ' ' + doc.paragraphs[para_idx - 1].text.lower()
                if para_idx < len(doc.paragraphs) - 1:
                    context_text += ' ' + doc.paragraphs[para_idx + 1].text.lower()
                
                detected_type = None
                field_key = None
                
                # 优先通过上下文判断图片类型；如果判断不出，也保留为未知类型，让前端选择
                if any(keyword in context_text for keyword in ['作者说', 'osid', '二维码', 'qr code']):
                    detected_type = 'first_image'
                    field_key = 'first_image'
                elif any(keyword in context_text for keyword in ['配图', '图片', '图', 'figure', 'illustration']):
                    detected_type = 'second_image'
                    field_key = 'second_image'
                else:
                    # 未能从上下文判断类型，保留为未知类型，交给前端选择
                    detected_type = None
                    field_key = 'first_image'  # 默认字段键，前端可通过 selected_type 覆盖
                
                # 调试日志
                logger.debug(f"识别到图片字段: 段落{para_idx}, 类型={detected_type}, 上下文='{context_text[:50]}'")
                
                # 创建图片字段配置（即使类型未知也创建，交给前端选择）
                if field_key:
                    format_info = _extract_format_from_paragraph(para)
                    
                    # 检查是否有前缀（如"论文配图："、"作者说链接/OSID"）
                    prefix_text = ''
                    prefix_type = None
                    prefix_format_info = {}
                    
                    text = para.text.strip()
                    if text:
                        # 检查是否包含标签关键词
                        for keyword in ['配图', '图片', '图', '作者说', 'osid', '二维码']:
                            if keyword in text:
                                # 提取包含关键词的前缀部分
                                pattern = rf'^.*?{re.escape(keyword)}[：:\s]*'
                                match = re.match(pattern, text, re.IGNORECASE)
                                if match:
                                    prefix_text = match.group(0).strip()
                                    prefix_type = _detect_prefix_type(prefix_text) or '标签'
                                    prefix_format_info = _extract_prefix_format_from_paragraph(
                                        para, 0, len(prefix_text)
                                    )
                                    break
                    
                    label = _get_field_label(field_key)
                    if detected_type is None:
                        label = '图片（未识别）'

                    field_data = {
                        'field': field_key,
                        'label': label,
                        'type': 'image',
                        'location': f'paragraph_{para_idx}',
                        'prefix_type': prefix_type,
                        'prefix': prefix_text,
                        'prefix_format': prefix_format_info,
                        'format': format_info,
                        'order': para_idx,
                        'required': False,
                        'detected_type': detected_type
                    }
                    
                    fields.append(field_data)
                    identified_paragraphs.add(para_idx)
                
                image_fields.append({
                    'location': f'paragraph_{para_idx}',
                    'detected_type': detected_type,
                    'field_key': field_key
                })
    except Exception as e:
        logger.warning(f"提取图片字段时出错: {str(e)}")
        # 如果出错，返回已识别的字段，不影响其他功能
    
    return fields  # 返回字段配置列表，而不是image_fields

def _extract_format_from_paragraph(para) -> Dict:
    """从段落中提取格式信息"""
    format_info = {
        'font_name': '',
        'font_size': 12,
        'font_color': '#000000'
    }
    
    if para.runs:
        # 使用第一个 run 的格式
        first_run = para.runs[0]
        font = first_run.font
        
        if font and font.name:
            format_info['font_name'] = font.name
        
        if font and font.size:
            # 将 Pt 转换为数字
            try:
                if hasattr(font.size, 'pt'):
                    format_info['font_size'] = int(font.size.pt)
                elif isinstance(font.size, (int, float)):
                    format_info['font_size'] = int(font.size)
            except:
                format_info['font_size'] = 12
        
        if font and font.color:
            try:
                # 将 RGBColor 转换为十六进制
                if font.color.rgb:
                    rgb = font.color.rgb
                    if isinstance(rgb, RGBColor):
                        format_info['font_color'] = f'#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}'
            except:
                pass
    
    return format_info

def _extract_prefix_format_from_paragraph(para, start_pos: int, end_pos: int) -> Dict:
    """从段落中提取指定位置范围的格式信息（用于提取标签格式）"""
    format_info = {
        'font_name': '',
        'font_size': 12,
        'font_color': '#000000'
    }
    
    if not para.runs:
        return format_info
    
    # 计算标签文本在段落中的位置
    current_pos = 0
    target_run = None
    
    for run in para.runs:
        run_length = len(run.text)
        if current_pos <= start_pos < current_pos + run_length:
            # 标签在这个run中
            target_run = run
            break
        current_pos += run_length
    
    # 如果没找到，使用第一个run
    if target_run is None and para.runs:
        target_run = para.runs[0]
    
    if target_run:
        font = target_run.font
        
        if font and font.name:
            format_info['font_name'] = font.name
        
        if font and font.size:
            try:
                if hasattr(font.size, 'pt'):
                    format_info['font_size'] = int(font.size.pt)
                elif isinstance(font.size, (int, float)):
                    format_info['font_size'] = int(font.size)
            except:
                format_info['font_size'] = 12
        
        if font and font.color:
            try:
                if font.color.rgb:
                    rgb = font.color.rgb
                    if isinstance(rgb, RGBColor):
                        format_info['font_color'] = f'#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}'
            except:
                pass
        
        # 检查是否加粗
        if font and font.bold is not None:
            format_info['font_bold'] = font.bold
    
    return format_info

def _get_field_label(field_key: str) -> str:
    """获取字段的中文标签"""
    labels = {
        'title': '标题',
        'chinese_title': '中文标题',
        'authors': '作者',
        'chinese_authors': '中文作者',
        'doi': 'DOI',
        'citation': '引用信息',
        'first_image': '作者说链接/OSID',
        'second_image': '论文配图'
    }
    return labels.get(field_key, field_key)

# 修正字段关键词映射（之前写错了变量名）
FIELD_KEY_KEYWORDS = FIELD_KEYWORDS

def _detect_prefix_type(prefix_text: str) -> Optional[str]:
    """
    判断前缀类型：序号 或 标签
    
    Args:
        prefix_text: 前缀文本
    
    Returns:
        "序号" 或 "标签" 或 None
    """
    if not prefix_text:
        return None
    
    prefix_text = prefix_text.strip()
    
    # 判断是否为序号：数字开头（如 "1. "、"2. "）或包含"序号"关键词
    if re.match(r'^\d+[\.、]\s*', prefix_text) or '序号' in prefix_text:
        return '序号'
    
    # 判断是否为标签：包含"标签："或字段关键词（如"作者："、"DOI："、"Citation："）
    # 检查是否包含字段关键词（不区分大小写）
    prefix_lower = prefix_text.lower()
    for keywords in FIELD_KEYWORDS.values():
        for keyword in keywords:
            if keyword.lower() in prefix_lower:
                return '标签'
    
    # 如果包含"标签"关键词
    if '标签' in prefix_text:
        return '标签'
    
    return None

def _extract_numbered_fields(doc: Document, identified_paragraphs: set = None) -> List[Dict]:
    """
    识别序号字段（如 "1. 中文标题"、"2. 标题"）
    
    每个段落作为一个字段候选，段落内的\n视为字段内容的一部分
    """
    if identified_paragraphs is None:
        identified_paragraphs = set()
    
    fields = []
    
    for para_idx, para in enumerate(doc.paragraphs):
        # 跳过已识别的段落
        if para_idx in identified_paragraphs:
            continue
        
        text = para.text  # 保留原始文本
        
        # 匹配序号模式：数字 + 点/顿号 + 空格
        # 例如："1. "、"2. "、"1、"等
        number_pattern = re.compile(r'^\s*(\d+)[\.、]\s+')
        match = number_pattern.match(text)
        
        if match:
            # 提取序号文本
            number_text = match.group(0)  # 例如："1. "
            number_value = match.group(1)  # 例如："1"
            
            # 获取序号后的内容
            content_after_number = text[match.end():].strip()
            
            if not content_after_number:
                continue
            
            # 通过内容特征判断字段类型
            field_key = None
            
            # 先尝试通过关键词匹配（更准确）
            for field_key_check, keywords in FIELD_KEYWORDS.items():
                for keyword in keywords:
                    if keyword.lower() in content_after_number.lower():
                        field_key = field_key_check
                        break
                if field_key:
                    break
            
            # 如果无法通过关键词判断，通过内容特征判断
            if not field_key:
                # 计算中文字符和英文字符的比例
                chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', content_after_number))
                english_chars = len(re.findall(r'[a-zA-Z]', content_after_number))
                total_chars = len(re.sub(r'\s+', '', content_after_number))
                
                if total_chars > 0:
                    chinese_ratio = chinese_chars / total_chars
                    english_ratio = english_chars / total_chars
                    
                    # 如果中文字符占比高（>60%），且内容较长，可能是中文标题
                    if chinese_ratio > 0.6 and len(content_after_number) > 10:
                        field_key = 'chinese_title'
                    # 如果英文字符占比高（>60%），且内容较长，可能是英文标题
                    elif english_ratio > 0.6 and len(content_after_number) > 10:
                        field_key = 'title'
                    # 如果中文字符占比高，但内容较短，可能是中文作者
                    elif chinese_ratio > 0.8 and len(content_after_number) < 50:
                        # 检查是否符合中文姓名模式
                        if re.match(r'^[\u4e00-\u9fa5]+(?:[,，]\s*[\u4e00-\u9fa5]+)*', content_after_number):
                            field_key = 'chinese_authors'
                        else:
                            field_key = 'chinese_title'
                    # 如果英文字符占比高，但内容较短，可能是英文作者
                    elif english_ratio > 0.8 and len(content_after_number) < 100:
                        field_key = 'authors'
            
            # 如果识别到字段，创建字段数据
            if field_key:
                # 提取序号格式
                prefix_format_info = _extract_prefix_format_from_paragraph(
                    para, match.start(), match.end()
                )
                
                # 提取字段内容格式
                format_info = _extract_format_after_label(para, match.end())
                
                field_data = {
                    'field': field_key,
                    'label': _get_field_label(field_key),
                    'type': 'numbered',
                    'location': f'paragraph_{para_idx}',
                    'prefix_type': '序号',
                    'prefix': number_text.strip(),  # 例如："1."
                    'prefix_format': prefix_format_info,
                    'format': format_info,
                    'order': para_idx,
                    'required': False
                }
                
                fields.append(field_data)
                identified_paragraphs.add(para_idx)
    
    return fields

def _extract_content_based_fields(doc: Document, identified_paragraphs: set = None, paper_data: Optional[Dict] = None) -> List[Dict]:
    """
    识别无前缀但内容特征明显的字段（如 "中文作者"）
    
    通过内容模式匹配识别字段类型，如果提供了论文数据，则使用智能匹配
    """
    if identified_paragraphs is None:
        identified_paragraphs = set()
    
    fields = []
    
    for para_idx, para in enumerate(doc.paragraphs):
        # 跳过已识别的段落
        if para_idx in identified_paragraphs:
            continue
        
        text = para.text.strip()
        
        if not text:
            continue
        
        field_key = None
        
        # 1. 如果有论文数据，优先使用智能匹配
        if paper_data:
            field_key = _match_field_with_paper_data(text, paper_data)
            if field_key:
                logger.debug(f"通过论文数据智能匹配字段: 段落{para_idx}, 字段={field_key}, 文本='{text[:50]}'")
        
        # 2. 如果没有匹配到，使用内容特征识别
        if not field_key:
            # 识别中文作者模式：中文姓名，逗号分隔
            # 例如："张三, 李四" 或 "张三，李四"
            chinese_name_pattern = re.compile(r'^[\u4e00-\u9fa5]+(?:[,，]\s*[\u4e00-\u9fa5]+)+$')
            if chinese_name_pattern.match(text):
                # 检查是否包含作者相关关键词（可能在其他位置）
                if not any(keyword in text for keyword in ['作者', 'author', 'Author']):
                    # 纯中文姓名列表，很可能是中文作者
                    field_key = 'chinese_authors'
            
            # 识别DOI模式：通常以10.开头，包含斜杠
            if not field_key:
                doi_pattern = re.compile(r'^10\.\d+/[^\s]+$', re.IGNORECASE)
                if doi_pattern.match(text):
                    field_key = 'doi'
            
            # 识别引用格式：通常包含作者名、年份、期刊等信息
            if not field_key:
                # 检查是否包含常见的引用格式特征
                citation_keywords = ['et al', 'vol', 'pp', 'doi', 'journal', '年', '卷', '期']
                if any(keyword.lower() in text.lower() for keyword in citation_keywords):
                    # 进一步检查格式
                    if re.search(r'\d{4}', text):  # 包含年份
                        field_key = 'citation'
        
        # 如果识别到字段，创建字段数据
        if field_key:
            format_info = _extract_format_from_paragraph(para)
            
            field_data = {
                'field': field_key,
                'label': _get_field_label(field_key),
                'type': 'content_based',
                'location': f'paragraph_{para_idx}',
                'prefix_type': None,  # 无前缀
                'prefix': '',  # 无前缀文本
                'prefix_format': {},
                'format': format_info,
                'order': para_idx,
                'required': False
            }
            
            fields.append(field_data)
            identified_paragraphs.add(para_idx)
    
    return fields

def _match_field_with_paper_data(text: str, paper_data: Dict) -> Optional[str]:
    """
    使用论文数据智能匹配字段
    
    Args:
        text: 模板中的文本内容
        paper_data: 论文数据字典
    
    Returns:
        匹配到的字段名，如果没有匹配则返回None
    """
    if not paper_data:
        return None
    
    text_lower = text.lower().strip()
    text_normalized = re.sub(r'\s+', ' ', text_lower)  # 标准化空格

    # 先做精确匹配：如果模板文本与 title/authors 完全一致，则直接返回对应字段
    def normalize_for_exact_match(s: str) -> str:
        if not s:
            return ''
        s = re.sub(r'\s+', ' ', s.strip()).lower()
        # 去掉末尾常见标点，避免 "title." 之类
        s = s.rstrip(' .,:;')
        return s

    t_exact = normalize_for_exact_match(text)
    title_exact = normalize_for_exact_match(paper_data.get('title', ''))
    chinese_title_exact = normalize_for_exact_match(paper_data.get('chinese_title', ''))
    authors_exact = normalize_for_exact_match(paper_data.get('authors', ''))
    chinese_authors_exact = normalize_for_exact_match(paper_data.get('chinese_authors', ''))

    if t_exact and t_exact == title_exact:
        return 'title'
    if t_exact and t_exact == chinese_title_exact:
        return 'chinese_title'
    if t_exact and t_exact == authors_exact:
        return 'authors'
    if t_exact and t_exact == chinese_authors_exact:
        return 'chinese_authors'
    
    # 计算相似度的辅助函数
    def similarity(str1: str, str2: str) -> float:
        """简单的相似度计算（基于包含关系和长度）"""
        if not str1 or not str2:
            return 0.0
        str1_norm = re.sub(r'\s+', ' ', str1.lower().strip())
        str2_norm = re.sub(r'\s+', ' ', str2.lower().strip())
        
        # 完全匹配
        if str1_norm == str2_norm:
            return 1.0
        
        # 包含关系
        if str1_norm in str2_norm or str2_norm in str1_norm:
            return 0.8
        
        # 计算公共字符比例
        set1 = set(str1_norm)
        set2 = set(str2_norm)
        if len(set1) == 0 or len(set2) == 0:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    # 匹配各个字段
    matches: List[Tuple[str, float]] = []
    
    # 匹配标题
    title = paper_data.get('title', '').strip()
    chinese_title = paper_data.get('chinese_title', '').strip()
    if title:
        sim = similarity(text_normalized, title.lower())
        if sim > 0.5:
            matches.append(('title', sim))
    if chinese_title:
        sim = similarity(text_normalized, chinese_title.lower())
        if sim > 0.5:
            matches.append(('chinese_title', sim))
    
    # 匹配作者
    authors = paper_data.get('authors', '').strip()
    chinese_authors = paper_data.get('chinese_authors', '').strip()
    if authors:
        # 检查是否包含作者名（部分匹配）
        author_list = [a.strip() for a in re.split(r'[,，;；]', authors) if a.strip()]
        for author in author_list[:3]:  # 只检查前3个作者
            if author.lower() in text_lower or text_lower in author.lower():
                matches.append(('authors', 0.7))
                break
    if chinese_authors:
        author_list = [a.strip() for a in re.split(r'[,，;；]', chinese_authors) if a.strip()]
        for author in author_list[:3]:
            if author in text or text in author:
                matches.append(('chinese_authors', 0.7))
                break
    
    # 匹配DOI
    doi = paper_data.get('doi', '').strip()
    if doi and doi.lower() in text_lower:
        matches.append(('doi', 0.9))
    
    # 匹配引用信息（严格一点，避免“标题/作者”误判成引用）
    citation = paper_data.get('citation', '').strip()
    if citation:
        sim = similarity(text_normalized, citation.lower())

        # 只有在文本中明显具有“引用结构”时才允许作为 citation
        citation_like = False
        # 必须包含年份
        if re.search(r'\b(19|20)\d{2}\b', text):
            # 并且包含典型引用关键词中的至少一个
            citation_keywords = ['et al', 'vol', 'pp', 'doi', 'journal', '年', '卷', '期']
            if any(k.lower() in text_lower for k in citation_keywords):
                citation_like = True

        # 只有在“引用结构”明显且相似度较高时才认为是 citation
        if citation_like and sim > 0.7:
            matches.append(('citation', sim))
    
    # 如果既匹配到标题/作者，又匹配到 citation，则优先标题/作者
    if matches:
        # 先看有没有非 citation 的匹配（标题/作者/DOI等）
        non_citation = [m for m in matches if m[0] != 'citation']
        if non_citation:
            non_citation.sort(key=lambda x: x[1], reverse=True)
            return non_citation[0][0]
        # 否则才退回到 citation
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0][0]
    
    return None

