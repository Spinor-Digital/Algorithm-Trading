#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETH日交易算法系统主应用
基于"裸K实战买入形态"的ETH和ETH期权日内交易系统
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
import json

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

# 导入项目模块
from config import (
    API_CONFIG, TRADING_CONFIG, ANALYSIS_CONFIG, BACKTEST_CONFIG,
    OPTIONS_CONFIG, SIGNAL_SCORING, PATHS, APP_CONFIG
)
from data.data_fetcher import DataFetcher
from models.market_analyzer import MarketAnalyzer, TrendType, CandlePattern
from strategy.trading_strategy import TradingStrategy, TradeDirection, TradeStatus
from backtesting.backtester import Backtester
from utils.helpers import ensure_directories, format_price, create_candlestick_figure

# 配置日志
log_level = getattr(logging, APP_CONFIG['log_level'])
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(PATHS['logs_dir'], f"app_{datetime.now().strftime('%Y%m%d')}.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('app')

# 加载环境变量
load_dotenv()

# 全局变量
data_fetcher = None
market_analyzer = None
trading_strategy = None
backtester = None
stop_thread = False
background_thread = None
last_update_time = None
market_analysis = None
trading_signal = None

def init_components():
    """初始化所有组件"""
    global data_fetcher, market_analyzer, trading_strategy, backtester
    
    # 合并配置
    config = {
        'API_CONFIG': API_CONFIG,
        'TRADING_CONFIG': TRADING_CONFIG,
        'ANALYSIS_CONFIG': ANALYSIS_CONFIG,
        'BACKTEST_CONFIG': BACKTEST_CONFIG,
        'OPTIONS_CONFIG': OPTIONS_CONFIG,
        'SIGNAL_SCORING': SIGNAL_SCORING,
        'PATHS': PATHS,
        'APP_CONFIG': APP_CONFIG
    }
    
    # 确保所有目录存在
    ensure_directories(list(PATHS.values()))
    
    # 初始化组件
    try:
        data_fetcher = DataFetcher(config)
        market_analyzer = MarketAnalyzer(config)
        trading_strategy = TradingStrategy(config, data_fetcher, market_analyzer)
        backtester = Backtester(config, data_fetcher, market_analyzer)
        
        logger.info("所有组件初始化成功")
        return True
    except Exception as e:
        logger.error(f"组件初始化失败: {str(e)}")
        return False

def background_update():
    """
    后台更新线程，定期获取市场数据和运行策略
    """
    global stop_thread, last_update_time, market_analysis, trading_signal
    
    logger.info("后台更新线程已启动")
    
    while not stop_thread:
        try:
            # 运行策略
            strategy_result = trading_strategy.run_strategy()
            
            if strategy_result['status'] == 'success':
                # 更新全局变量
                market_analysis = strategy_result['market_analysis']
                trading_signal = strategy_result.get('new_order')
                last_update_time = datetime.now()
                
                logger.info(f"策略运行成功，信号: {market_analysis['signal']['action']}")
            else:
                logger.error(f"策略运行失败: {strategy_result.get('message', '未知错误')}")
            
            # 等待指定时间再次更新
            for i in range(APP_CONFIG['update_interval']):
                if stop_thread:
                    break
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"后台更新线程出错: {str(e)}")
            # 短暂等待后重试
            time.sleep(10)

def start_background_thread():
    """启动后台更新线程"""
    global background_thread, stop_thread
    
    if background_thread is None or not background_thread.is_alive():
        stop_thread = False
        background_thread = threading.Thread(target=background_update)
        background_thread.daemon = True
        background_thread.start()
        logger.info("已启动后台更新线程")
    else:
        logger.info("后台更新线程已在运行")

def stop_background_thread():
    """停止后台更新线程"""
    global stop_thread
    
    stop_thread = True
    logger.info("已发送停止信号给后台更新线程")

def plot_candlestick_with_analysis(df, support_levels, resistance_levels, trend, pattern):
    """
    使用Plotly绘制带有分析结果的K线图
    
    Args:
        df: 包含OHLCV数据的DataFrame
        support_levels: 支撑位列表
        resistance_levels: 阻力位列表
        trend: 趋势类型
        pattern: K线形态
        
    Returns:
        Plotly图表对象
    """
    # 创建子图
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.8, 0.2]
    )
    
    # 添加K线图
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K线'
        ),
        row=1, col=1
    )
    
    # 添加移动平均线
    short_ma = df['close'].rolling(window=ANALYSIS_CONFIG['short_ma_period']).mean()
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=short_ma,
            name=f"MA({ANALYSIS_CONFIG['short_ma_period']})",
            line=dict(color='blue', width=1)
        ),
        row=1, col=1
    )
    
    long_ma = df['close'].rolling(window=ANALYSIS_CONFIG['long_ma_period']).mean()
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=long_ma,
            name=f"MA({ANALYSIS_CONFIG['long_ma_period']})",
            line=dict(color='purple', width=1)
        ),
        row=1, col=1
    )
    
    # 添加支撑位
    for level in support_levels:
        fig.add_trace(
            go.Scatter(
                x=[df.index[0], df.index[-1]],
                y=[level, level],
                name=f'支撑: {level:.2f}',
                line=dict(color='green', width=1, dash='dash')
            ),
            row=1, col=1
        )
    
    # 添加阻力位
    for level in resistance_levels:
        fig.add_trace(
            go.Scatter(
                x=[df.index[0], df.index[-1]],
                y=[level, level],
                name=f'阻力: {level:.2f}',
                line=dict(color='red', width=1, dash='dash')
            ),
            row=1, col=1
        )
    
    # 添加成交量图
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['volume'],
            name='成交量',
            marker=dict(
                color=np.where(df['close'] >= df['open'], 'red', 'green'),
            )
        ),
        row=2, col=1
    )
    
    # 获取趋势信息
    trend_info = {
        TrendType.UPTREND.name: '上升趋势',
        TrendType.DOWNTREND.name: '下降趋势',
        TrendType.SIDEWAYS.name: '横盘整理'
    }
    
    # 设置图表布局和标题
    fig.update_layout(
        title=f"市场分析 - {trend_info.get(trend, trend)} - {pattern['description']}",
        xaxis_title="时间",
        yaxis_title="价格",
        xaxis_rangeslider_visible=False,
        height=700,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    
    return fig

def plot_backtest_results(equity_curve_df, trades_df):
    """
    绘制回测结果图表
    
    Args:
        equity_curve_df: 权益曲线DataFrame
        trades_df: 交易记录DataFrame
        
    Returns:
        Plotly图表对象
    """
    # 创建子图
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3]
    )
    
    # 添加权益曲线
    fig.add_trace(
        go.Scatter(
            x=equity_curve_df.index,
            y=equity_curve_df['equity'],
            name='权益曲线',
            line=dict(color='blue', width=2)
        ),
        row=1, col=1
    )
    
    # 添加交易点
    if not trades_df.empty:
        # 处理时间格式
        trades_df['open_time'] = pd.to_datetime(trades_df['open_time'])
        trades_df['close_time'] = pd.to_datetime(trades_df['close_time'])
        
        # 多头交易
        long_trades = trades_df[trades_df['direction'] == 'LONG']
        if not long_trades.empty:
            # 入场点
            fig.add_trace(
                go.Scatter(
                    x=long_trades['open_time'],
                    y=long_trades['entry_price'],
                    name='多头入场',
                    mode='markers',
                    marker=dict(color='green', size=10, symbol='triangle-up')
                ),
                row=1, col=1
            )
            
            # 出场点
            fig.add_trace(
                go.Scatter(
                    x=long_trades['close_time'],
                    y=long_trades['close_price'],
                    name='多头出场',
                    mode='markers',
                    marker=dict(color='green', size=10, symbol='triangle-down')
                ),
                row=1, col=1
            )
        
        # 空头交易
        short_trades = trades_df[trades_df['direction'] == 'SHORT']
        if not short_trades.empty:
            # 入场点
            fig.add_trace(
                go.Scatter(
                    x=short_trades['open_time'],
                    y=short_trades['entry_price'],
                    name='空头入场',
                    mode='markers',
                    marker=dict(color='red', size=10, symbol='triangle-down')
                ),
                row=1, col=1
            )
            
            # 出场点
            fig.add_trace(
                go.Scatter(
                    x=short_trades['close_time'],
                    y=short_trades['close_price'],
                    name='空头出场',
                    mode='markers',
                    marker=dict(color='red', size=10, symbol='triangle-up')
                ),
                row=1, col=1
            )
    
    # 添加回撤曲线
    if 'equity' in equity_curve_df.columns:
        # 计算回撤
        equity_curve_df['peak'] = equity_curve_df['equity'].cummax()
        equity_curve_df['drawdown'] = (equity_curve_df['equity'] - equity_curve_df['peak']) / equity_curve_df['peak'] * 100
        
        fig.add_trace(
            go.Scatter(
                x=equity_curve_df.index,
                y=equity_curve_df['drawdown'],
                name='回撤(%)',
                line=dict(color='red', width=1)
            ),
            row=2, col=1
        )
    
    # 设置图表布局
    fig.update_layout(
        title="回测结果",
        xaxis_title="时间",
        yaxis_title="权益",
        yaxis2_title="回撤(%)",
        xaxis_rangeslider_visible=False,
        height=700,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    
    return fig

def display_market_analysis():
    """显示市场分析结果"""
    if market_analysis is None:
        st.warning("暂无市场分析数据，请等待或点击'运行一次'按钮")
        return
    
    st.subheader("市场分析")
    
    # 创建两列布局
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 绘制K线图
        try:
            df_15m = data_fetcher.get_latest_data(timeframe=TRADING_CONFIG['timeframe_entry'], n_periods=100)
            
            if not df_15m.empty:
                fig = plot_candlestick_with_analysis(
                    df=df_15m,
                    support_levels=market_analysis['support_levels'],
                    resistance_levels=market_analysis['resistance_levels'],
                    trend=market_analysis['trend'],
                    pattern=market_analysis['pattern']
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("无法获取K线数据")
        except Exception as e:
            st.error(f"绘制图表时出错: {str(e)}")
    
    with col2:
        # 显示市场分析结果
        st.markdown("### 市场状态")
        
        # 趋势
        trend_mapping = {
            'UPTREND': ('📈 上升趋势', 'green'),
            'DOWNTREND': ('📉 下降趋势', 'red'),
            'SIDEWAYS': ('↔️ 横盘整理', 'gray')
        }
        trend_text, trend_color = trend_mapping.get(market_analysis['trend'], ('未知趋势', 'black'))
        st.markdown(f"**趋势:** <span style='color:{trend_color}'>{trend_text}</span>", unsafe_allow_html=True)
        
        # 当前价格
        st.markdown(f"**当前价格:** ${market_analysis['current_price']:.2f}")
        
        # K线形态
        pattern = market_analysis['pattern']
        st.markdown(f"**K线形态:** {pattern['description']}")
        st.markdown(f"**形态强度:** {pattern['strength']*100:.0f}%")
        
        # 支撑位
        if market_analysis['support_levels']:
            sl_text = ', '.join([f"${level:.2f}" for level in market_analysis['support_levels'][:3]])
            st.markdown(f"**支撑位:** {sl_text}")
        
        # 阻力位
        if market_analysis['resistance_levels']:
            rl_text = ', '.join([f"${level:.2f}" for level in market_analysis['resistance_levels'][:3]])
            st.markdown(f"**阻力位:** {rl_text}")
        
        # 信号
        signal = market_analysis['signal']
        signal_mapping = {
            'BUY': ('🟢 买入', 'green'),
            'SELL': ('🔴 卖出', 'red'),
            'HOLD': ('⚪ 持有', 'gray')
        }
        signal_text, signal_color = signal_mapping.get(signal['action'], ('未知信号', 'black'))
        st.markdown(f"**信号:** <span style='color:{signal_color}'>{signal_text}</span>", unsafe_allow_html=True)
        st.markdown(f"**置信度:** {signal['confidence']:.0f}%")
        
        # 如果有具体的交易信号，显示止损止盈位
        if signal['action'] in ['BUY', 'SELL'] and signal['confidence'] >= SIGNAL_SCORING['minimum_score']:
            st.markdown(f"**止损价:** ${signal['stop_loss']:.2f}")
            st.markdown(f"**止盈价:** ${signal['take_profit']:.2f}")
            
            # 计算风险回报比
            if signal['action'] == 'BUY':
                risk = market_analysis['current_price'] - signal['stop_loss']
                reward = signal['take_profit'] - market_analysis['current_price']
            else:  # SELL
                risk = signal['stop_loss'] - market_analysis['current_price']
                reward = market_analysis['current_price'] - signal['take_profit']
            
            if risk > 0:
                rrr = reward / risk
                st.markdown(f"**风险回报比:** 1:{rrr:.1f}")
        
        # 更新时间
        if last_update_time:
            st.markdown(f"**最后更新:** {last_update_time.strftime('%Y-%m-%d %H:%M:%S')}")

def display_trading_signals():
    """显示交易信号"""
    st.subheader("交易信号")
    
    # 显示当前信号
    if market_analysis and market_analysis['signal']:
        signal = market_analysis['signal']
        
        if signal['action'] != 'HOLD' and signal['confidence'] >= SIGNAL_SCORING['minimum_score']:
            # 信号卡片
            signal_color = "green" if signal['action'] == 'BUY' else "red"
            direction_text = "做多" if signal['direction'] == 'LONG' else "做空"
            
            st.markdown(
                f"""
                <div style="padding: 10px; border-radius: 5px; background-color: {signal_color}20; border: 1px solid {signal_color};">
                    <h3 style="color: {signal_color};">{signal['action']} {direction_text} 信号</h3>
                    <p><strong>价格:</strong> ${market_analysis['current_price']:.2f}</p>
                    <p><strong>止损:</strong> ${signal['stop_loss']:.2f}</p>
                    <p><strong>止盈:</strong> ${signal['take_profit']:.2f}</p>
                    <p><strong>置信度:</strong> {signal['confidence']:.0f}%</p>
                    <p><strong>原因:</strong> {signal['reasoning']}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.info("当前无交易信号或信号置信度不足")
    else:
        st.warning("暂无交易信号数据，请等待或点击'运行一次'按钮")
    
    # 显示当前持仓
    st.subheader("当前持仓")
    
    if trading_strategy and hasattr(trading_strategy, 'open_positions'):
        if trading_strategy.open_positions:
            for i, position in enumerate(trading_strategy.open_positions):
                position_color = "green" if position['direction'] == TradeDirection.LONG else "red"
                direction_text = "多头" if position['direction'] == TradeDirection.LONG else "空头"
                
                # 计算当前盈亏
                current_price = data_fetcher.fetch_current_price()
                if position['direction'] == TradeDirection.LONG:
                    pnl_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
                else:  # SHORT
                    pnl_pct = (position['entry_price'] - current_price) / position['entry_price'] * 100
                
                pnl_pct *= TRADING_CONFIG['leverage']  # 应用杠杆
                
                pnl_color = "green" if pnl_pct > 0 else "red"
                
                # 计算持仓时间
                hold_time = datetime.now() - position['open_time']
                hold_hours = hold_time.total_seconds() / 3600
                
                st.markdown(
                    f"""
                    <div style="padding: 10px; border-radius: 5px; background-color: {position_color}20; border: 1px solid {position_color};">
                        <h3 style="color: {position_color};">{direction_text} 仓位 #{i+1}</h3>
                        <p><strong>合约:</strong> {position['contract']['symbol']}</p>
                        <p><strong>入场价:</strong> ${position['entry_price']:.2f}</p>
                        <p><strong>当前价:</strong> ${current_price:.2f}</p>
                        <p><strong>止损:</strong> ${position['stop_loss']:.2f}</p>
                        <p><strong>止盈:</strong> ${position['take_profit']:.2f}</p>
                        <p><strong>盈亏:</strong> <span style="color: {pnl_color}">{pnl_pct:.2f}%</span></p>
                        <p><strong>持仓时间:</strong> {hold_hours:.1f}小时</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("当前无持仓")
    else:
        st.warning("无法获取持仓信息")
    
    # 显示历史交易
    st.subheader("历史交易")
    
    if trading_strategy and hasattr(trading_strategy, 'trade_history'):
        if trading_strategy.trade_history:
            # 转换为DataFrame便于显示
            history_data = []
            for trade in trading_strategy.trade_history:
                history_data.append({
                    '方向': "多头" if trade['direction'] == TradeDirection.LONG else "空头",
                    '合约': trade['contract']['symbol'] if 'contract' in trade and trade['contract'] else '未知',
                    '入场价': f"${trade['entry_price']:.2f}",
                    '出场价': f"${trade['close_price']:.2f}" if 'close_price' in trade else '未平仓',
                    '止损': f"${trade['stop_loss']:.2f}",
                    '止盈': f"${trade['take_profit']:.2f}",
                    '盈亏': f"{trade['pnl']*100:.2f}%" if 'pnl' in trade else '未知',
                    '开仓时间': trade['open_time'].strftime('%Y-%m-%d %H:%M'),
                    '平仓时间': trade['close_time'].strftime('%Y-%m-%d %H:%M') if 'close_time' in trade and trade['close_time'] else '未平仓',
                    '原因': trade.get('close_reason', '未平仓')
                })
            
            history_df = pd.DataFrame(history_data)
            st.dataframe(history_df)
        else:
            st.info("暂无历史交易")
    else:
        st.warning("无法获取历史交易信息")

def display_backtest_results(results):
    """显示回测结果"""
    if results is None or results['status'] != 'success':
        st.warning("暂无回测结果或回测失败")
        return
    
    st.subheader("回测结果")
    
    # 绘制权益曲线
    if 'equity_curve' in results and not results['equity_curve'].empty:
        fig = plot_backtest_results(results['equity_curve'], results['trades'])
        st.plotly_chart(fig, use_container_width=True)
    
    # 显示性能指标
    if 'performance' in results:
        perf = results['performance']
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("总回报率", f"{perf['total_return']*100:.2f}%")
            st.metric("最大回撤", f"{perf['max_drawdown']*100:.2f}%")
        
        with col2:
            st.metric("年化回报率", f"{perf['annual_return']*100:.2f}%")
            st.metric("夏普比率", f"{perf['sharpe_ratio']:.2f}")
        
        with col3:
            st.metric("胜率", f"{perf['win_rate']*100:.2f}%")
            st.metric("盈亏比", f"{perf['profit_factor']:.2f}")
        
        with col4:
            st.metric("交易次数", f"{perf['num_trades']}")
            st.metric("平均每笔盈亏", f"{perf['avg_trade']:.2f}")
    
    # 显示交易记录
    if 'trades' in results and not results['trades'].empty:
        st.subheader("交易记录")
        
        # 转换为更易读的格式
        trades_display = results['trades'].copy()
        
        if 'direction' in trades_display.columns:
            trades_display['方向'] = trades_display['direction'].map({'LONG': '多头', 'SHORT': '空头'})
        
        if 'open_time' in trades_display.columns:
            trades_display['开仓时间'] = pd.to_datetime(trades_display['open_time']).dt.strftime('%Y-%m-%d %H:%M')
        
        if 'close_time' in trades_display.columns:
            trades_display['平仓时间'] = pd.to_datetime(trades_display['close_time']).dt.strftime('%Y-%m-%d %H:%M')
        
        columns_mapping = {
            'entry_price': '入场价',
            'close_price': '出场价',
            'stop_loss': '止损价',
            'take_profit': '止盈价',
            'pnl_pct': '盈亏比例',
            'pnl_amount': '盈亏金额',
            'close_reason': '平仓原因'
        }
        
        for old_col, new_col in columns_mapping.items():
            if old_col in trades_display.columns:
                trades_display[new_col] = trades_display[old_col]
                if 'price' in old_col or 'amount' in old_col:
                    trades_display[new_col] = trades_display[new_col].map(lambda x: f"${x:.2f}" if isinstance(x, (int, float)) else x)
                elif 'pct' in old_col:
                    trades_display[new_col] = trades_display[new_col].map(lambda x: f"{x*100:.2f}%" if isinstance(x, (int, float)) else x)
        
        # 选择要显示的列
        display_columns = [col for col in ['方向', '入场价', '出场价', '止损价', '止盈价', 
                                        '盈亏比例', '盈亏金额', '开仓时间', '平仓时间', '平仓原因'] 
                          if col in trades_display.columns]
        
        st.dataframe(trades_display[display_columns])

def run_app():
    """运行Streamlit应用"""
    # 设置页面配置
    st.set_page_config(
        page_title="ETH日交易算法",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 标题
    st.title("ETH日交易算法")
    st.markdown("基于'裸K实战买入形态'的ETH和ETH期权日内交易系统")
    
    # 侧边栏 - 控制面板
    with st.sidebar:
        st.header("控制面板")
        
        # API设置
        st.subheader("API设置")
        binance_api_key = st.text_input("Binance API Key", value=API_CONFIG['binance_api_key'], type="password")
        binance_api_secret = st.text_input("Binance API Secret", value=API_CONFIG['binance_api_secret'], type="password")
        deribit_api_key = st.text_input("Deribit API Key", value=API_CONFIG['deribit_api_key'], type="password")
        deribit_api_secret = st.text_input("Deribit API Secret", value=API_CONFIG['deribit_api_secret'], type="password")
        use_testnet = st.checkbox("使用测试网络", value=API_CONFIG['use_testnet'])
        
        # 交易参数
        st.subheader("交易参数")
        position_size = st.slider("仓位大小(账户比例)", min_value=0.01, max_value=1.0, value=TRADING_CONFIG['position_size'], step=0.01)
        leverage = st.slider("杠杆倍数", min_value=1, max_value=100, value=TRADING_CONFIG['leverage'], step=1)
        max_trade_duration = st.slider("最大持仓时间(小时)", min_value=1, max_value=48, value=24, step=1)
        
        # 分析参数
        st.subheader("分析参数")
        short_ma = st.slider("短期均线周期", min_value=5, max_value=50, value=ANALYSIS_CONFIG['short_ma_period'], step=1)
        long_ma = st.slider("长期均线周期", min_value=20, max_value=200, value=ANALYSIS_CONFIG['long_ma_period'], step=5)
        min_score = st.slider("最小信号分数", min_value=50, max_value=90, value=SIGNAL_SCORING['minimum_score'], step=5)
        
        # 回测参数
        st.subheader("回测参数")
        backtest_days = st.slider("回测天数", min_value=7, max_value=90, value=30, step=1)
        initial_capital = st.number_input("初始资金(USDT)", min_value=1000, max_value=1000000, value=BACKTEST_CONFIG['initial_capital'], step=1000)
        
        # 应用按钮
        if st.button("应用设置"):
            # 更新配置
            API_CONFIG['binance_api_key'] = binance_api_key
            API_CONFIG['binance_api_secret'] = binance_api_secret
            API_CONFIG['deribit_api_key'] = deribit_api_key
            API_CONFIG['deribit_api_secret'] = deribit_api_secret
            API_CONFIG['use_testnet'] = use_testnet
            
            TRADING_CONFIG['position_size'] = position_size
            TRADING_CONFIG['leverage'] = leverage
            TRADING_CONFIG['max_trade_duration'] = timedelta(hours=max_trade_duration)
            
            ANALYSIS_CONFIG['short_ma_period'] = short_ma
            ANALYSIS_CONFIG['long_ma_period'] = long_ma
            SIGNAL_SCORING['minimum_score'] = min_score
            
            BACKTEST_CONFIG['start_date'] = datetime.now() - timedelta(days=backtest_days)
            BACKTEST_CONFIG['initial_capital'] = initial_capital
            
            # 重新初始化组件
            if init_components():
                st.success("设置已应用，组件已重新初始化")
            else:
                st.error("应用设置失败，请检查参数")
        
        # 控制按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("启动自动更新"):
                start_background_thread()
                st.success("已启动自动更新")
        
        with col2:
            if st.button("停止自动更新"):
                stop_background_thread()
                st.success("已停止自动更新")
        
        if st.button("运行一次"):
            try:
                if trading_strategy:
                    with st.spinner("正在运行策略..."):
                        global market_analysis, trading_signal, last_update_time
                        strategy_result = trading_strategy.run_strategy()
                        if strategy_result['status'] == 'success':
                            market_analysis = strategy_result['market_analysis']
                            trading_signal = strategy_result.get('new_order')
                            last_update_time = datetime.now()
                            st.success("策略运行成功")
                        else:
                            st.error(f"策略运行失败: {strategy_result.get('message', '未知错误')}")
                else:
                    st.error("请先初始化组件")
            except Exception as e:
                st.error(f"运行策略时出错: {str(e)}")
        
        if st.button("运行回测"):
            try:
                if backtester:
                    with st.spinner("正在运行回测..."):
                        backtest_result = backtester.run_backtest(
                            start_date=BACKTEST_CONFIG['start_date'],
                            end_date=BACKTEST_CONFIG['end_date'],
                            initial_capital=BACKTEST_CONFIG['initial_capital']
                        )
                        st.session_state.backtest_result = backtest_result
                        if backtest_result['status'] == 'success':
                            st.success("回测完成")
                        else:
                            st.error(f"回测失败: {backtest_result.get('message', '未知错误')}")
                else:
                    st.error("请先初始化组件")
            except Exception as e:
                st.error(f"运行回测时出错: {str(e)}")
    
    # 主要内容
    tab1, tab2, tab3 = st.tabs(["市场分析", "交易信号", "回测结果"])
    
    with tab1:
        display_market_analysis()
    
    with tab2:
        display_trading_signals()
    
    with tab3:
        # 如果有回测结果，显示回测结果
        backtest_result = st.session_state.get('backtest_result')
        display_backtest_results(backtest_result)

if __name__ == "__main__":
    # 初始化组件
    init_components()
    
    # 运行应用
    run_app() 