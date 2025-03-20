#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置文件，包含项目的所有配置参数
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# API配置
API_CONFIG = {
    'binance_api_key': os.getenv('BINANCE_API_KEY', ''),
    'binance_api_secret': os.getenv('BINANCE_API_SECRET', ''),
    'deribit_api_key': os.getenv('DERIBIT_API_KEY', ''),
    'deribit_api_secret': os.getenv('DERIBIT_API_SECRET', ''),
    'use_testnet': os.getenv('USE_TESTNET', 'True').lower() in ('true', '1', 't')
}

# 交易配置
TRADING_CONFIG = {
    'symbol': 'ETH/USDT',            # 交易对
    'timeframe_trend': '1h',         # 趋势判断时间框架
    'timeframe_entry': '15m',        # 入场判断时间框架
    'position_size': 0.1,            # 仓位大小（账户资金比例）
    'leverage': 100,                 # 杠杆倍数
    'max_trade_duration': timedelta(hours=24),  # 最大持仓时间
    'max_trades_per_day': 3,         # 每日最大交易次数
    'min_hours_between_trades': 4,   # 交易之间的最小间隔（小时）
    'enable_pyramiding': False,      # 是否允许金字塔加仓
    'enable_trailing_stop': True,    # 是否启用追踪止损
    'trailing_stop_activation': 0.01,# 追踪止损激活比例
    'trailing_stop_distance': 0.005, # 追踪止损距离比例
}

# 技术分析配置
ANALYSIS_CONFIG = {
    # 移动平均线
    'short_ma_period': 20,          # 短期移动平均线周期
    'long_ma_period': 50,           # 长期移动平均线周期
    'trend_periods': 10,            # 趋势确认周期数
    
    # 支撑/阻力位
    'support_resistance_lookback': 100,  # 支撑/阻力位回看周期数
    'support_resistance_threshold': 0.01,# 支撑/阻力位阈值
    'min_touches': 2,               # 最小触及次数
    
    # K线形态
    'doji_ratio': 0.05,             # 十字星实体比例阈值
    'engulfing_ratio': 1.5,         # 吞没形态大小比例
    'hammer_ratio': 2.0,            # 锤子线影线比例
    
    # 信号确认
    'confirmation_periods': 3,      # 信号确认周期数
    'min_pattern_quality': 0.7,     # 最小形态质量
}

# 数据库设置
DATABASE_CONFIG = {
    'database_type': 'sqlite',      # 数据库类型
    'database_name': 'eth_trader.db',  # 数据库名称
    'auto_backup': True,            # 自动备份
    'backup_interval': timedelta(days=1),  # 备份间隔
}

# 回测配置
BACKTEST_CONFIG = {
    'start_date': datetime.now() - timedelta(days=30),  # 回测开始日期
    'end_date': datetime.now(),      # 回测结束日期
    'initial_capital': 10000,        # 初始资金
    'commission': 0.0004,            # 交易手续费
    'slippage': 0.0002,              # 滑点
    'trade_on_close': False,         # 是否在K线收盘价交易
    'enable_fractional': True,       # 是否支持小数仓位
    'use_adjusted_prices': True,     # 是否使用调整后的价格
}

# 程序设置
APP_CONFIG = {
    'debug': os.getenv('DEBUG', 'False').lower() in ('true', '1', 't'),
    'log_level': os.getenv('LOG_LEVEL', 'INFO'),
    'update_interval': 60,           # 数据更新间隔（秒）
    'max_retries': 3,                # 最大重试次数
    'retry_wait': 5,                 # 重试等待时间（秒）
    'timezone': 'UTC',               # 时区
    'enable_notifications': False,   # 启用通知
    'notification_types': ['email', 'telegram'],  # 通知类型
}

# 信号评分权重
SIGNAL_SCORING = {
    'trend_weight': 40,              # 趋势权重
    'pattern_weight': 30,            # 形态权重
    'support_resistance_weight': 20, # 支撑/阻力位权重
    'volume_weight': 10,             # 成交量权重
    'minimum_score': 70,             # 最小信号分数
    'risk_reward_ratio': 2.0,        # 风险回报比
}

# 期权交易参数
OPTIONS_CONFIG = {
    'days_to_expiry': 7,             # 到期天数
    'delta_threshold': 0.5,          # Delta阈值
    'max_implied_volatility': 1.2,   # 最大隐含波动率
    'min_implied_volatility': 0.4,   # 最小隐含波动率
    'gamma_threshold': 0.02,         # Gamma阈值
    'vega_threshold': 0.1,           # Vega阈值
    'theta_threshold': -0.01,        # Theta阈值
    'option_pricing_model': 'black_scholes',  # 期权定价模型
}

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PATHS = {
    'data_dir': os.path.join(BASE_DIR, 'data'),
    'database_dir': os.path.join(BASE_DIR, 'database'),
    'logs_dir': os.path.join(BASE_DIR, 'logs'),
    'results_dir': os.path.join(BASE_DIR, 'results'),
    'backups_dir': os.path.join(BASE_DIR, 'database', 'backups'),
}

# 确保所有路径存在
for path in PATHS.values():
    os.makedirs(path, exist_ok=True)


if __name__ == "__main__":
    import pprint
    
    print("API配置:")
    pprint.pprint({k: '***' if 'secret' in k else v for k, v in API_CONFIG.items()})
    
    print("\n交易配置:")
    pprint.pprint(TRADING_CONFIG)
    
    print("\n技术分析配置:")
    pprint.pprint(ANALYSIS_CONFIG)
    
    print("\n路径配置:")
    pprint.pprint(PATHS)
    
    # 测试路径是否创建成功
    print("\n检查路径是否创建成功:")
    for name, path in PATHS.items():
        print(f"{name}: {'存在' if os.path.exists(path) else '不存在'}") 