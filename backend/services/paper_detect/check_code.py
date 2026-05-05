import json
import re
import requests
import time
import uuid
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

# === 功能一：高德地图地址审核 ===

def get_address_info(query_address, api_key):
    """
    使用高德地图API进行地址审核和信息查询。
    """
    base_url = "https://restapi.amap.com/v3/place/text"
    params = {
        'keywords': query_address,
        'key': api_key,
        'offset': 3,
        'page': 1,
        'extensions': 'all'
    }
    result = {'status': 'error', 'is_exact_match': False, 'message': '', 'candidates': []}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data['status'] != '1' or len(data['pois']) == 0:
            result['status'] = 'no_match'
            result['message'] = '在高德地图中未找到任何匹配的地址。'
            return result
        candidates = [poi['name'] for poi in data['pois']]
        result['candidates'] = candidates
        top_result = data['pois'][0]
        if top_result['name'] == query_address:
            result['is_exact_match'] = True
            result['status'] = 'ok'
            result['message'] = '地址精确匹配成功。'
        else:
            result['status'] = 'no_match'
            result['message'] = f"地址无法精确匹配。最相关的{len(candidates)}个结果是：{', '.join(candidates)}"
        return result
    except Exception as e:
        result['message'] = f"调用高德地图API时出错: {e}"
        return result

# === 功能二：阿里云地址标准化 (使用官方SDK) ===

def get_structured_address_aliyun(address_text, app_key, access_key_id, access_key_secret):
    result = {'status': 'error', 'structured_address': None, 'message': ''}
    try:
        client = AcsClient(access_key_id, access_key_secret, "cn-hangzhou")
        request = CommonRequest()
        request.set_domain("address-purification.cn-hangzhou.aliyuncs.com")
        request.set_version("2019-11-18")
        request.set_product("address-purification")
        request.set_location_service_code("addrp")
        request.set_action_name("StreetStd")
        request.set_method("POST")
        request.add_body_params("AppKey", app_key)
        request.add_body_params("Text", address_text)
        request.add_body_params("ServiceCode", "addrp")

        response = client.do_action_with_exception(request)
        data = json.loads(response.decode("utf-8"))

        # 阿里云返回的Data是一个字符串，需要再次解析
        if 'Data' in data and isinstance(data['Data'], str):
            inner_data = json.loads(data['Data'])
            if inner_data.get('status') == 'OK':
                result['status'] = 'ok'
                result['structured_address'] = inner_data.get('street_std')
                result['message'] = '地址标准化成功。'
            else:
                result['message'] = f"阿里云API返回内部错误: {inner_data.get('message', '状态不为OK')}"
        else:
            result['message'] = data.get('Message', 'API返回的顶层数据格式不正确。')

    except Exception as e:
        result['message'] = f"调用阿里云SDK时出错: {e}"
    
    return result

# === 功能三：DEEPSEEK V3 邮编查询 ===

def _load_zipcode_prompt():
    """从 prompts.json 加载邮编查询提示词"""
    try:
        from pathlib import Path
        prompts_path = Path(__file__).parent / "prompts.json"
        if prompts_path.exists():
            with open(prompts_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('zipcode_query', {}).get('prompt', None)
    except Exception as e:
        print(f"警告: 加载邮编查询提示词失败: {e}")
    return None

def get_zipcode_from_deepseek(structured_address_string, api_key, api_base, model):
    """使用DEEPSEEK V3 API和结构化地址查询邮编。"""
    API_ENDPOINT = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 从 JSON 文件加载提示词
    prompt_template = _load_zipcode_prompt()
    if not prompt_template:
        # 使用默认提示词
        prompt_template = "根据以下中国地址的结构化信息，请仅返回最准确的6位邮政编码，不要包含任何其他文字或解释。地址信息：\n{address}"
    
    prompt = prompt_template.format(address=structured_address_string)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 100,  # 增加到 100，支持思考过程
        "temperature": 0.0
    }
    result = {'status': 'error', 'zipcode': None, 'message': ''}
    try:
        response = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        content = data['choices'][0]['message']['content'].strip()
        # 用正则表达式提取 6 位邮编（支持新格式中的邮编）
        zip_match = re.search(r'(\d{6})', content)
        if zip_match:
            result['status'] = 'ok'
            result['zipcode'] = zip_match.group(1)
            result['message'] = '邮编查询成功。'
        else:
            result['message'] = f'大模型未能返回有效的6位邮编，返回内容: "{content}"'
    except Exception as e:
        result['message'] = f"调用硅基流动API时出错: {e}"
    return result

if __name__ == '__main__':
    # --- 凭证配置: 从新建的 config_api.py 导入 ---
    try:
        # 尝试相对导入（当作为模块导入时）
        try:
            from .config_api import (
                AMAP_API_KEY, ALIYUN_APP_KEY, ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET,
                DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL
            )
        except ImportError:
            # 尝试绝对导入（当直接运行时）
            from config_api import (
                AMAP_API_KEY, ALIYUN_APP_KEY, ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET,
                DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL
            )
        print("已从 paper_detect/config_api.py 加载API凭证。")
    except ImportError as e:
        print(f"错误: 无法从 paper_detect/config_api.py 导入API凭证。请确保文件存在且包含所有必需的变量。")
        print(f"详细错误: {e}")
        exit(1)

    # --- 测试执行 ---
    print("\n--- 1. 测试高德地图地址审核 ---")
    if AMAP_API_KEY:
        test_amap_address = "东华大学材料科学与工程学院"
        amap_info = get_address_info(test_amap_address, AMAP_API_KEY)
        print(f"查询地址: '{test_amap_address}' -> 结果: {amap_info}")
    else:
        print("高德地图API Key未配置，跳过测试。")

    print("\n--- 2. 测试阿里云地址标准化 ---")
    aliyun_configured = all([ALIYUN_APP_KEY, ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET])
    struct_info = None
    if aliyun_configured:
        test_aliyun_address = "东华大学纺织学院"
        print(f"查询地址: {test_aliyun_address}")
        struct_info = get_structured_address_aliyun(test_aliyun_address, ALIYUN_APP_KEY, ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET)
        print(f"阿里云返回: {struct_info}")
    else:
        print("阿里云凭证未配置，跳过测试。")

    print("\n--- 3. 测试DEEPSEEK V3邮编查询 ---")
    if DEEPSEEK_API_KEY and struct_info and struct_info['status'] == 'ok' and struct_info['structured_address']:
        print(f"输入给大模型的结构化地址: {struct_info['structured_address']}")
        zip_info = get_zipcode_from_deepseek(struct_info['structured_address'], DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, DEEPSEEK_MODEL)
        print(f"DeepSeek返回: {zip_info}")
    else:
        print("DeepSeek API Key未配置，或上一步阿里云测试失败，跳过测试。")
