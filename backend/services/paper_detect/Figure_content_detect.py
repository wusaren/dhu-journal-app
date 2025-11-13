#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=== 图片内容智能检测模块 ===

使用硅基流动 Qwen3-VL-32B-Instruct 视觉模型检测图表内容规范性

【检测规则】
1. 刻度线指向图内
2. 物理量/单位表示规范（用"/"分隔，物理量斜体，单位正体）
3. 组合单位加括号，如（H/m）
4. 特殊单位：℃不加括号，角度(°)加括号
5. 坐标轴数字小数位数统一
6. 纵横坐标标题使用文字或符号要统一
"""

import os
import sys
import io
import base64
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from docx import Document
from docx.oxml import parse_xml
from PIL import Image

try:
    import requests
except ImportError:
    print("警告: 需要安装 requests 库: pip install requests")
    requests = None


class FigureContentDetector:
    """图片内容检测器 - 使用视觉模型分析图表规范性"""
    
    def __init__(self, api_key: str = None, api_base: str = None, 
                 model: str = None, save_images: bool = None, image_dir: str = None):
        """
        初始化检测器
        
        参数:
            api_key: 硅基流动API密钥（可选，未提供时从配置文件读取）
            api_base: API基础URL（可选，未提供时从配置文件读取）
            model: 模型名称（可选，未提供时从配置文件读取）
            save_images: 是否永久保存提取的图片（可选，未提供时从配置文件读取）
            image_dir: 保存图片的目录（可选，未提供时从配置文件读取）
        """
        # 尝试从配置文件加载
        try:
            from paper_detect.config_loader import get_config
            config = get_config()
            config.load()
            
            self.api_key = api_key or config.api_key
            self.api_base = api_base or config.api_base
            self.model = model or config.model
            self.save_images = save_images if save_images is not None else config.save_images
            self.image_dir = Path(image_dir or config.image_dir)
        except ImportError:
            # 如果无法导入配置加载器，使用默认值
            self.api_key = api_key
            self.api_base = api_base or "https://api.siliconflow.cn/v1"
            self.model = model or "Qwen/Qwen3-VL-32B-Instruct"
            self.save_images = save_images if save_images is not None else False
            self.image_dir = Path(image_dir or "extracted_figures")
        
        # 验证API密钥
        if not self.api_key:
            raise ValueError(
                "未提供API密钥。请通过以下方式之一配置:\n"
                "1. 在 config_api.py 中设置 SILICONFLOW_API_KEY\n"
                "2. 传递 api_key 参数: FigureContentDetector(api_key='sk-xxx')"
            )
        
        # 如果需要永久保存图片，创建目录
        if self.save_images and not self.image_dir.exists():
            self.image_dir.mkdir(parents=True, exist_ok=True)
        
        # 检测规则提示词（分为多个独立问题）
        self.detection_prompts = {
            'is_chart': """**严格要求：只输出JSON，不要任何解释文字**

判断图片是否为带坐标轴的图表？

输出格式（二选一）：
```json
{"is_chart": true, "chart_type": "折线图"}
```
```json
{"is_chart": false, "chart_type": "照片"}
```

禁止输出任何JSON之外的文字！""",

            'tick_direction': """**只输出JSON，不要任何其他文字**

刻度线是否指向图内？（要求：必须指向图内）

格式：
```json
{"ok": true, "description": "指向图内"}
```
或
```json
{"ok": false, "description": "指向图外"}
```""",

            'unit_format': """**只输出JSON**

物理量/单位格式是否正确？
要求：用"/"分隔，物理量斜体，单位正体

```json
{"ok": true, "issues": []}
```
或
```json
{"ok": false, "issues": ["E未斜体", "V应正体"]}
```

只列问题，不解释！""",

            'unit_brackets': """**只输出JSON**

组合单位是否加括号？
要求：组合单位加括号(H/m)，℃不加，角度(°)加

```json
{"ok": true, "issues": []}
```
或
```json
{"ok": false, "issues": ["V/m应为(V/m)"]}
```""",

            'decimal_consistency': """**只输出JSON**

纵横轴小数位数是否一致？
规则：纵轴0.1,0.2(1位) → 横轴必须1.0,2.0(1位)，不能1,2(整数)

```json
{"ok": true, "y_decimals": "1位", "x_decimals": "1位"}
```
或
```json
{"ok": false, "y_decimals": "1位", "x_decimals": "0位", "description": "不一致"}
```""",

            'axis_title_consistency': """**只输出JSON**

纵横坐标标题用文字还是符号？是否统一？
要求：都用文字或都用符号
✓ Temperature/Time  ✓ T/t  ✗ Temperature/t

```json
{"ok": true, "y_type": "符号", "x_type": "符号"}
```
或
```json
{"ok": false, "y_type": "文字", "x_type": "符号", "description": "不统一"}
```"""
        }
    
    def extract_and_save_image(self, paragraph, doc_path: str, figure_number: int = None) -> Optional[str]:
        """
        从段落中提取图片并保存到本地
        
        参数:
            paragraph: 段落对象
            doc_path: 文档路径（用于提取图片）
            figure_number: 图片编号（用于文件命名）
        
        返回:
            保存的图片文件路径或None
        """
        try:
            # 检查段落是否包含图片
            para_xml = paragraph._element
            
            # 查找图片元素
            blips = para_xml.xpath('.//a:blip')
            if not blips:
                blips = para_xml.xpath('.//v:imagedata')
            
            if not blips:
                return None
            
            # 获取图片关系ID
            blip = blips[0]
            embed_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
            if not embed_id:
                embed_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            
            if not embed_id:
                return None
            
            # 从文档中提取图片
            image_part = paragraph.part.related_parts[embed_id]
            image_bytes = image_part.blob
            
            # 确定图片格式
            content_type = image_part.content_type
            if 'png' in content_type:
                ext = 'png'
            elif 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            elif 'gif' in content_type:
                ext = 'gif'
            elif 'bmp' in content_type:
                ext = 'bmp'
            else:
                ext = 'png'  # 默认使用png
            
            # 保存图片
            if self.save_images:
                # 永久保存
                doc_name = Path(doc_path).stem
                if figure_number:
                    filename = f"{doc_name}_Fig{figure_number}.{ext}"
                else:
                    filename = f"{doc_name}_figure_{id(paragraph)}.{ext}"
                
                image_path = self.image_dir / filename
                with open(image_path, 'wb') as f:
                    f.write(image_bytes)
                
                print(f"  ✓ 图片已保存: {image_path}")
                return str(image_path)
            else:
                # 使用临时文件
                temp_file = tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False)
                temp_file.write(image_bytes)
                temp_file.close()
                
                print(f"  ✓ 图片已提取到临时文件: {temp_file.name}")
                return temp_file.name
            
        except Exception as e:
            print(f"  ✗ 提取图片失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def encode_image_base64(self, image_bytes: bytes) -> str:
        """
        将图片字节编码为base64字符串（兼容旧方法）
        
        参数:
            image_bytes: 图片字节数据
        
        返回:
            base64编码的字符串
        """
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def encode_image_base64_from_file(self, image_path: str) -> str:
        """
        从图片文件读取并编码为base64字符串
        
        参数:
            image_path: 图片文件路径
        
        返回:
            base64编码的字符串
        """
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def call_vision_api(self, image_base64: str, prompt: str) -> Optional[Dict]:
        """
        调用硅基流动视觉API
        
        参数:
            image_base64: base64编码的图片
            prompt: 提示词
        
        返回:
            API响应字典或None
        """
        if not requests:
            print("错误: 未安装 requests 库")
            return None
        
        url = f"{self.api_base}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的图表检查助手。你必须严格按照JSON格式回答，不要输出任何JSON之外的文字、解释或推理过程。只输出纯JSON。"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_tokens": 500,  # 减少token限制，强制简短回答
            "temperature": 0.0,  # 最低温度
            "response_format": {"type": "json_object"}  # 强制JSON输出
        }
        
        # 添加重试机制：最多重试3次
        max_retries = 3
        retry_delay = 5  # 重试间隔5秒
        
        for attempt in range(max_retries):
            try:
                # 增加超时时间到180秒（3分钟），适应复杂图片处理
                if attempt > 0:
                    print(f"    第 {attempt + 1} 次重试...")
                    import time
                    time.sleep(retry_delay)
                
                response = requests.post(url, json=payload, headers=headers, timeout=180)
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"    API调用超时（180秒），正在重试...")
                else:
                    print(f"    API调用超时（已重试{max_retries}次），建议：")
                    print(f"      1. 检查网络连接")
                    print(f"      2. 减小图片尺寸")
                    print(f"      3. 稍后重试")
                    return None
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"    网络错误: {e}，正在重试...")
                else:
                    print(f"    API调用失败（已重试{max_retries}次）: {e}")
                    return None
                    
            except Exception as e:
                print(f"    API调用失败: {e}")
                return None
        
        return None
    
    def parse_api_response(self, response: Dict) -> Dict:
        """
        解析API响应
        
        参数:
            response: API返回的响应
        
        返回:
            解析后的检测结果
        """
        try:
            if not response or 'choices' not in response:
                return {'error': 'API响应格式错误'}
            
            content = response['choices'][0]['message']['content']
            
            # 尝试从响应中提取JSON
            import json
            import re
            
            # 查找JSON代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                result = json.loads(json_str)
                return result
            
            # 如果没有代码块，尝试直接解析
            try:
                result = json.loads(content)
                return result
            except:
                # 返回原始文本
                return {
                    'raw_response': content,
                    'parsed': False
                }
                
        except Exception as e:
            return {'error': f'解析响应失败: {e}'}
    
    def detect_figure_content(self, paragraph, doc_path: str, figure_number: int = None) -> Dict:
        """
        检测图片内容规范性（完整流程：提取→保存→逐项分析）
        
        参数:
            paragraph: 包含图片的段落
            doc_path: 文档路径
            figure_number: 图片编号（可选，用于文件命名）
        
        返回:
            检测结果字典
        """
        result = {
            'ok': True,
            'is_chart': False,
            'messages': [],
            'details': {},
            'image_path': None
        }
        
        # 1. 提取并保存图片到本地
        print(f"    正在提取图片...")
        image_path = self.extract_and_save_image(paragraph, doc_path, figure_number)
        if not image_path:
            result['ok'] = False
            result['messages'].append("无法提取图片数据")
            return result
        
        result['image_path'] = image_path
        
        # 2. 读取图片并编码为base64
        try:
            image_base64 = self.encode_image_base64_from_file(image_path)
        except Exception as e:
            result['ok'] = False
            result['messages'].append(f"读取图片文件失败: {e}")
            # 清理临时文件
            if not self.save_images and os.path.exists(image_path):
                os.unlink(image_path)
            return result
        
        # 3. 第一步：判断是否为图表
        print(f"    [1/6] 判断图片类型...")
        is_chart_response = self.call_vision_api(image_base64, self.detection_prompts['is_chart'])
        
        if not is_chart_response:
            result['ok'] = False
            result['messages'].append("图片类型判断失败")
            if not self.save_images and os.path.exists(image_path):
                os.unlink(image_path)
            return result
        
        is_chart_result = self.parse_api_response(is_chart_response)
        result['details']['is_chart_check'] = is_chart_result
        
        if not is_chart_result.get('is_chart', False):
            # 不是图表，跳过后续检测
            result['is_chart'] = False
            result['messages'].append(f"图片类型: {is_chart_result.get('chart_type', '非图表')}")
            if not self.save_images and os.path.exists(image_path):
                os.unlink(image_path)
            return result
        
        result['is_chart'] = True
        print(f"    图表类型: {is_chart_result.get('chart_type', '图表')}")
        
        # 4. 逐项检测（针对图表）
        check_results = {}
        check_order = [
            ('tick_direction', '刻度线方向'),
            ('unit_format', '物理量单位表示'),
            ('unit_brackets', '组合单位括号'),
            ('decimal_consistency', '数值格式统一性'),
            ('axis_title_consistency', '坐标轴标题一致性')
        ]
        
        for idx, (check_key, check_name) in enumerate(check_order, start=2):
            print(f"    [{idx}/6] 检查{check_name}...")
            
            response = self.call_vision_api(image_base64, self.detection_prompts[check_key])
            if not response:
                check_results[check_key] = {'ok': False, 'error': 'API调用失败'}
                continue
            
            parsed_result = self.parse_api_response(response)
            check_results[check_key] = parsed_result
            
            # 收集问题
            if not parsed_result.get('ok', True):
                result['ok'] = False
                
                # 根据不同的结果格式提取问题描述
                if 'issues' in parsed_result:
                    for issue in parsed_result['issues']:
                        result['messages'].append(f"❌ [{check_name}] {issue}")
                elif 'description' in parsed_result:
                    result['messages'].append(f"❌ [{check_name}] {parsed_result['description']}")
        
        result['details']['check_results'] = check_results
        
        # 清理临时文件（如果不是永久保存）
        if not self.save_images and os.path.exists(image_path):
            os.unlink(image_path)
            result['image_path'] = None
        
        # 如果所有检查都通过
        if result['ok']:
            result['messages'].append("✅ 图表内容符合所有规范")
        
        return result


def detect_figure_content_with_api(doc_path: str, figure_paragraph, api_key: str, 
                                   save_images: bool = False, figure_number: int = None) -> Dict:
    """
    便捷函数：检测单个图片内容（自动完成：提取→保存→分析）
    
    参数:
        doc_path: 文档路径
        figure_paragraph: 包含图片的段落
        api_key: API密钥
        save_images: 是否永久保存图片（默认False，使用临时文件）
        figure_number: 图片编号（可选）
    
    返回:
        检测结果
    """
    detector = FigureContentDetector(api_key, save_images=save_images)
    return detector.detect_figure_content(figure_paragraph, doc_path, figure_number)


# 示例用法
if __name__ == '__main__':
    print(__doc__)
    print("\n使用示例：")
    print("""
from paper_detect.Figure_content_detect import FigureContentDetector

# 初始化检测器
api_key = "your_siliconflow_api_key"
detector = FigureContentDetector(api_key)

# 检测图片
from docx import Document
doc = Document('paper.docx')
paragraph = doc.paragraphs[10]  # 假设第10段包含图片

result = detector.detect_figure_content(paragraph, 'paper.docx')
print(result)
""")

