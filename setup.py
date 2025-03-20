#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
项目初始化脚本，创建必要的目录结构并确保所有组件就绪
"""

import os
import sys
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('setup')

# 定义项目路径
def setup_project():
    """设置项目目录结构"""
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 定义需要创建的目录
    dirs = [
        os.path.join(current_dir, 'data'),
        os.path.join(current_dir, 'models'),
        os.path.join(current_dir, 'strategy'),
        os.path.join(current_dir, 'backtesting'),
        os.path.join(current_dir, 'utils'),
        os.path.join(current_dir, 'database'),
        os.path.join(current_dir, 'database', 'backups'),
        os.path.join(current_dir, 'logs'),
        os.path.join(current_dir, 'results')
    ]
    
    # 创建目录
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        logger.info(f"创建目录: {d}")
    
    # 创建初始__init__.py文件
    init_files = [
        os.path.join(current_dir, 'data', '__init__.py'),
        os.path.join(current_dir, 'models', '__init__.py'),
        os.path.join(current_dir, 'strategy', '__init__.py'),
        os.path.join(current_dir, 'backtesting', '__init__.py'),
        os.path.join(current_dir, 'utils', '__init__.py')
    ]
    
    for f in init_files:
        if not os.path.exists(f):
            with open(f, 'w') as file:
                file.write(f"""#!/usr/bin/env python
# -*- coding: utf-8 -*-
\"\"\"
{os.path.basename(os.path.dirname(f))} 模块初始化
\"\"\"
""")
            logger.info(f"创建文件: {f}")
    
    # 检查核心模块是否存在
    core_files = [
        os.path.join(current_dir, 'config.py'),
        os.path.join(current_dir, 'app.py'),
        os.path.join(current_dir, 'data', 'data_fetcher.py'),
        os.path.join(current_dir, 'models', 'market_analyzer.py'),
        os.path.join(current_dir, 'strategy', 'trading_strategy.py'),
        os.path.join(current_dir, 'backtesting', 'backtester.py'),
        os.path.join(current_dir, 'utils', 'helpers.py')
    ]
    
    missing_files = [f for f in core_files if not os.path.exists(f)]
    if missing_files:
        logger.warning("以下核心文件不存在，请创建:")
        for f in missing_files:
            logger.warning(f"  - {f}")
    
    # 检查requirements.txt
    req_file = os.path.join(current_dir, 'requirements.txt')
    if not os.path.exists(req_file):
        logger.warning(f"缺少requirements.txt文件，请创建")
    
    # 创建示例.env文件
    env_file = os.path.join(current_dir, '.env.example')
    if not os.path.exists(env_file):
        with open(env_file, 'w') as file:
            file.write("""# API设置
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
DERIBIT_API_KEY=your_deribit_api_key
DERIBIT_API_SECRET=your_deribit_api_secret

# 应用设置
DEBUG=True
LOG_LEVEL=INFO
""")
        logger.info(f"创建示例环境变量文件: {env_file}")
    
    # 检查项目是否已就绪
    if not missing_files and os.path.exists(req_file):
        logger.info("项目设置完成，所有必要组件已就绪")
        return True
    else:
        logger.warning("项目设置不完整，请创建缺失的组件")
        return False

def install_dependencies():
    """安装项目依赖"""
    import subprocess
    
    try:
        logger.info("正在安装项目依赖...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        logger.info("依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"安装依赖时出错: {str(e)}")
        return False
    except FileNotFoundError:
        logger.error("找不到requirements.txt文件")
        return False

if __name__ == "__main__":
    logger.info("开始项目初始化...")
    
    # 设置项目目录结构
    setup_result = setup_project()
    
    # 安装依赖
    if setup_result and input("是否要安装项目依赖? (y/n): ").lower() == 'y':
        install_dependencies()
    
    logger.info("项目初始化完成")
    
    # 提供后续步骤说明
    print("\n后续步骤:")
    print("1. 设置API密钥（复制.env.example为.env并填写密钥）")
    print("2. 运行应用: streamlit run app.py")
    print("3. 访问: http://localhost:8501") 