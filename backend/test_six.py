# test_six.py
import sys
print("Python路径:", sys.path)

try:
    import six
    print("✓ six 模块已成功导入")
    print(f"six 版本: {six.__version__ if hasattr(six, '__version__') else '未知'}")
    print(f"six 位置: {six.__file__}")
except ImportError as e:
    print(f"✗ six 导入失败: {e}")
    
# 检查 site-packages 路径
import site
print("\nSite-packages 路径:")
for path in site.getsitepackages():
    print(f"  - {path}")