import re
from openai import OpenAI

try:
    from .config_api import CLASSIFICATION_API_KEY, CLASSIFICATION_BASE_URL
    print('启动成功！')
    CLASSIFICATION_API_ENABLED = True
except ImportError:
    CLASSIFICATION_API_ENABLED = False

# 初始化API客户端
client = None
if CLASSIFICATION_API_ENABLED:
    client = OpenAI(
        api_key=CLASSIFICATION_API_KEY,
        base_url=CLASSIFICATION_BASE_URL,
    )

def detect_classification(all_reports):
    """ 
    检测摘要的分类号
    """
    if not CLASSIFICATION_API_ENABLED or not client:
        all_reports['Classification'] = {'error': 'API未配置，跳过分类号检测。'}
        return all_reports

    # 1. 提取摘要和原文CLC号
    abstract_text = all_reports.get('Abstract', {}).get('structure', {}).get('content', '')
    original_clc = all_reports.get('Keywords', {}).get('clc_content', '')

    if not abstract_text:
        all_reports['Classification'] = {'error': '未找到摘要内容，无法进行分类。'}
        return all_reports

    # 2. 调用API进行分类
    instruction = "Classify the subsequent abstract according to the Chinese Library Classification system, detailing the rationale behind your choice and the final code."
    
    try:
        response = client.chat.completions.create(
            model="qwen",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"{instruction}\n{abstract_text}"}
            ],
            temperature=0.1
        )
        content = response.choices[0].message.content
        
        # 3. 解析API返回结果
        # 提取两位大写字母和数字的组合，例如 R7, TQ, TP
        match = re.search(r'\b([A-Z]{1,2}\d{0,2})\b', content)
        code = match.group(1) if match else "未提取到分类号"
        
        api_code_prefix = code[:2]
        original_clc_prefix = original_clc.strip()[:2] if original_clc else ''

        match_status = "未知"
        if api_code_prefix and original_clc_prefix:
            match_status = "一致" if api_code_prefix.upper() == original_clc_prefix.upper() else "不一致"

        all_reports['Classification'] = {
            'code': api_code_prefix, # API提取的分类号前两位
            'reason': content,
            'raw_code': code, # API提取的原始分类号
            'original_clc': original_clc, # 文档中提取的原始CLC号
            'match_status': match_status # 对比状态
        }

    except Exception as e:
        all_reports['Classification'] = {'error': f"API请求失败: {e}"}

    return all_reports
