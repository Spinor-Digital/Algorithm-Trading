#!/bin/bash

# 停止任何正在运行的脚本
set -e

echo "ETH日交易算法系统 - 环境设置脚本"
echo "================================="

# 检查是否安装了pyenv
if command -v pyenv 1>/dev/null 2>&1; then
    echo "检测到pyenv已安装"
    
    # 检查是否已安装Python 3.9.16
    if pyenv versions | grep -q 3.9.16; then
        echo "Python 3.9.16已安装"
    else
        echo "正在安装Python 3.9.16..."
        pyenv install 3.9.16
    fi
    
    # 设置本地Python版本
    echo "设置本地Python版本为3.9.16..."
    pyenv local 3.9.16
    
    # 创建虚拟环境
    echo "创建虚拟环境..."
    python -m venv venv
else
    echo "未检测到pyenv，尝试使用系统默认的Python..."
    
    # 检查系统Python版本
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "当前系统Python版本: $PY_VERSION"
    
    if [[ "$PY_VERSION" == "3.9" ]]; then
        echo "使用系统Python 3.9创建虚拟环境..."
        python3 -m venv venv
    else
        echo "警告: 系统Python版本不是3.9"
        echo "建议安装pyenv来管理Python版本:"
        echo "Mac: brew install pyenv"
        echo "Linux: curl https://pyenv.run | bash"
        
        read -p "是否继续使用系统Python创建虚拟环境? (y/n): " CONT
        if [[ "$CONT" == "y" ]]; then
            echo "使用系统Python创建虚拟环境..."
            python3 -m venv venv
        else
            echo "退出设置"
            exit 1
        fi
    fi
fi

# 激活虚拟环境并安装依赖
echo "激活虚拟环境并安装依赖..."
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo "环境设置完成!"
echo "使用以下命令激活环境并运行应用:"
echo "source venv/bin/activate && streamlit run streamlit_app.py" 