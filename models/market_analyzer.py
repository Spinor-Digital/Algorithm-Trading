#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
市场分析模块，负责分析市场趋势、识别支撑/阻力位、检测K线形态
"""

import os
import logging
from typing import Dict, List, Tuple, Optional, Union, Any
from enum import Enum

import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from scipy.cluster.hierarchy import linkage, fcluster
import matplotlib.pyplot as plt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('market_analyzer')

class TrendType(Enum):
    """市场趋势类型枚举"""
    UPTREND = 1
    DOWNTREND = -1
    SIDEWAYS = 0

class CandlePattern(Enum):
    """K线形态枚举"""
    BULLISH_ENGULFING = 1
    BEARISH_ENGULFING = -1
    HAMMER = 2
    SHOOTING_STAR = -2
    MORNING_STAR = 3
    EVENING_STAR = -3
    DOJI = 0
    NONE = 999

class MarketAnalyzer:
    """
    市场分析器类，负责分析市场趋势、支撑/阻力位和K线形态
    实现裸K交易策略的核心分析逻辑
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化市场分析器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.analysis_config = config['ANALYSIS_CONFIG']
        self.signal_scoring = config['SIGNAL_SCORING']
        self.results_dir = config['PATHS']['results_dir']
        
        # 确保结果目录存在
        os.makedirs(self.results_dir, exist_ok=True)
        
        logger.info("市场分析器初始化完成")
    
    def identify_trend(self, df: pd.DataFrame) -> TrendType:
        """
        识别市场趋势
        
        Args:
            df: 包含OHLCV数据的DataFrame
            
        Returns:
            趋势类型
        """
        if len(df) < 20:
            logger.warning("数据不足，无法准确识别趋势")
            return TrendType.SIDEWAYS
        
        # 计算短期和长期移动平均线
        short_ma = df['close'].rolling(window=self.analysis_config['short_ma_period']).mean()
        long_ma = df['close'].rolling(window=self.analysis_config['long_ma_period']).mean()
        
        # 获取最近的MA值
        latest_short_ma = short_ma.iloc[-1]
        latest_long_ma = long_ma.iloc[-1]
        
        # 计算MA差值序列
        ma_diff = short_ma - long_ma
        
        # 获取最近几个周期的MA差值
        recent_ma_diff = ma_diff.iloc[-self.analysis_config['trend_periods']:]
        
        # 检查MA交叉情况
        ma_cross_up = (ma_diff.iloc[-2] <= 0) and (ma_diff.iloc[-1] > 0)
        ma_cross_down = (ma_diff.iloc[-2] >= 0) and (ma_diff.iloc[-1] < 0)
        
        # 检查价格走势
        price_direction = np.polyfit(range(len(recent_ma_diff)), recent_ma_diff.values, 1)[0]
        
        # 检查支撑/阻力突破
        support_levels, resistance_levels = self.identify_support_resistance(df)
        current_price = df['close'].iloc[-1]
        
        # 计算价格与支撑/阻力的距离
        nearest_support = min(support_levels, key=lambda x: abs(x - current_price)) if support_levels else 0
        nearest_resistance = min(resistance_levels, key=lambda x: abs(x - current_price)) if resistance_levels else float('inf')
        
        # 计算趋势强度得分
        trend_score = 0
        
        # 移动平均线位置关系
        if latest_short_ma > latest_long_ma:
            trend_score += 1
        elif latest_short_ma < latest_long_ma:
            trend_score -= 1
        
        # 价格走势方向
        if price_direction > 0:
            trend_score += 1
        elif price_direction < 0:
            trend_score -= 1
        
        # 移动平均线交叉
        if ma_cross_up:
            trend_score += 2
        elif ma_cross_down:
            trend_score -= 2
        
        # 支撑/阻力突破
        if current_price > nearest_resistance * 1.01:  # 突破阻力
            trend_score += 2
        elif current_price < nearest_support * 0.99:  # 跌破支撑
            trend_score -= 2
        
        # 价格与MA的关系
        if df['close'].iloc[-1] > latest_short_ma:
            trend_score += 1
        elif df['close'].iloc[-1] < latest_short_ma:
            trend_score -= 1
        
        logger.debug(f"趋势评分: {trend_score}")
        
        # 根据趋势得分返回趋势类型
        if trend_score >= 2:
            return TrendType.UPTREND
        elif trend_score <= -2:
            return TrendType.DOWNTREND
        else:
            return TrendType.SIDEWAYS
    
    def identify_support_resistance(self, df: pd.DataFrame, n_levels: int = 5) -> Tuple[List[float], List[float]]:
        """
        识别支撑和阻力位
        
        Args:
            df: 包含OHLCV数据的DataFrame
            n_levels: 要识别的支撑/阻力位数量
            
        Returns:
            支撑位列表和阻力位列表的元组
        """
        if len(df) < 30:
            logger.warning("数据不足，无法准确识别支撑/阻力位")
            return [], []
        
        # 寻找局部极值点
        pivot_highs, pivot_lows = self.find_pivot_points(df)
        
        # 如果没有足够的极值点，返回空列表
        if len(pivot_highs) < 2 or len(pivot_lows) < 2:
            logger.warning("未找到足够的极值点")
            return [], []
        
        # 聚类支撑位
        if len(pivot_lows) >= 2:
            # 将价格点转换为一维数组用于聚类
            price_array = np.array(pivot_lows).reshape(-1, 1)
            
            # 使用层次聚类
            Z = linkage(price_array, 'ward')
            
            # 根据聚类结果分组
            max_d = 0.02 * np.mean(pivot_lows)  # 聚类距离阈值
            clusters = fcluster(Z, max_d, criterion='distance')
            
            # 对每个聚类计算平均价格
            support_levels = []
            for i in range(1, clusters.max() + 1):
                cluster_prices = [p for j, p in enumerate(pivot_lows) if clusters[j] == i]
                if cluster_prices:
                    support_levels.append(np.mean(cluster_prices))
        else:
            support_levels = []
        
        # 聚类阻力位
        if len(pivot_highs) >= 2:
            # 将价格点转换为一维数组用于聚类
            price_array = np.array(pivot_highs).reshape(-1, 1)
            
            # 使用层次聚类
            Z = linkage(price_array, 'ward')
            
            # 根据聚类结果分组
            max_d = 0.02 * np.mean(pivot_highs)  # 聚类距离阈值
            clusters = fcluster(Z, max_d, criterion='distance')
            
            # 对每个聚类计算平均价格
            resistance_levels = []
            for i in range(1, clusters.max() + 1):
                cluster_prices = [p for j, p in enumerate(pivot_highs) if clusters[j] == i]
                if cluster_prices:
                    resistance_levels.append(np.mean(cluster_prices))
        else:
            resistance_levels = []
        
        # 排序并取前n个
        support_levels = sorted(support_levels)[:n_levels]
        resistance_levels = sorted(resistance_levels, reverse=True)[:n_levels]
        
        return support_levels, resistance_levels
    
    def find_pivot_points(self, df: pd.DataFrame) -> Tuple[List[float], List[float]]:
        """
        在价格数据中寻找关键转折点
        
        Args:
            df: 包含OHLCV数据的DataFrame
            
        Returns:
            高点和低点价格列表的元组
        """
        # 使用scipy的argrelextrema函数查找局部极值
        order = min(5, len(df) // 10)  # 用于确定局部极值的窗口大小
        
        # 查找局部高点
        high_idx = argrelextrema(df['high'].values, np.greater, order=order)[0]
        pivot_highs = [df['high'].iloc[i] for i in high_idx]
        
        # 查找局部低点
        low_idx = argrelextrema(df['low'].values, np.less, order=order)[0]
        pivot_lows = [df['low'].iloc[i] for i in low_idx]
        
        logger.debug(f"识别到 {len(pivot_highs)} 个高点和 {len(pivot_lows)} 个低点")
        
        return pivot_highs, pivot_lows
    
    def identify_candlestick_pattern(self, df: pd.DataFrame, window: int = 3) -> Dict[str, Any]:
        """
        识别K线形态
        
        Args:
            df: 包含OHLCV数据的DataFrame
            window: 分析窗口大小
            
        Returns:
            包含K线形态信息的字典
        """
        if len(df) < window + 1:
            logger.warning("数据不足，无法识别K线形态")
            return {
                'pattern': CandlePattern.NONE,
                'strength': 0,
                'description': '无明显形态'
            }
        
        # 获取最近几根K线
        recent_candles = df.iloc[-window-1:].copy()
        
        # 计算每根K线的实体大小和影线长度
        recent_candles['body_size'] = abs(recent_candles['close'] - recent_candles['open'])
        recent_candles['upper_shadow'] = recent_candles['high'] - recent_candles[['open', 'close']].max(axis=1)
        recent_candles['lower_shadow'] = recent_candles[['open', 'close']].min(axis=1) - recent_candles['low']
        recent_candles['total_range'] = recent_candles['high'] - recent_candles['low']
        recent_candles['is_bullish'] = recent_candles['close'] > recent_candles['open']
        
        # 计算平均实体大小
        avg_body_size = recent_candles['body_size'].mean()
        
        # 最近一根K线
        current = recent_candles.iloc[-1]
        prev = recent_candles.iloc[-2] if len(recent_candles) > 1 else None
        prev2 = recent_candles.iloc[-3] if len(recent_candles) > 2 else None
        
        # 识别Doji（十字星）
        is_doji = current['body_size'] < 0.1 * current['total_range']
        
        # 识别Hammer（锤子线）
        is_hammer = (
            current['lower_shadow'] > 2 * current['body_size'] and
            current['upper_shadow'] < 0.2 * current['total_range'] and
            current['body_size'] < 0.5 * current['total_range']
        )
        
        # 识别Shooting Star（流星线）
        is_shooting_star = (
            current['upper_shadow'] > 2 * current['body_size'] and
            current['lower_shadow'] < 0.2 * current['total_range'] and
            current['body_size'] < 0.5 * current['total_range']
        )
        
        # 识别Engulfing（吞没形态）
        is_bullish_engulfing = (
            prev is not None and
            current['is_bullish'] and
            not prev['is_bullish'] and
            current['body_size'] > 1.5 * avg_body_size and
            current['open'] < prev['close'] and
            current['close'] > prev['open']
        )
        
        is_bearish_engulfing = (
            prev is not None and
            not current['is_bullish'] and
            prev['is_bullish'] and
            current['body_size'] > 1.5 * avg_body_size and
            current['open'] > prev['close'] and
            current['close'] < prev['open']
        )
        
        # 识别Morning Star（启明星）
        is_morning_star = (
            prev2 is not None and
            prev is not None and
            not prev2['is_bullish'] and
            current['is_bullish'] and
            prev2['body_size'] > avg_body_size and
            prev['body_size'] < 0.5 * avg_body_size and
            current['body_size'] > avg_body_size and
            prev['low'] < prev2['close'] and
            current['close'] > (prev2['open'] + prev2['close']) / 2
        )
        
        # 识别Evening Star（黄昏星）
        is_evening_star = (
            prev2 is not None and
            prev is not None and
            prev2['is_bullish'] and
            not current['is_bullish'] and
            prev2['body_size'] > avg_body_size and
            prev['body_size'] < 0.5 * avg_body_size and
            current['body_size'] > avg_body_size and
            prev['high'] > prev2['close'] and
            current['close'] < (prev2['open'] + prev2['close']) / 2
        )
        
        # 根据识别结果返回形态信息
        if is_bullish_engulfing:
            return {
                'pattern': CandlePattern.BULLISH_ENGULFING,
                'strength': 0.8,
                'description': '看涨吞没形态',
                'signal': 'BUY'
            }
        elif is_bearish_engulfing:
            return {
                'pattern': CandlePattern.BEARISH_ENGULFING,
                'strength': 0.8,
                'description': '看跌吞没形态',
                'signal': 'SELL'
            }
        elif is_hammer and current['close'] < current['open']:
            return {
                'pattern': CandlePattern.HAMMER,
                'strength': 0.7,
                'description': '锤子线（看涨反转）',
                'signal': 'BUY'
            }
        elif is_shooting_star and current['close'] > current['open']:
            return {
                'pattern': CandlePattern.SHOOTING_STAR,
                'strength': 0.7,
                'description': '流星线（看跌反转）',
                'signal': 'SELL'
            }
        elif is_morning_star:
            return {
                'pattern': CandlePattern.MORNING_STAR,
                'strength': 0.9,
                'description': '启明星（看涨反转）',
                'signal': 'BUY'
            }
        elif is_evening_star:
            return {
                'pattern': CandlePattern.EVENING_STAR,
                'strength': 0.9,
                'description': '黄昏星（看跌反转）',
                'signal': 'SELL'
            }
        elif is_doji:
            return {
                'pattern': CandlePattern.DOJI,
                'strength': 0.5,
                'description': '十字星（犹豫不决）',
                'signal': 'HOLD'
            }
        else:
            return {
                'pattern': CandlePattern.NONE,
                'strength': 0,
                'description': '无明显形态',
                'signal': 'HOLD'
            }
    
    def is_near_support_resistance(self, price: float, levels: List[float], threshold: float = 0.01) -> bool:
        """
        检查价格是否接近支撑/阻力位
        
        Args:
            price: 当前价格
            levels: 支撑或阻力位列表
            threshold: 接近阈值（百分比）
            
        Returns:
            如果价格接近任何支撑/阻力位则返回True
        """
        if not levels:
            return False
        
        for level in levels:
            if abs(price - level) / price < threshold:
                logger.debug(f"价格 {price} 接近支撑/阻力位 {level}")
                return True
        
        return False
    
    def plot_with_analysis(self, df: pd.DataFrame, support_levels: List[float], resistance_levels: List[float], 
                         trend: TrendType, pattern: Dict[str, Any], filename: str = 'market_analysis.png'):
        """
        绘制带有分析结果的K线图
        
        Args:
            df: 包含OHLCV数据的DataFrame
            support_levels: 支撑位列表
            resistance_levels: 阻力位列表
            trend: 趋势类型
            pattern: K线形态信息
            filename: 保存的文件名
        """
        # 创建图表
        fig, ax = plt.subplots(figsize=(12, 6))
        
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
        
        # 绘制移动平均线
        short_ma = df['close'].rolling(window=self.analysis_config['short_ma_period']).mean()
        long_ma = df['close'].rolling(window=self.analysis_config['long_ma_period']).mean()
        
        ax.plot(df.index, short_ma, 'blue', label=f'MA{self.analysis_config["short_ma_period"]}')
        ax.plot(df.index, long_ma, 'purple', label=f'MA{self.analysis_config["long_ma_period"]}')
        
        # 绘制支撑位
        y_range = df['high'].max() - df['low'].min()
        for level in support_levels:
            ax.axhline(y=level, color='g', linestyle='--', alpha=0.7)
            ax.text(df.index[-1], level, f'S: {level:.2f}', color='g')
        
        # 绘制阻力位
        for level in resistance_levels:
            ax.axhline(y=level, color='r', linestyle='--', alpha=0.7)
            ax.text(df.index[-1], level, f'R: {level:.2f}', color='r')
        
        # 添加趋势信息
        trend_text = {
            TrendType.UPTREND: '上升趋势',
            TrendType.DOWNTREND: '下降趋势',
            TrendType.SIDEWAYS: '横盘整理'
        }
        
        # 添加形态信息
        pattern_text = pattern['description']
        
        # 设置标题和标签
        plt.title(f'市场分析 - {trend_text[trend]} - {pattern_text}', fontsize=14)
        plt.xlabel('时间')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # 保存图表
        plt.tight_layout()
        file_path = os.path.join(self.results_dir, filename)
        plt.savefig(file_path)
        plt.close()
        
        logger.info(f"市场分析图表已保存至 {file_path}")
        
        return file_path
    
    def analyze_market(self, df_trend: pd.DataFrame, df_entry: pd.DataFrame) -> Dict[str, Any]:
        """
        综合分析市场，结合趋势和入场点分析
        
        Args:
            df_trend: 趋势分析用DataFrame（1小时K线）
            df_entry: 入场点分析用DataFrame（15分钟K线）
            
        Returns:
            包含分析结果的字典
        """
        # 检查数据有效性
        if df_trend.empty or df_entry.empty:
            logger.error("无效的市场数据，无法进行分析")
            return {
                'status': 'error',
                'message': '无效的市场数据'
            }
        
        # 分析趋势（使用1小时K线）
        trend = self.identify_trend(df_trend)
        
        # 识别支撑/阻力位（使用1小时K线）
        support_levels, resistance_levels = self.identify_support_resistance(df_trend)
        
        # 识别K线形态（使用15分钟K线，更快响应市场变化）
        pattern = self.identify_candlestick_pattern(df_entry)
        
        # 获取当前价格
        current_price = df_entry['close'].iloc[-1]
        
        # 检查价格是否接近支撑/阻力位
        near_support = self.is_near_support_resistance(current_price, support_levels)
        near_resistance = self.is_near_support_resistance(current_price, resistance_levels)
        
        # 生成交易信号
        signal = self._generate_signal(
            trend=trend,
            pattern=pattern,
            near_support=near_support,
            near_resistance=near_resistance,
            current_price=current_price,
            support_levels=support_levels,
            resistance_levels=resistance_levels
        )
        
        # 生成市场分析图表
        chart_filename = f'market_analysis_{df_entry.index[-1].strftime("%Y%m%d_%H%M%S")}.png'
        chart_path = self.plot_with_analysis(
            df=df_entry,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            trend=trend,
            pattern=pattern,
            filename=chart_filename
        )
        
        # 返回分析结果
        result = {
            'status': 'success',
            'timestamp': df_entry.index[-1],
            'trend': trend.name,
            'pattern': pattern,
            'support_levels': support_levels,
            'resistance_levels': resistance_levels,
            'current_price': current_price,
            'signal': signal,
            'chart_path': chart_path
        }
        
        logger.info(f"市场分析完成，趋势: {trend.name}, 形态: {pattern['description']}, 信号: {signal['action']}")
        
        return result
    
    def _generate_signal(self, trend: TrendType, pattern: Dict[str, Any], 
                        near_support: bool, near_resistance: bool,
                        current_price: float, support_levels: List[float], 
                        resistance_levels: List[float]) -> Dict[str, Any]:
        """
        根据市场分析生成交易信号
        
        Args:
            trend: 趋势类型
            pattern: K线形态信息
            near_support: 是否接近支撑位
            near_resistance: 是否接近阻力位
            current_price: 当前价格
            support_levels: 支撑位列表
            resistance_levels: 阻力位列表
            
        Returns:
            包含信号信息的字典
        """
        # 初始分数和方向
        buy_score = 0
        sell_score = 0
        
        # 基于趋势的评分
        if trend == TrendType.UPTREND:
            buy_score += self.signal_scoring['trend_weight']
        elif trend == TrendType.DOWNTREND:
            sell_score += self.signal_scoring['trend_weight']
        
        # 基于K线形态的评分
        pattern_signal = pattern.get('signal', 'HOLD')
        pattern_strength = pattern.get('strength', 0)
        
        if pattern_signal == 'BUY':
            buy_score += self.signal_scoring['pattern_weight'] * pattern_strength
        elif pattern_signal == 'SELL':
            sell_score += self.signal_scoring['pattern_weight'] * pattern_strength
        
        # 基于支撑/阻力位的评分
        if near_support:
            buy_score += self.signal_scoring['support_resistance_weight']
        if near_resistance:
            sell_score += self.signal_scoring['support_resistance_weight']
        
        # 计算信号强度和方向
        signal_direction = 'LONG' if buy_score > sell_score else 'SHORT' if sell_score > buy_score else 'HOLD'
        signal_strength = max(buy_score, sell_score)
        
        # 信号置信度（0-100）
        confidence = min(100, signal_strength)
        
        # 确定动作
        if confidence >= self.signal_scoring['minimum_score']:
            action = 'BUY' if signal_direction == 'LONG' else 'SELL' if signal_direction == 'SHORT' else 'HOLD'
        else:
            action = 'HOLD'
            signal_direction = 'NONE'
        
        # 计算止损和止盈价格
        stop_loss = None
        take_profit = None
        
        if action == 'BUY':
            # 多单止损：最近的支撑位以下
            nearest_support = max([s for s in support_levels if s < current_price], default=current_price * 0.97)
            stop_loss = nearest_support * 0.99  # 止损价略低于支撑位
            
            # 多单止盈：风险回报比计算或最近阻力位
            risk = current_price - stop_loss
            take_profit = current_price + (risk * self.signal_scoring['risk_reward_ratio'])
            
            # 验证止盈是否接近阻力位，如果是，设为略低于阻力位
            nearest_resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.03)
            if take_profit > nearest_resistance:
                take_profit = nearest_resistance * 0.99
        
        elif action == 'SELL':
            # 空单止损：最近的阻力位以上
            nearest_resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.03)
            stop_loss = nearest_resistance * 1.01  # 止损价略高于阻力位
            
            # 空单止盈：风险回报比计算或最近支撑位
            risk = stop_loss - current_price
            take_profit = current_price - (risk * self.signal_scoring['risk_reward_ratio'])
            
            # 验证止盈是否接近支撑位，如果是，设为略高于支撑位
            nearest_support = max([s for s in support_levels if s < current_price], default=current_price * 0.97)
            if take_profit < nearest_support:
                take_profit = nearest_support * 1.01
        
        # 生成理由解释
        reasoning = []
        if trend != TrendType.SIDEWAYS:
            reasoning.append(f"市场趋势: {trend.name}")
        if pattern['pattern'] != CandlePattern.NONE:
            reasoning.append(f"K线形态: {pattern['description']}")
        if near_support:
            reasoning.append(f"价格接近支撑位")
        if near_resistance:
            reasoning.append(f"价格接近阻力位")
        
        reasoning_str = "，".join(reasoning)
        
        return {
            'action': action,
            'direction': signal_direction,
            'confidence': confidence,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'reasoning': reasoning_str
        }


if __name__ == "__main__":
    # 测试代码，直接运行该模块时执行
    import sys
    import os
    
    # 添加项目根目录到路径
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from config import API_CONFIG, TRADING_CONFIG, ANALYSIS_CONFIG, SIGNAL_SCORING, PATHS
    from data.data_fetcher import DataFetcher
    
    # 测试配置
    test_config = {
        'API_CONFIG': API_CONFIG,
        'TRADING_CONFIG': TRADING_CONFIG,
        'ANALYSIS_CONFIG': ANALYSIS_CONFIG,
        'SIGNAL_SCORING': SIGNAL_SCORING,
        'PATHS': PATHS
    }
    
    # 初始化组件
    data_fetcher = DataFetcher(test_config)
    market_analyzer = MarketAnalyzer(test_config)
    
    try:
        # 获取测试数据
        df_1h = data_fetcher.get_latest_data(timeframe='1h', n_periods=100)
        df_15m = data_fetcher.get_latest_data(timeframe='15m', n_periods=100)
        
        if not df_1h.empty and not df_15m.empty:
            # 执行市场分析
            result = market_analyzer.analyze_market(df_1h, df_15m)
            
            # 打印分析结果
            print("市场分析结果:")
            print(f"趋势: {result['trend']}")
            print(f"K线形态: {result['pattern']['description']}")
            print(f"信号: {result['signal']['action']} ({result['signal']['confidence']}% 置信度)")
            if result['signal']['action'] != 'HOLD':
                print(f"方向: {result['signal']['direction']}")
                print(f"止损: {result['signal']['stop_loss']}")
                print(f"止盈: {result['signal']['take_profit']}")
            print(f"理由: {result['signal']['reasoning']}")
        else:
            print("无法获取测试数据")
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
