import os
import sys
import importlib.util

# 打印环境信息
print(f"Python版本: {sys.version}")
print(f"Python路径: {sys.executable}")
print(f"当前工作目录: {os.getcwd()}")

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
        raise 