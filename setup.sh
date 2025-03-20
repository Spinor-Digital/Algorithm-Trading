#!/bin/bash

# 检查Python版本和distutils是否可用
python_version=$(python --version 2>&1)
echo "使用的Python版本: $python_version"

# 尝试导入distutils
python -c "import distutils" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "distutils模块不可用，安装补丁..."
    
    # 安装setuptools最新版本
    pip install --upgrade setuptools wheel
    
    # 尝试创建distutils链接（适用于某些环境）
    SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
    if [ -d "${SITE_PACKAGES}/setuptools/_distutils" ]; then
        echo "找到setuptools/_distutils，创建链接..."
        mkdir -p "${SITE_PACKAGES}/distutils"
        ln -sf "${SITE_PACKAGES}/setuptools/_distutils" "${SITE_PACKAGES}/distutils"
    fi
else
    echo "distutils模块已可用"
fi

# 检查依赖项
echo "检查依赖项..."
pip install -r requirements.txt

# 启动应用
echo "启动应用..."
streamlit run app.py "$@" 