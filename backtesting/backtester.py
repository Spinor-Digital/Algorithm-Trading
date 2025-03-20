#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回测模块，用于在历史数据上评估交易策略性能
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
import copy

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('backtester')

class Backtester:
    """
    回测器类，用于在历史数据上评估交易策略性能
    """
    
    def __init__(self, config: Dict[str, Any], data_fetcher, market_analyzer):
        """
        初始化回测器
        
        Args:
            config: 配置字典
            data_fetcher: 数据获取器实例
            market_analyzer: 市场分析器实例
        """
        self.config = config
        self.backtest_config = config['BACKTEST_CONFIG']
        self.trading_config = config['TRADING_CONFIG']
        self.data_fetcher = data_fetcher
        self.market_analyzer = market_analyzer
        self.results_dir = config['PATHS']['results_dir']
        
        # 回测状态追踪
        self.trades = []
        self.equity_curve = []
        self.signals = []
        
        # 确保结果目录存在
        os.makedirs(self.results_dir, exist_ok=True)
    
    def run_backtest(self, start_date: Optional[datetime] = None, 
                   end_date: Optional[datetime] = None,
                   initial_capital: Optional[float] = None) -> Dict[str, Any]:
        """
        运行回测
        
        Args:
            start_date: 回测开始日期，默认为配置中的start_date
            end_date: 回测结束日期，默认为配置中的end_date
            initial_capital: 初始资金，默认为配置中的initial_capital
            
        Returns:
            包含回测结果的字典
        """
        # 使用提供的参数或配置的默认值
        start_date = start_date or self.backtest_config['start_date']
        end_date = end_date or self.backtest_config['end_date']
        initial_capital = initial_capital or self.backtest_config['initial_capital']
        
        try:
            logger.info(f"开始回测, 日期范围: {start_date} - {end_date}, 初始资金: {initial_capital}")
            
            # 获取历史数据
            df_1h = self.data_fetcher.fetch_historical_data(
                timeframe=self.trading_config['timeframe_trend'],
                start_date=start_date,
                end_date=end_date
            )
            
            df_15m = self.data_fetcher.fetch_historical_data(
                timeframe=self.trading_config['timeframe_entry'],
                start_date=start_date,
                end_date=end_date
            )
            
            if df_1h.empty or df_15m.empty:
                logger.error("获取历史数据失败，无法进行回测")
                return {'status': 'error', 'message': '获取历史数据失败'}
            
            # 初始化回测状态
            self.trades = []
            self.equity_curve = [{'timestamp': start_date, 'equity': initial_capital}]
            self.signals = []
            
            current_capital = initial_capital
            open_positions = []
            
            # 按照15分钟K线遍历（更细粒度）
            for i in range(100, len(df_15m)):
                date = df_15m.index[i]
                
                # 只在交易时段回测（可以自定义）
                
                # 获取当前及之前的数据
                current_1h = df_1h[df_1h.index <= date].iloc[-100:] if len(df_1h[df_1h.index <= date]) >= 100 else df_1h[df_1h.index <= date]
                current_15m = df_15m[df_15m.index <= date].iloc[-100:] if len(df_15m[df_15m.index <= date]) >= 100 else df_15m[df_15m.index <= date]
                
                if current_1h.empty or current_15m.empty:
                    continue
                
                # 当前价格
                current_price = current_15m['close'].iloc[-1]
                
                # 更新开仓的盈亏
                positions_to_close = []
                for position in open_positions:
                    # 检查是否达到最大持仓时间
                    position_time = date - position['open_time']
                    if position_time > self.trading_config['max_trade_duration']:
                        position['close_reason'] = "达到最大持仓时间"
                        position['close_time'] = date
                        position['close_price'] = current_price
                        positions_to_close.append(position)
                        continue
                    
                    # 检查是否触发止盈止损
                    if position['direction'] == 'LONG':
                        # 多头止损
                        if current_price <= position['stop_loss']:
                            position['close_reason'] = "触发止损"
                            position['close_time'] = date
                            position['close_price'] = position['stop_loss']  # 假设止损价成交
                            positions_to_close.append(position)
                        # 多头止盈
                        elif current_price >= position['take_profit']:
                            position['close_reason'] = "触发止盈"
                            position['close_time'] = date
                            position['close_price'] = position['take_profit']  # 假设止盈价成交
                            positions_to_close.append(position)
                    else:  # SHORT
                        # 空头止损
                        if current_price >= position['stop_loss']:
                            position['close_reason'] = "触发止损"
                            position['close_time'] = date
                            position['close_price'] = position['stop_loss']  # 假设止损价成交
                            positions_to_close.append(position)
                        # 空头止盈
                        elif current_price <= position['take_profit']:
                            position['close_reason'] = "触发止盈"
                            position['close_time'] = date
                            position['close_price'] = position['take_profit']  # 假设止盈价成交
                            positions_to_close.append(position)
                
                # 平仓并计算盈亏
                for position in positions_to_close:
                    # 计算盈亏
                    if position['direction'] == 'LONG':
                        pnl_pct = (position['close_price'] - position['entry_price']) / position['entry_price']
                    else:  # SHORT
                        pnl_pct = (position['entry_price'] - position['close_price']) / position['entry_price']
                    
                    # 应用杠杆
                    pnl_pct = pnl_pct * self.trading_config['leverage']
                    
                    # 考虑交易成本
                    pnl_pct -= self.backtest_config['commission']
                    
                    # 计算盈亏金额
                    pnl_amount = position['size'] * pnl_pct
                    
                    # 更新资金
                    current_capital += pnl_amount
                    
                    # 更新交易记录
                    position['pnl_pct'] = pnl_pct
                    position['pnl_amount'] = pnl_amount
                    self.trades.append(position)
                    
                    # 从开仓列表中移除
                    open_positions.remove(position)
                    
                    # 更新权益曲线
                    self.equity_curve.append({
                        'timestamp': date,
                        'equity': current_capital,
                        'trade_type': 'close',
                        'trade_id': position['id']
                    })
                
                # 检查是否需要生成新信号
                # 每小时或特定条件下生成信号
                if date.minute == 0 or (len(open_positions) == 0 and date.minute % 15 == 0):
                    # 市场分析
                    analysis = self.market_analyzer.analyze_market(current_1h, current_15m)
                    signal = analysis['signal']
                    
                    # 记录信号
                    self.signals.append({
                        'timestamp': date,
                        'action': signal['action'],
                        'direction': signal['direction'],
                        'confidence': signal['confidence'],
                        'price': current_price
                    })
                    
                    # 如果没有开仓且信号为买入或卖出，则开仓
                    if len(open_positions) == 0 and signal['action'] != 'HOLD' and signal['confidence'] >= 70:
                        
                        # 计算仓位大小（基于账户资金比例）
                        position_size = current_capital * self.trading_config['position_size']
                        
                        # 生成交易
                        trade = {
                            'id': len(self.trades) + 1,
                            'direction': signal['direction'],
                            'entry_price': current_price,
                            'stop_loss': signal['stop_loss'],
                            'take_profit': signal['take_profit'],
                            'open_time': date,
                            'size': position_size,
                            'reasoning': signal['reasoning']
                        }
                        
                        # 添加到开仓列表
                        open_positions.append(trade)
                        
                        # 更新权益曲线
                        self.equity_curve.append({
                            'timestamp': date,
                            'equity': current_capital,
                            'trade_type': 'open',
                            'trade_id': trade['id']
                        })
            
            # 回测结束，关闭所有未平仓的交易
            final_date = df_15m.index[-1]
            final_price = df_15m['close'].iloc[-1]
            
            for position in open_positions:
                position['close_reason'] = "回测结束"
                position['close_time'] = final_date
                position['close_price'] = final_price
                
                # 计算盈亏
                if position['direction'] == 'LONG':
                    pnl_pct = (position['close_price'] - position['entry_price']) / position['entry_price']
                else:  # SHORT
                    pnl_pct = (position['entry_price'] - position['close_price']) / position['entry_price']
                
                # 应用杠杆
                pnl_pct = pnl_pct * self.trading_config['leverage']
                
                # 考虑交易成本
                pnl_pct -= self.backtest_config['commission']
                
                # 计算盈亏金额
                pnl_amount = position['size'] * pnl_pct
                
                # 更新资金
                current_capital += pnl_amount
                
                # 更新交易记录
                position['pnl_pct'] = pnl_pct
                position['pnl_amount'] = pnl_amount
                self.trades.append(position)
            
            # 最终权益曲线点
            self.equity_curve.append({
                'timestamp': final_date,
                'equity': current_capital
            })
            
            # 转换为DataFrame便于后续分析
            equity_df = pd.DataFrame(self.equity_curve)
            trades_df = pd.DataFrame(self.trades)
            signals_df = pd.DataFrame(self.signals)
            
            # 计算性能指标
            performance = self._calculate_performance(equity_df, trades_df)
            
            # 生成回测报告
            self._generate_backtest_report(performance, equity_df, trades_df, signals_df)
            
            # 返回结果
            result = {
                'status': 'success',
                'performance': performance,
                'equity_curve': equity_df,
                'trades': trades_df,
                'signals': signals_df
            }
            
            logger.info(f"回测完成, 最终资金: {current_capital:.2f}, 总回报率: {(current_capital/initial_capital-1)*100:.2f}%")
            return result
            
        except Exception as e:
            logger.error(f"回测过程中发生错误: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _calculate_performance(self, equity_df: pd.DataFrame, trades_df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算策略性能指标
        
        Args:
            equity_df: 权益曲线DataFrame
            trades_df: 交易记录DataFrame
            
        Returns:
            包含性能指标的字典
        """
        if equity_df.empty or trades_df.empty:
            return {
                'total_return': 0,
                'annual_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'avg_trade': 0,
                'num_trades': 0
            }
        
        # 设置时间索引
        equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'])
        equity_df.set_index('timestamp', inplace=True)
        
        # 计算总回报
        initial_equity = equity_df['equity'].iloc[0]
        final_equity = equity_df['equity'].iloc[-1]
        total_return = (final_equity / initial_equity) - 1
        
        # 计算年化回报
        days = (equity_df.index[-1] - equity_df.index[0]).days
        if days > 0:
            annual_return = (1 + total_return) ** (365 / days) - 1
        else:
            annual_return = 0
        
        # 计算每日回报
        equity_df_daily = equity_df.resample('D').last().dropna()
        if len(equity_df_daily) > 1:
            equity_df_daily['daily_return'] = equity_df_daily['equity'].pct_change()
            
            # 计算夏普比率（假设无风险利率为0）
            sharpe_ratio = equity_df_daily['daily_return'].mean() / equity_df_daily['daily_return'].std() * np.sqrt(252) if equity_df_daily['daily_return'].std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 计算最大回撤
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = 1 - equity_df['equity'] / equity_df['cummax']
        max_drawdown = equity_df['drawdown'].max()
        
        # 交易统计
        num_trades = len(trades_df)
        if num_trades > 0:
            win_trades = trades_df[trades_df['pnl_amount'] > 0]
            loss_trades = trades_df[trades_df['pnl_amount'] <= 0]
            
            win_rate = len(win_trades) / num_trades if num_trades > 0 else 0
            
            # 计算盈亏比（总盈利/总亏损的绝对值）
            total_profit = win_trades['pnl_amount'].sum() if not win_trades.empty else 0
            total_loss = abs(loss_trades['pnl_amount'].sum()) if not loss_trades.empty else 0
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
            
            # 平均每笔交易盈亏
            avg_trade = trades_df['pnl_amount'].mean()
        else:
            win_rate = 0
            profit_factor = 0
            avg_trade = 0
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_trade': avg_trade,
            'num_trades': num_trades
        }
    
    def _generate_backtest_report(self, performance: Dict[str, Any], 
                                equity_df: pd.DataFrame, 
                                trades_df: pd.DataFrame,
                                signals_df: pd.DataFrame):
        """
        生成回测报告
        
        Args:
            performance: 性能指标字典
            equity_df: 权益曲线DataFrame
            trades_df: 交易记录DataFrame
            signals_df: 信号记录DataFrame
        """
        # 创建报告目录
        report_dir = os.path.join(self.results_dir, f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(report_dir, exist_ok=True)
        
        # 绘制权益曲线
        if not equity_df.empty:
            plt.figure(figsize=(12, 6))
            plt.plot(equity_df.index, equity_df['equity'], label='权益曲线')
            
            # 标记交易点
            if 'trade_type' in equity_df.columns:
                opens = equity_df[equity_df['trade_type'] == 'open']
                closes = equity_df[equity_df['trade_type'] == 'close']
                
                if not opens.empty:
                    plt.scatter(opens.index, opens['equity'], color='green', marker='^', label='开仓点')
                if not closes.empty:
                    plt.scatter(closes.index, closes['equity'], color='red', marker='v', label='平仓点')
            
            plt.title('回测权益曲线')
            plt.xlabel('日期')
            plt.ylabel('账户权益')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.savefig(os.path.join(report_dir, 'equity_curve.png'))
            plt.close()
        
        # 绘制回撤曲线
        if 'drawdown' in equity_df.columns:
            plt.figure(figsize=(12, 6))
            plt.plot(equity_df.index, equity_df['drawdown'] * 100)
            plt.title('回撤百分比')
            plt.xlabel('日期')
            plt.ylabel('回撤 (%)')
            plt.grid(True, alpha=0.3)
            plt.savefig(os.path.join(report_dir, 'drawdown.png'))
            plt.close()
        
        # 绘制月度回报热图
        if len(equity_df) > 30:
            monthly_returns = equity_df['equity'].resample('M').last().pct_change().dropna()
            monthly_returns = monthly_returns.groupby([monthly_returns.index.year, monthly_returns.index.month]).first()
            monthly_returns = monthly_returns.unstack()
            
            if not monthly_returns.empty:
                plt.figure(figsize=(12, 8))
                plt.pcolor(monthly_returns, cmap='RdYlGn', edgecolors='k', linewidths=1)
                plt.colorbar(label='月回报率')
                plt.title('月度回报热图')
                plt.xticks(np.arange(0.5, len(monthly_returns.columns), 1), monthly_returns.columns)
                plt.yticks(np.arange(0.5, len(monthly_returns.index), 1), monthly_returns.index)
                plt.savefig(os.path.join(report_dir, 'monthly_returns.png'))
                plt.close()
        
        # 生成性能指标报告
        with open(os.path.join(report_dir, 'performance_report.txt'), 'w') as f:
            f.write("==================== 回测性能报告 ====================\n\n")
            f.write(f"总回报率: {performance['total_return']*100:.2f}%\n")
            f.write(f"年化回报率: {performance['annual_return']*100:.2f}%\n")
            f.write(f"夏普比率: {performance['sharpe_ratio']:.2f}\n")
            f.write(f"最大回撤: {performance['max_drawdown']*100:.2f}%\n")
            f.write(f"胜率: {performance['win_rate']*100:.2f}%\n")
            f.write(f"盈亏比: {performance['profit_factor']:.2f}\n")
            f.write(f"平均每笔交易盈亏: {performance['avg_trade']:.2f}\n")
            f.write(f"总交易次数: {performance['num_trades']}\n\n")
            
            # 计算月度统计
            if len(equity_df) > 30:
                monthly_returns = equity_df['equity'].resample('M').last().pct_change().dropna()
                if not monthly_returns.empty:
                    f.write("==================== 月度回报统计 ====================\n\n")
                    for year in sorted(monthly_returns.index.year.unique()):
                        year_data = monthly_returns[monthly_returns.index.year == year]
                        f.write(f"{year}年月度回报: {year_data.mean()*100:.2f}% (平均), 最佳月: {year_data.max()*100:.2f}%, 最差月: {year_data.min()*100:.2f}%\n")
                    
                    f.write("\n最佳三个月:\n")
                    for date, ret in monthly_returns.nlargest(3).items():
                        f.write(f"{date.strftime('%Y-%m')}: {ret*100:.2f}%\n")
                    
                    f.write("\n最差三个月:\n")
                    for date, ret in monthly_returns.nsmallest(3).items():
                        f.write(f"{date.strftime('%Y-%m')}: {ret*100:.2f}%\n")
            
            # 连续盈利和亏损的统计
            if not trades_df.empty:
                f.write("\n==================== 交易统计 ====================\n\n")
                
                trades_df['is_win'] = trades_df['pnl_amount'] > 0
                
                # 计算连续盈利和亏损
                trades_df['streak'] = (trades_df['is_win'] != trades_df['is_win'].shift()).cumsum()
                streak_groups = trades_df.groupby('streak')
                
                max_win_streak = 0
                max_loss_streak = 0
                
                for _, group in streak_groups:
                    if len(group) > 0:
                        if group['is_win'].iloc[0]:
                            max_win_streak = max(max_win_streak, len(group))
                        else:
                            max_loss_streak = max(max_loss_streak, len(group))
                
                f.write(f"最大连续盈利次数: {max_win_streak}\n")
                f.write(f"最大连续亏损次数: {max_loss_streak}\n")
                
                # 计算平均持仓时间
                if 'open_time' in trades_df.columns and 'close_time' in trades_df.columns:
                    trades_df['duration'] = trades_df['close_time'] - trades_df['open_time']
                    avg_duration = trades_df['duration'].mean()
                    f.write(f"平均持仓时间: {avg_duration}\n")
                
                # 计算多空交易的表现
                if 'direction' in trades_df.columns:
                    long_trades = trades_df[trades_df['direction'] == 'LONG']
                    short_trades = trades_df[trades_df['direction'] == 'SHORT']
                    
                    long_win_rate = len(long_trades[long_trades['pnl_amount'] > 0]) / len(long_trades) if len(long_trades) > 0 else 0
                    short_win_rate = len(short_trades[short_trades['pnl_amount'] > 0]) / len(short_trades) if len(short_trades) > 0 else 0
                    
                    f.write(f"\n多头交易: {len(long_trades)}次, 胜率: {long_win_rate*100:.2f}%\n")
                    f.write(f"空头交易: {len(short_trades)}次, 胜率: {short_win_rate*100:.2f}%\n")
        
        # 保存交易记录
        if not trades_df.empty:
            trades_df.to_csv(os.path.join(report_dir, 'trades.csv'))
        
        # 保存信号记录
        if not signals_df.empty:
            signals_df.to_csv(os.path.join(report_dir, 'signals.csv'))
        
        # 保存权益曲线数据
        if not equity_df.empty:
            equity_df.to_csv(os.path.join(report_dir, 'equity_curve.csv'))
        
        logger.info(f"回测报告已生成至: {report_dir}")


if __name__ == "__main__":
    # 测试代码，直接运行该模块时执行
    import sys
    import os
    
    # 添加项目根目录到路径
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from config import API_CONFIG, TRADING_CONFIG, ANALYSIS_CONFIG, BACKTEST_CONFIG, PATHS
    from data.data_fetcher import DataFetcher
    from models.market_analyzer import MarketAnalyzer
    
    # 测试配置
    test_config = {
        'API_CONFIG': API_CONFIG,
        'TRADING_CONFIG': TRADING_CONFIG,
        'ANALYSIS_CONFIG': ANALYSIS_CONFIG,
        'BACKTEST_CONFIG': BACKTEST_CONFIG,
        'PATHS': PATHS
    }
    
    # 初始化组件
    data_fetcher = DataFetcher(test_config)
    market_analyzer = MarketAnalyzer(test_config)
    
    # 初始化回测器
    backtester = Backtester(test_config, data_fetcher, market_analyzer)
    
    # 运行回测
    # 使用较短的时间范围进行测试
    from datetime import datetime, timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # 回测最近30天
    
    result = backtester.run_backtest(start_date=start_date, end_date=end_date)
    
    print("回测结果:")
    if result['status'] == 'success':
        perf = result['performance']
        print(f"总回报率: {perf['total_return']*100:.2f}%")
        print(f"年化回报率: {perf['annual_return']*100:.2f}%")
        print(f"夏普比率: {perf['sharpe_ratio']:.2f}")
        print(f"最大回撤: {perf['max_drawdown']*100:.2f}%")
        print(f"胜率: {perf['win_rate']*100:.2f}%")
        print(f"总交易次数: {perf['num_trades']}")
    else:
        print(f"回测错误: {result.get('message', '未知错误')}") 