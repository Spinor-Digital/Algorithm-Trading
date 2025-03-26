import os
import sys
import importlib.util

# 打印环境信息
print(f"Python版本: {sys.version}")
print(f"Python路径: {sys.executable}")
print(f"当前工作目录: {os.getcwd()}")

# 检查Python版本
py_version = sys.version_info
required_version = (3, 9)
if py_version.major > required_version[0] or (py_version.major == required_version[0] and py_version.minor > required_version[1]):
    print(f"警告: 当前Python版本为{py_version.major}.{py_version.minor}，而推荐的版本是Python {required_version[0]}.{required_version[1]}")
    print("某些功能可能不兼容，建议使用Python 3.9运行此应用")

# 尝试解决distutils问题
try:
    import distutils
    print("distutils可用")
except ImportError:
    print("distutils不可用，尝试修复...")
    try:
        import setuptools
        setuptools_dir = os.path.dirname(setuptools.__file__)
        distutils_path = os.path.join(setuptools_dir, "_distutils")
        
        if os.path.exists(distutils_path):
            # 创建distutils模块
            spec = importlib.util.spec_from_file_location(
                "distutils", 
                os.path.join(distutils_path, "__init__.py")
            )
            distutils = importlib.util.module_from_spec(spec)
            sys.modules["distutils"] = distutils
            spec.loader.exec_module(distutils)
            print("已修复distutils")
    except Exception as e:
        print(f"修复distutils失败: {e}")

# 导入app.py
try:
    # 添加当前目录到Python路径
    if '.' not in sys.path:
        sys.path.insert(0, '.')
        
    # 导入app
    import app
    print("成功导入app模块")
except Exception as e:
    print(f"导入app时出错: {e}")
    
    # 尝试直接执行app.py
    try:
        print("尝试直接执行app.py...")
        with open('app.py') as f:
            exec(f.read())
    except Exception as e2:
        print(f"执行app.py时出错: {e2}")
        print("\n可能的解决方案:")
        print("1. 确保安装了所有必要的依赖: pip install -r requirements.txt")
        print("2. 检查API密钥配置是否正确")
        print("3. 检查.env文件是否存在并包含必要的配置")
        raise 