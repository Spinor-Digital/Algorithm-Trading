#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据获取模块，负责从交易所获取ETH价格和期权数据
"""

import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple

import pandas as pd
import numpy as np
import ccxt
import requests
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('data_fetcher')

# 加载环境变量
load_dotenv()

class DataFetcher:
    """
    数据获取器类，负责从交易所API获取数据
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化数据获取器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.api_config = config['API_CONFIG']
        self.trading_config = config['TRADING_CONFIG']
        self.database_dir = config['PATHS']['database_dir']
        
        # 确保数据目录存在
        os.makedirs(self.database_dir, exist_ok=True)
        
        # 初始化交易所API连接
        self._init_exchanges()
        
        logger.info("数据获取器初始化完成")
    
    def _init_exchanges(self):
        """初始化交易所API连接"""
        # 初始化Binance交易所API
        try:
            self.binance = ccxt.binance({
                'apiKey': self.api_config['binance_api_key'],
                'secret': self.api_config['binance_api_secret'],
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future'  # 使用期货API
                }
            })
            logger.info("Binance API连接初始化成功")
        except Exception as e:
            logger.warning(f"Binance API连接初始化失败: {str(e)}")
            self.binance = None
        
        # 初始化Deribit交易所API（用于期权数据）
        try:
            self.deribit = ccxt.deribit({
                'apiKey': self.api_config['deribit_api_key'],
                'secret': self.api_config['deribit_api_secret'],
                'enableRateLimit': True
            })
            logger.info("Deribit API连接初始化成功")
        except Exception as e:
            logger.warning(f"Deribit API连接初始化失败: {str(e)}")
            self.deribit = None
    
    def get_latest_data(self, timeframe: str = '1h', n_periods: int = 100) -> pd.DataFrame:
        """
        获取最新的OHLCV数据
        
        Args:
            timeframe: 时间框架，如'1h'、'15m'等
            n_periods: 获取的K线数量
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        try:
            symbol = self.trading_config['symbol']
            
            # 优先使用交易所API获取数据
            if self.binance:
                ohlcv = self.binance.fetch_ohlcv(symbol, timeframe, limit=n_periods)
                
                if ohlcv:
                    # 转换为DataFrame
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)
                    return df
            
            # 如果交易所API获取失败，尝试使用备用API
            return self._fetch_data_from_backup_api(symbol, timeframe, n_periods)
                
        except Exception as e:
            logger.error(f"获取最新数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def _fetch_data_from_backup_api(self, symbol: str, timeframe: str, n_periods: int) -> pd.DataFrame:
        """
        从备用API获取数据
        
        Args:
            symbol: 交易对名称
            timeframe: 时间框架
            n_periods: K线数量
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        try:
            # 备用API: CryptoCompare
            base, quote = symbol.split('/')
            
            # 转换timeframe格式
            if timeframe.endswith('m'):
                tf_minutes = int(timeframe[:-1])
            elif timeframe.endswith('h'):
                tf_minutes = int(timeframe[:-1]) * 60
            elif timeframe.endswith('d'):
                tf_minutes = int(timeframe[:-1]) * 1440
            else:
                tf_minutes = 60  # 默认为1小时
            
            # 构建请求URL
            url = f"https://min-api.cryptocompare.com/data/v2/histominute"
            params = {
                'fsym': base,
                'tsym': quote,
                'limit': min(n_periods * tf_minutes, 2000),  # API限制
                'aggregate': tf_minutes
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data['Response'] == 'Success':
                df = pd.DataFrame(data['Data']['Data'])
                df['timestamp'] = pd.to_datetime(df['time'], unit='s')
                df = df.rename(columns={
                    'time': 'time',
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'volumefrom': 'volume'
                })
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                df.set_index('timestamp', inplace=True)
                
                # 取最近的n_periods个周期
                return df.iloc[-n_periods:]
            else:
                logger.error(f"备用API返回错误: {data['Message']}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"从备用API获取数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def fetch_historical_data(self, timeframe: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        获取历史OHLCV数据
        
        Args:
            timeframe: 时间框架
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        try:
            symbol = self.trading_config['symbol']
            
            # 计算需要获取的数据点数量
            time_diff = end_date - start_date
            
            if timeframe.endswith('m'):
                minutes = int(timeframe[:-1])
                n_periods = int(time_diff.total_seconds() / 60 / minutes) + 1
            elif timeframe.endswith('h'):
                hours = int(timeframe[:-1])
                n_periods = int(time_diff.total_seconds() / 3600 / hours) + 1
            elif timeframe.endswith('d'):
                days = int(timeframe[:-1])
                n_periods = int(time_diff.total_seconds() / 86400 / days) + 1
            else:
                n_periods = 1000  # 默认值
            
            # CCXT的限制，单次请求最多获取1000条数据
            max_periods_per_request = 1000
            
            # 如果需要获取的数据超过限制，则分批获取
            if n_periods > max_periods_per_request:
                all_data = []
                current_date = start_date
                
                while current_date < end_date:
                    # 计算当前批次的结束日期
                    next_date = current_date + timedelta(days=max_periods_per_request // 24)
                    if next_date > end_date:
                        next_date = end_date
                    
                    # 获取当前批次的数据
                    batch_data = self._fetch_historical_batch(symbol, timeframe, current_date, next_date)
                    if not batch_data.empty:
                        all_data.append(batch_data)
                    
                    # 更新下一批次的开始日期
                    current_date = next_date
                    
                    # 避免API限制
                    time.sleep(1)
                
                # 合并所有批次的数据
                if all_data:
                    df = pd.concat(all_data)
                    df = df[~df.index.duplicated(keep='first')]  # 去除可能的重复数据
                    df.sort_index(inplace=True)
                    return df
                else:
                    return pd.DataFrame()
            else:
                # 直接获取数据
                return self._fetch_historical_batch(symbol, timeframe, start_date, end_date)
                
        except Exception as e:
            logger.error(f"获取历史数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def _fetch_historical_batch(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        获取一批历史数据
        
        Args:
            symbol: 交易对
            timeframe: 时间框架
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        try:
            # 转换日期为时间戳（毫秒）
            since = int(start_date.timestamp() * 1000)
            
            if self.binance:
                ohlcv = self.binance.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                
                if ohlcv:
                    # 转换为DataFrame
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)
                    
                    # 筛选在时间范围内的数据
                    mask = (df.index >= start_date) & (df.index <= end_date)
                    return df.loc[mask]
            
            # 如果交易所API获取失败，尝试使用备用API
            return self._fetch_historical_from_backup(symbol, timeframe, start_date, end_date)
                
        except Exception as e:
            logger.error(f"获取历史数据批次时出错: {str(e)}")
            return pd.DataFrame()
    
    def _fetch_historical_from_backup(self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        从备用API获取历史数据
        
        Args:
            symbol: 交易对
            timeframe: 时间框架
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        try:
            # 备用API: CryptoCompare
            base, quote = symbol.split('/')
            
            # 转换timeframe格式
            if timeframe.endswith('m'):
                tf_minutes = int(timeframe[:-1])
                url = "https://min-api.cryptocompare.com/data/v2/histominute"
            elif timeframe.endswith('h'):
                tf_minutes = int(timeframe[:-1]) * 60
                url = "https://min-api.cryptocompare.com/data/v2/histohour"
            elif timeframe.endswith('d'):
                tf_minutes = int(timeframe[:-1]) * 1440
                url = "https://min-api.cryptocompare.com/data/v2/histoday"
            else:
                tf_minutes = 60
                url = "https://min-api.cryptocompare.com/data/v2/histohour"
            
            # 计算需要的数据点数量
            time_diff = end_date - start_date
            n_periods = int(time_diff.total_seconds() / 60 / tf_minutes) + 1
            
            # 构建请求
            params = {
                'fsym': base,
                'tsym': quote,
                'limit': min(n_periods, 2000),  # API限制
                'toTs': int(end_date.timestamp())
            }
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data['Response'] == 'Success':
                df = pd.DataFrame(data['Data']['Data'])
                df['timestamp'] = pd.to_datetime(df['time'], unit='s')
                df = df.rename(columns={
                    'time': 'time',
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'volumefrom': 'volume'
                })
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                df.set_index('timestamp', inplace=True)
                
                # 筛选在时间范围内的数据
                mask = (df.index >= start_date) & (df.index <= end_date)
                return df.loc[mask]
            else:
                logger.error(f"备用API返回错误: {data['Message']}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"从备用API获取历史数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def fetch_current_price(self) -> float:
        """
        获取当前价格
        
        Returns:
            当前价格
        """
        try:
            symbol = self.trading_config['symbol']
            
            if self.binance:
                ticker = self.binance.fetch_ticker(symbol)
                return ticker['last']
            
            # 备用方法
            base, quote = symbol.split('/')
            url = f"https://min-api.cryptocompare.com/data/price?fsym={base}&tsyms={quote}"
            response = requests.get(url)
            data = response.json()
            
            if quote in data:
                return float(data[quote])
            else:
                logger.error("无法获取当前价格")
                return 0.0
                
        except Exception as e:
            logger.error(f"获取当前价格时出错: {str(e)}")
            return 0.0
    
    def fetch_eth_options(self, expiry_days: int = 7) -> pd.DataFrame:
        """
        获取ETH期权合约数据
        
        Args:
            expiry_days: 到期天数
            
        Returns:
            包含期权数据的DataFrame
        """
        try:
            if self.deribit:
                # 获取可用的期权合约
                instruments = self.deribit.fetch_markets()
                
                # 过滤ETH期权合约
                eth_options = [
                    inst for inst in instruments 
                    if inst['type'] == 'option' and 'ETH' in inst['id']
                ]
                
                # 计算目标到期日期
                target_expiry = datetime.now() + timedelta(days=expiry_days)
                target_expiry_date = target_expiry.strftime('%Y-%m-%d')
                
                # 过滤出接近目标到期日的合约
                filtered_options = []
                for option in eth_options:
                    option_expiry = datetime.strptime(option['expiry'], '%Y-%m-%d %H:%M:%S')
                    days_to_expiry = (option_expiry - datetime.now()).days
                    
                    if 0 <= days_to_expiry <= expiry_days + 3:  # 允许一些灵活性
                        option_data = {
                            'symbol': option['id'],
                            'strike': option['strike'],
                            'option_type': 'call' if option['option'] == 'call' else 'put',
                            'expiry': option_expiry,
                            'days_to_expiry': days_to_expiry
                        }
                        filtered_options.append(option_data)
                
                if not filtered_options:
                    logger.warning(f"未找到接近{expiry_days}天到期的ETH期权合约")
                    return pd.DataFrame()
                
                # 获取合约的详细信息（价格、隐含波动率等）
                for option in filtered_options:
                    try:
                        ticker = self.deribit.fetch_ticker(option['symbol'])
                        option['bid'] = ticker['bid'] if ticker['bid'] else 0
                        option['ask'] = ticker['ask'] if ticker['ask'] else 0
                        option['last'] = ticker['last'] if ticker['last'] else 0
                        option['volume'] = ticker['volume'] if ticker['volume'] else 0
                        option['iv'] = ticker.get('info', {}).get('impliedVolatility', 0)
                        option['delta'] = ticker.get('info', {}).get('delta', 0)
                        option['gamma'] = ticker.get('info', {}).get('gamma', 0)
                        option['theta'] = ticker.get('info', {}).get('theta', 0)
                        option['vega'] = ticker.get('info', {}).get('vega', 0)
                    except Exception as e:
                        logger.error(f"获取合约 {option['symbol']} 的详细信息时出错: {str(e)}")
                
                # 转换为DataFrame
                df = pd.DataFrame(filtered_options)
                
                # 计算中间价格
                df['mid_price'] = (df['bid'] + df['ask']) / 2
                
                return df
            
            # 如果没有Deribit API访问，使用模拟数据
            return self._generate_mock_options_data(expiry_days)
                
        except Exception as e:
            logger.error(f"获取ETH期权数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def _generate_mock_options_data(self, expiry_days: int) -> pd.DataFrame:
        """
        生成模拟的期权数据（当真实API不可用时）
        
        Args:
            expiry_days: 到期天数
            
        Returns:
            包含模拟期权数据的DataFrame
        """
        try:
            # 获取当前ETH价格
            current_price = self.fetch_current_price()
            if current_price <= 0:
                current_price = 3000  # 假设的价格
            
            # 计算到期日
            expiry_date = datetime.now() + timedelta(days=expiry_days)
            
            # 生成不同行权价的期权
            strikes = [
                current_price * (1 - 0.2),
                current_price * (1 - 0.1),
                current_price * (1 - 0.05),
                current_price,
                current_price * (1 + 0.05),
                current_price * (1 + 0.1),
                current_price * (1 + 0.2)
            ]
            
            # 模拟数据
            options_data = []
            
            for strike in strikes:
                # 计算看涨期权数据
                call_delta = max(0, min(1, (current_price / strike - 0.9) * 2))
                call_price = max(0.001, current_price * 0.05 * call_delta)
                
                call_option = {
                    'symbol': f'ETH-{expiry_date.strftime("%d%b%y")}-{strike}-C',
                    'strike': strike,
                    'option_type': 'call',
                    'expiry': expiry_date,
                    'days_to_expiry': expiry_days,
                    'bid': call_price * 0.95,
                    'ask': call_price * 1.05,
                    'last': call_price,
                    'volume': np.random.randint(10, 100),
                    'iv': 0.6 + np.random.normal(0, 0.1),
                    'delta': call_delta,
                    'gamma': 0.01 + np.random.normal(0, 0.005),
                    'theta': -0.01 - np.random.normal(0, 0.005),
                    'vega': 0.1 + np.random.normal(0, 0.05)
                }
                
                # 计算看跌期权数据
                put_delta = -max(0, min(1, (strike / current_price - 0.9) * 2))
                put_price = max(0.001, current_price * 0.05 * abs(put_delta))
                
                put_option = {
                    'symbol': f'ETH-{expiry_date.strftime("%d%b%y")}-{strike}-P',
                    'strike': strike,
                    'option_type': 'put',
                    'expiry': expiry_date,
                    'days_to_expiry': expiry_days,
                    'bid': put_price * 0.95,
                    'ask': put_price * 1.05,
                    'last': put_price,
                    'volume': np.random.randint(10, 100),
                    'iv': 0.7 + np.random.normal(0, 0.1),
                    'delta': put_delta,
                    'gamma': 0.01 + np.random.normal(0, 0.005),
                    'theta': -0.01 - np.random.normal(0, 0.005),
                    'vega': 0.1 + np.random.normal(0, 0.05)
                }
                
                options_data.append(call_option)
                options_data.append(put_option)
            
            # 转换为DataFrame
            df = pd.DataFrame(options_data)
            
            # 计算中间价格
            df['mid_price'] = (df['bid'] + df['ask']) / 2
            
            logger.info("生成了模拟期权数据（真实API不可用）")
            return df
                
        except Exception as e:
            logger.error(f"生成模拟期权数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def save_data(self, df: pd.DataFrame, filename: str):
        """
        保存数据到文件
        
        Args:
            df: 要保存的DataFrame
            filename: 文件名
        """
        try:
            filepath = os.path.join(self.database_dir, filename)
            df.to_csv(filepath)
            logger.info(f"数据已保存到 {filepath}")
        except Exception as e:
            logger.error(f"保存数据时出错: {str(e)}")
    
    def load_data(self, filename: str) -> pd.DataFrame:
        """
        从文件加载数据
        
        Args:
            filename: 文件名
            
        Returns:
            加载的DataFrame
        """
        try:
            filepath = os.path.join(self.database_dir, filename)
            if os.path.exists(filepath):
                df = pd.read_csv(filepath, index_col=0, parse_dates=True)
                logger.info(f"数据已从 {filepath} 加载")
                return df
            else:
                logger.warning(f"数据文件 {filepath} 不存在")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"加载数据时出错: {str(e)}")
            return pd.DataFrame()


if __name__ == "__main__":
    # 测试代码，直接运行该模块时执行
    import sys
    import os
    
    # 添加项目根目录到路径
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from config import API_CONFIG, TRADING_CONFIG, PATHS
    
    # 测试配置
    test_config = {
        'API_CONFIG': API_CONFIG,
        'TRADING_CONFIG': TRADING_CONFIG,
        'PATHS': PATHS
    }
    
    # 初始化数据获取器
    data_fetcher = DataFetcher(test_config)
    
    try:
        # 测试获取最新数据
        df_1h = data_fetcher.get_latest_data(timeframe='1h', n_periods=10)
        print("1小时K线数据:")
        print(df_1h)
        
        # 测试获取当前价格
        price = data_fetcher.fetch_current_price()
        print(f"当前ETH价格: {price}")
        
        # 测试获取期权数据
        options = data_fetcher.fetch_eth_options(expiry_days=7)
        print("ETH期权数据:")
        print(options.head())
        
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}") 