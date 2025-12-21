# backend/services/paper_detect/config_api.py
# 占位配置文件。若有真实 API Key 请填写，否则保持空字符串/默认值以禁用对应功能。

# Figure_content_detect / SiliconFlow
SILICONFLOW_API_KEY = ""
SILICONFLOW_API_BASE = "https://api.siliconflow.cn/v1"
SILICONFLOW_MODEL = "Qwen/Qwen3-VL-235B-A22B-Instruct"
SAVE_EXTRACTED_IMAGES = False
EXTRACTED_IMAGES_DIR = "uploads/format_check/extracted_figures"

# Chinese_section_detect / 高德、阿里云、DeepSeek
AMAP_API_KEY = ""
ALIYUN_APP_KEY = ""
ALIYUN_ACCESS_KEY_ID = ""
ALIYUN_ACCESS_KEY_SECRET = ""
DEEPSEEK_API_KEY = ""
DEEPSEEK_API_BASE = ""
DEEPSEEK_MODEL = ""

# Classification_detect
CLASSIFICATION_API_KEY = ""
CLASSIFICATION_BASE_URL = ""