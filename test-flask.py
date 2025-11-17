# 在两个服务器上分别运行
import flask_security
import werkzeug
import passlib

print("Flask-Security版本:", flask_security.__version__)
print("Werkzeug版本:", werkzeug.__version__)
print("Passlib版本:", passlib.__version__)

# 检查哈希方法
from flask_security.utils import get_hmac   as _get_hmac
print("哈希方法信息:", _get_hmac.__module__ if hasattr(flask_security.utils, '_get_hmac') else "未知")