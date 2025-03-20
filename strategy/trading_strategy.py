#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
交易策略模块，基于市场分析结果生成交易信号并实现交易逻辑
"""

import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple

import pandas as pd
import numpy as np
from enum import Enum

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trading_strategy')

class TradeDirection(Enum):
    """交易方向枚举"""
    LONG = 1
    SHORT = -1
    NONE = 0

class TradeStatus(Enum):
    """交易状态枚举"""
    OPEN = 1
    CLOSED = 0
    PENDING = 2

class TradingStrategy:
    """
    交易策略类，实现裸K交易策略
    """
    
    def __init__(self, config: Dict[str, Any], data_fetcher, market_analyzer):
        """
        初始化交易策略
        
        Args:
            config: 配置字典
            data_fetcher: 数据获取器实例
            market_analyzer: 市场分析器实例
        """
        self.config = config
        self.trading_config = config['TRADING_CONFIG']
        self.options_config = config['OPTIONS_CONFIG']
        self.signal_scoring = config['SIGNAL_SCORING']
        self.data_fetcher = data_fetcher
        self.market_analyzer = market_analyzer
        self.results_dir = config['PATHS']['results_dir']
        
        # 交易状态追踪
        self.open_positions = []
        self.trade_history = []
        self.daily_pnl = 0
        self.last_signal_time = None
        self.position_start_time = None
        
        # 确保结果目录存在
        os.makedirs(self.results_dir, exist_ok=True)
    
    def run_strategy(self) -> Dict[str, Any]:
        """
        运行交易策略，进行市场分析并生成交易信号
        
        Returns:
            包含策略结果的字典
        """
        try:
            # 获取用于趋势判断的1小时K线数据
            df_1h = self.data_fetcher.get_latest_data(
                timeframe=self.trading_config['timeframe_trend'],
                n_periods=100
            )
            
            # 获取用于入场判断的15分钟K线数据
            df_15m = self.data_fetcher.get_latest_data(
                timeframe=self.trading_config['timeframe_entry'],
                n_periods=100
            )
            
            if df_1h.empty or df_15m.empty:
                logger.error("获取市场数据失败，无法运行策略")
                return {'status': 'error', 'message': '获取市场数据失败'}
            
            # 市场分析
            market_analysis = self.market_analyzer.analyze_market(df_1h, df_15m)
            
            # 处理现有交易
            self._manage_open_positions()
            
            # 检查是否可以下新订单
            new_order = None
            if not self._has_open_position() and market_analysis['signal']['action'] != 'HOLD':
                # 生成交易订单
                new_order = self._generate_order(market_analysis)
                
                # 如果生成了有效订单
                if new_order:
                    # 选择适当的期权合约
                    new_order = self._select_option_contract(new_order)
                    
                    # 添加到开仓列表
                    if 'contract' in new_order and new_order['contract']:
                        self.open_positions.append(new_order)
                        self.position_start_time = datetime.now()
                        logger.info(f"新增交易: {new_order['direction'].name} {new_order['contract']['symbol']} @ {new_order['entry_price']}")
            
            # 生成结果
            result = {
                'status': 'success',
                'timestamp': datetime.now(),
                'market_analysis': market_analysis,
                'open_positions': self.open_positions,
                'trade_history': self.trade_history[-10:] if len(self.trade_history) > 10 else self.trade_history,
                'daily_pnl': self.daily_pnl,
                'new_order': new_order
            }
            
            # 记录结果
            self._log_strategy_result(result)
            
            return result
            
        except Exception as e:
            logger.error(f"运行策略时发生错误: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _generate_order(self, market_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        基于市场分析生成交易订单
        
        Args:
            market_analysis: 市场分析结果
            
        Returns:
            交易订单字典，如果没有交易信号则返回None
        """
        signal = market_analysis['signal']
        
        # 如果信号置信度不足或动作为HOLD，不生成订单
        if signal['confidence'] < self.signal_scoring['minimum_score'] or signal['action'] == 'HOLD':
            logger.info(f"不满足交易条件: 置信度{signal['confidence']}，动作{signal['action']}")
            return None
        
        # 获取当前价格
        current_price = market_analysis['current_price']
        
        # 确定交易方向
        direction = TradeDirection.LONG if signal['direction'] == 'LONG' else TradeDirection.SHORT
        
        # 计算仓位大小（基于账户资金比例）
        position_size = self.trading_config['position_size']
        
        # 创建订单
        order = {
            'order_id': f"order_{int(time.time())}",
            'symbol': self.trading_config['symbol'],
            'direction': direction,
            'position_size': position_size,
            'entry_price': current_price,
            'stop_loss': signal['stop_loss'],
            'take_profit': signal['take_profit'],
            'status': TradeStatus.PENDING,
            'open_time': datetime.now(),
            'close_time': None,
            'pnl': 0.0,
            'contract': None,  # 将由_select_option_contract设置
            'reasoning': signal['reasoning']
        }
        
        logger.info(f"生成{direction.name}单: 入场价{current_price}, 止损{signal['stop_loss']}, 止盈{signal['take_profit']}")
        return order
    
    def _select_option_contract(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        为交易选择合适的期权合约
        
        Args:
            order: 交易订单
            
        Returns:
            更新了合约信息的订单
        """
        try:
            # 获取ETH期权数据
            options_data = self.data_fetcher.fetch_eth_options(
                expiry_days=self.options_config['days_to_expiry']
            )
            
            if options_data.empty:
                logger.warning("未能获取期权数据，无法选择合约")
                return order
            
            # 当前ETH价格
            current_price = order['entry_price']
            
            # 根据交易方向选择期权类型
            option_type = 'call' if order['direction'] == TradeDirection.LONG else 'put'
            
            # 过滤出符合条件的期权合约
            filtered_options = options_data[
                (options_data['option_type'] == option_type) & 
                (options_data['days_to_expiry'] >= 1) &  # 确保至少有1天到期时间
                (abs(options_data['delta'].abs() - self.options_config['delta_threshold']) < 0.2)  # Delta接近目标值
            ]
            
            if filtered_options.empty:
                logger.warning(f"未找到符合条件的{option_type}期权合约")
                return order
            
            # 根据Delta接近度排序
            filtered_options['delta_diff'] = abs(filtered_options['delta'].abs() - self.options_config['delta_threshold'])
            filtered_options = filtered_options.sort_values('delta_diff')
            
            # 选择最佳合约
            best_contract = filtered_options.iloc[0]
            
            # 更新订单
            order['contract'] = {
                'symbol': best_contract['symbol'],
                'strike': best_contract['strike'],
                'option_type': best_contract['option_type'],
                'expiry': best_contract['expiry'].strftime('%Y-%m-%d'),
                'days_to_expiry': int(best_contract['days_to_expiry']),
                'price': float(best_contract['ask'] if order['direction'] == TradeDirection.LONG else best_contract['bid']),
                'delta': float(best_contract['delta']),
                'iv': float(best_contract['iv']) if not pd.isna(best_contract['iv']) else None
            }
            
            # 计算杠杆
            strike_distance = abs(current_price - best_contract['strike'])
            option_price = order['contract']['price']
            
            # 简单估计杠杆
            if option_price > 0:
                estimated_leverage = strike_distance / option_price
                order['estimated_leverage'] = min(estimated_leverage, 100)  # 限制最大杠杆
            else:
                order['estimated_leverage'] = 1
            
            logger.info(f"选择期权合约: {order['contract']['symbol']}, 行权价: {order['contract']['strike']}, Delta: {order['contract']['delta']}, 杠杆: {order.get('estimated_leverage', 'N/A')}")
            
            return order
            
        except Exception as e:
            logger.error(f"选择期权合约时发生错误: {str(e)}")
            return order
    
    def _manage_open_positions(self):
        """管理开仓，检查止盈止损和时间限制"""
        if not self.open_positions:
            return
        
        # 获取当前价格
        try:
            current_price = self.data_fetcher.fetch_current_price()
        except Exception as e:
            logger.error(f"获取当前价格失败: {str(e)}")
            return
        
        now = datetime.now()
        positions_to_close = []
        
        for position in self.open_positions:
            # 检查是否达到最大持仓时间
            position_time = now - self.position_start_time if self.position_start_time else timedelta(hours=25)
            if position_time > self.trading_config['max_trade_duration']:
                position['close_reason'] = "达到最大持仓时间"
                positions_to_close.append(position)
                continue
            
            # 不同方向的止盈止损检查
            if position['direction'] == TradeDirection.LONG:
                # 多头止损
                if current_price <= position['stop_loss']:
                    position['close_reason'] = "触发止损"
                    positions_to_close.append(position)
                # 多头止盈
                elif current_price >= position['take_profit']:
                    position['close_reason'] = "触发止盈"
                    positions_to_close.append(position)
            else:  # SHORT
                # 空头止损
                if current_price >= position['stop_loss']:
                    position['close_reason'] = "触发止损"
                    positions_to_close.append(position)
                # 空头止盈
                elif current_price <= position['take_profit']:
                    position['close_reason'] = "触发止盈"
                    positions_to_close.append(position)
        
        # 关闭需要平仓的交易
        for position in positions_to_close:
            self._close_position(position, current_price)
    
    def _close_position(self, position: Dict[str, Any], current_price: float):
        """
        关闭交易仓位
        
        Args:
            position: 要关闭的交易仓位
            current_price: 当前价格
        """
        position['close_price'] = current_price
        position['close_time'] = datetime.now()
        position['status'] = TradeStatus.CLOSED
        
        # 计算盈亏
        if position['direction'] == TradeDirection.LONG:
            position['pnl'] = (current_price - position['entry_price']) / position['entry_price']
        else:  # SHORT
            position['pnl'] = (position['entry_price'] - current_price) / position['entry_price']
        
        # 模拟杠杆效应
        position['pnl'] = position['pnl'] * self.trading_config['leverage']
        
        # 更新每日盈亏
        self.daily_pnl += position['pnl']
        
        # 添加到历史记录
        self.trade_history.append(position.copy())
        
        # 从开仓列表中移除
        self.open_positions.remove(position)
        
        logger.info(f"关闭交易: {position['direction'].name} {position['contract']['symbol']}, 原因: {position['close_reason']}, 盈亏: {position['pnl']:.2%}")
    
    def _has_open_position(self) -> bool:
        """
        检查是否有开仓
        
        Returns:
            如果有开仓则返回True
        """
        return len(self.open_positions) > 0
    
    def _log_strategy_result(self, result: Dict[str, Any]):
        """
        记录策略结果
        
        Args:
            result: 策略结果字典
        """
        # 创建简单的日志文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(self.results_dir, f"strategy_log_{timestamp}.txt")
        
        with open(log_file, 'w') as f:
            f.write(f"策略运行时间: {result['timestamp']}\n\n")
            
            f.write("市场分析:\n")
            f.write(f"  趋势: {result['market_analysis']['trend']}\n")
            f.write(f"  当前价格: {result['market_analysis']['current_price']}\n")
            f.write(f"  K线形态: {result['market_analysis']['pattern']['description']}\n")
            f.write(f"  信号类型: {result['market_analysis']['signal']['action']}\n")
            f.write(f"  信号置信度: {result['market_analysis']['signal']['confidence']}\n")
            
            if result['new_order']:
                f.write("\n新交易订单:\n")
                f.write(f"  方向: {result['new_order']['direction']}\n")
                f.write(f"  入场价: {result['new_order']['entry_price']}\n")
                f.write(f"  止损价: {result['new_order']['stop_loss']}\n")
                f.write(f"  止盈价: {result['new_order']['take_profit']}\n")
                if result['new_order']['contract']:
                    f.write(f"  期权合约: {result['new_order']['contract']['symbol']}\n")
                    f.write(f"  行权价: {result['new_order']['contract']['strike']}\n")
                    f.write(f"  到期日: {result['new_order']['contract']['expiry']}\n")
            
            f.write(f"\n当前持仓数量: {len(result['open_positions'])}\n")
            f.write(f"历史交易数量: {len(result['trade_history'])}\n")
            f.write(f"每日盈亏: {result['daily_pnl']:.2%}\n")
        
        logger.info(f"策略日志已保存至 {log_file}")
    
    def reset_daily_stats(self):
        """重置每日统计数据"""
        self.daily_pnl = 0
        self.last_signal_time = None
        logger.info("每日统计数据已重置")


if __name__ == "__main__":
    # 测试代码，直接运行该模块时执行
    import sys
    import os
    
    # 添加项目根目录到路径
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from config import API_CONFIG, TRADING_CONFIG, ANALYSIS_CONFIG, OPTIONS_CONFIG, SIGNAL_SCORING, PATHS
    from data.data_fetcher import DataFetcher
    from models.market_analyzer import MarketAnalyzer
    
    # 测试配置
    test_config = {
        'API_CONFIG': API_CONFIG,
        'TRADING_CONFIG': TRADING_CONFIG,
        'ANALYSIS_CONFIG': ANALYSIS_CONFIG,
        'OPTIONS_CONFIG': OPTIONS_CONFIG,
        'SIGNAL_SCORING': SIGNAL_SCORING,
        'PATHS': PATHS
    }
    
    # 初始化组件
    data_fetcher = DataFetcher(test_config)
    market_analyzer = MarketAnalyzer(test_config)
    
    # 初始化策略
    strategy = TradingStrategy(test_config, data_fetcher, market_analyzer)
    
    # 运行策略
    result = strategy.run_strategy()
    
    print("策略运行结果:")
    print(f"状态: {result['status']}")
    if result['status'] == 'success':
        print(f"市场趋势: {result['market_analysis']['trend']}")
        print(f"信号动作: {result['market_analysis']['signal']['action']}")
        print(f"信号置信度: {result['market_analysis']['signal']['confidence']}")
        if result['new_order']:
            print(f"新订单: {result['new_order']['direction']} @ {result['new_order']['entry_price']}")
            print(f"止损: {result['new_order']['stop_loss']}, 止盈: {result['new_order']['take_profit']}")
            if result['new_order']['contract']:
                print(f"选择合约: {result['new_order']['contract']['symbol']}")
        else:
            print("无新订单")
    else:
        print(f"错误: {result.get('message', '未知错误')}") 