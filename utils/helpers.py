#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
工具函数模块，包含一些通用工具函数
"""

import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure

# 配置日志
logger = logging.getLogger('utils')

def ensure_directories(dirs: List[str]):
    """
    确保目录存在
    
    Args:
        dirs: 目录路径列表
    """
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        logger.info(f"确保目录存在: {d}")

def format_price(price: float, precision: int = 2) -> str:
    """
    格式化价格显示
    
    Args:
        price: 价格
        precision: 精度（小数位数）
        
    Returns:
        格式化后的价格字符串
    """
    return f"${price:.{precision}f}"

def calculate_drawdown(equity_series: pd.Series) -> pd.Series:
    """
    计算回撤序列
    
    Args:
        equity_series: 权益序列
        
    Returns:
        回撤序列
    """
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max
    return drawdown

def save_to_json(data: Any, filepath: str):
    """
    将数据保存为JSON文件
    
    Args:
        data: 要保存的数据
        filepath: 文件路径
    """
    try:
        # 处理datetime对象
        def json_serial(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        with open(filepath, 'w') as f:
            json.dump(data, f, default=json_serial, indent=4)
        
        logger.info(f"数据已保存到 {filepath}")
    except Exception as e:
        logger.error(f"保存JSON文件时出错: {str(e)}")

def load_from_json(filepath: str) -> Any:
    """
    从JSON文件加载数据
    
    Args:
        filepath: 文件路径
        
    Returns:
        加载的数据
    """
    try:
        if not os.path.exists(filepath):
            logger.warning(f"文件不存在: {filepath}")
            return None
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        logger.info(f"从 {filepath} 加载数据")
        return data
    except Exception as e:
        logger.error(f"加载JSON文件时出错: {str(e)}")
        return None

def parse_timeframe(timeframe: str) -> timedelta:
    """
    解析时间框架字符串为timedelta
    
    Args:
        timeframe: 时间框架字符串，如'1h', '15m', '1d'
        
    Returns:
        对应的timedelta
    """
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    elif unit == 'w':
        return timedelta(weeks=value)
    else:
        raise ValueError(f"无法解析时间框架: {timeframe}")

def create_candlestick_figure(df: pd.DataFrame, title: str = "K线图") -> Figure:
    """
    创建K线图
    
    Args:
        df: 包含OHLCV数据的DataFrame
        title: 图表标题
        
    Returns:
        matplotlib图表对象
    """
    # 创建图形
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 设置x轴格式
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.xticks(rotation=45)
    
    # 绘制K线
    width = 0.6
    width2 = 0.05
    
    up = df[df.close >= df.open]
    down = df[df.close < df.open]
    
    # 上涨K线
    ax.bar(up.index, up.close-up.open, width, bottom=up.open, color='red')
    ax.bar(up.index, up.high-up.close, width2, bottom=up.close, color='red')
    ax.bar(up.index, up.low-up.open, width2, bottom=up.open, color='red')
    
    # 下跌K线
    ax.bar(down.index, down.close-down.open, width, bottom=down.open, color='green')
    ax.bar(down.index, down.high-down.open, width2, bottom=down.open, color='green')
    ax.bar(down.index, down.low-down.close, width2, bottom=down.close, color='green')
    
    # 添加移动平均线
    for ma_period in [20, 50]:
        if len(df) > ma_period:
            ma = df['close'].rolling(ma_period).mean()
            ax.plot(df.index, ma, label=f'MA{ma_period}')
    
    # 设置标题和标签
    ax.set_title(title)
    ax.set_xlabel('日期')
    ax.set_ylabel('价格')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    return fig

def convert_to_timestamp(date_str: str) -> int:
    """
    将日期字符串转换为毫秒时间戳
    
    Args:
        date_str: 日期字符串，如'2023-01-01'或'2023-01-01 12:00:00'
        
    Returns:
        毫秒时间戳
    """
    try:
        # 尝试解析不同格式的日期字符串
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
            try:
                dt = datetime.strptime(date_str, fmt)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
        
        # 如果所有格式都失败，尝试解析ISO格式
        dt = pd.Timestamp(date_str).to_pydatetime()
        return int(dt.timestamp() * 1000)
    
    except Exception as e:
        logger.error(f"转换日期字符串时出错: {str(e)}")
        raise ValueError(f"无法解析日期: {date_str}")

def calculate_performance_stats(returns: pd.Series) -> Dict[str, float]:
    """
    计算绩效统计数据
    
    Args:
        returns: 收益率序列
        
    Returns:
        包含绩效指标的字典
    """
    if returns.empty:
        return {
            'total_return': 0,
            'annual_return': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'max_drawdown': 0,
            'volatility': 0,
            'win_rate': 0
        }
    
    # 总收益
    total_return = (1 + returns).prod() - 1
    
    # 年化收益 (假设252个交易日)
    n_periods = len(returns)
    annual_return = (1 + total_return) ** (252 / n_periods) - 1 if n_periods > 0 else 0
    
    # 波动率
    volatility = returns.std() * np.sqrt(252)
    
    # 夏普比率
    sharpe_ratio = annual_return / volatility if volatility > 0 else 0
    
    # 索提诺比率 (只考虑下行风险)
    downside_returns = returns[returns < 0]
    downside_deviation = downside_returns.std() * np.sqrt(252) if not downside_returns.empty else 0
    sortino_ratio = annual_return / downside_deviation if downside_deviation > 0 else 0
    
    # 最大回撤
    cum_returns = (1 + returns).cumprod()
    max_drawdown = (cum_returns / cum_returns.cummax() - 1).min()
    
    # 胜率
    win_rate = len(returns[returns > 0]) / len(returns) if len(returns) > 0 else 0
    
    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'max_drawdown': max_drawdown,
        'volatility': volatility,
        'win_rate': win_rate
    }

def timestamp_utc_to_local(timestamp: Union[int, float]) -> datetime:
    """
    将UTC时间戳转换为本地时间
    
    Args:
        timestamp: UTC时间戳（秒）
        
    Returns:
        本地时间datetime对象
    """
    utc_time = datetime.utcfromtimestamp(timestamp)
    # 获取本地时区偏移
    local_time = datetime.fromtimestamp(timestamp)
    return local_time

def get_candlestick_color(row) -> str:
    """
    根据K线方向返回颜色
    
    Args:
        row: DataFrame行，包含open和close值
        
    Returns:
        代表K线颜色的字符串
    """
    # 检查是上涨还是下跌蜡烛
    if row['close'] >= row['open']:
        return 'red'  # 上涨为红色
    else:
        return 'green'  # 下跌为绿色 