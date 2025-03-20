import os
import sys
import site
import importlib

# 检测Python版本
print(f"Python版本：{sys.version}")

# 尝试修复distutils问题
try:
    import distutils
    print("distutils模块已存在")
except ImportError:
    print("尝试修复distutils模块...")
    
    # 检查setuptools是否包含_distutils
    try:
        import setuptools
        setuptools_path = os.path.dirname(setuptools.__file__)
        distutils_path = os.path.join(setuptools_path, "_distutils")
        
        if os.path.exists(distutils_path):
            # 将setuptools的_distutils添加到sys.path
            sys.path.insert(0, setuptools_path)
            sys.modules['distutils'] = importlib.import_module('setuptools._distutils')
            print("已从setuptools导入_distutils作为distutils")
    except Exception as e:
        print(f"修复distutils出错: {e}")

# 导入并运行主应用
print("启动主应用...")
import app 