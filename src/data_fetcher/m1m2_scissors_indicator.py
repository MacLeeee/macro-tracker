"""
M1M2剪刀差与中证500 PE流动性指标
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
from typing import Dict, Any, Optional

from .base_fetcher import BaseFetcher
from ..database.db_manager import DatabaseManager


class M1M2ScissorsIndicator:
    """M1M2剪刀差与中证500 PE流动性指标"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
        # 数据源配置
        self.m1m2_indicator_key = "macro_china_m1m2"
        self.zz500_pe_indicator_key = "stock_zz500_pe"
        self.zz500_price_indicator_key = "stock_zz500_index"
        
        # 确保数据源配置存在
        self._ensure_source_indicators()
    
    def ensure_source_data(self) -> bool:
        """确保所有源数据都已获取"""
        try:
            # 直接使用AkShare获取数据
            from .akshare_fetcher import AkShareFetcher
            
            fetcher = AkShareFetcher()
            if not fetcher.is_available():
                logger.error("AkShare不可用")
                return False
            
            success_count = 0
            
            # 获取M1M2数据
            logger.info("获取M1M2货币供应量数据...")
            m1m2_data = fetcher.fetch_data_by_key(self.m1m2_indicator_key)
            if m1m2_data is not None and not m1m2_data.empty:
                self.db_manager.save_data(m1m2_data, self.m1m2_indicator_key)
                success_count += 1
                logger.info("M1M2数据保存成功")
            
            # 获取中证500 PE数据
            logger.info("获取中证500 PE数据...")
            pe_data = fetcher.fetch_data_by_key(self.zz500_pe_indicator_key)
            if pe_data is not None and not pe_data.empty:
                self.db_manager.save_data(pe_data, self.zz500_pe_indicator_key)
                success_count += 1
                logger.info("中证500 PE数据保存成功")
            
            # 获取中证500价格数据作为备用
            logger.info("获取中证500价格数据...")
            price_data = fetcher.fetch_data_by_key(self.zz500_price_indicator_key)
            if price_data is not None and not price_data.empty:
                self.db_manager.save_data(price_data, self.zz500_price_indicator_key)
                success_count += 1
                logger.info("中证500价格数据保存成功")
            
            return success_count >= 2  # 至少需要M1M2数据和一个估值数据
            
        except Exception as e:
            logger.error(f"源数据获取失败: {e}")
            return False
    
    def parse_time_period(self, time_str: str) -> Optional[datetime]:
        """解析时间字符串"""
        try:
            if pd.isna(time_str) or not time_str:
                return None
                
            time_str = str(time_str).strip()
            
            # 处理 "2025.7" 格式
            if '.' in time_str and len(time_str.split('.')) == 2:
                year, month = time_str.split('.')
                return datetime(int(year), int(month), 1)
            
            # 处理其他格式
            for fmt in ['%Y-%m', '%Y/%m', '%Y年%m月', '%Y年%m月份']:
                try:
                    return datetime.strptime(time_str, fmt)
                except:
                    continue
            
            logger.warning(f"无法解析时间格式: {time_str}")
            return None
            
        except Exception as e:
            logger.error(f"时间解析错误: {e}")
            return None
    
    def preprocess_m1m2_data(self, m1m2_data: pd.DataFrame) -> pd.DataFrame:
        """预处理M1M2数据"""
        try:
            data = m1m2_data.copy()
            
            # 处理时间列：优先使用标准化后的 date 列；否则解析 "统计时间"
            if 'date' in data.columns:
                data['date'] = pd.to_datetime(data['date'])
            elif '统计时间' in data.columns:
                data['date'] = data['统计时间'].apply(self.parse_time_period)
            else:
                logger.error("M1M2数据中未找到时间列（date/统计时间）")
                return pd.DataFrame()
            
            # 提取M1和M2增长率
            m1_growth_col = '货币(狭义货币M1)同比增长'
            m2_growth_col = '货币和准货币（广义货币M2）同比增长'
            
            if m1_growth_col not in data.columns or m2_growth_col not in data.columns:
                logger.error("M1M2数据中未找到增长率列")
                return pd.DataFrame()
            
            # 清理数据
            data = data.dropna(subset=['date', m1_growth_col, m2_growth_col])
            data['m1_growth'] = pd.to_numeric(data[m1_growth_col], errors='coerce')
            data['m2_growth'] = pd.to_numeric(data[m2_growth_col], errors='coerce')
            
            # 计算剪刀差
            data['m1m2_scissors'] = data['m1_growth'] - data['m2_growth']
            
            # 计算移动平均
            data['m1_growth_ma3'] = data['m1_growth'].rolling(3).mean()
            data['m2_growth_ma3'] = data['m2_growth'].rolling(3).mean()
            data['scissors_ma3'] = data['m1m2_scissors'].rolling(3).mean()
            
            # 选择需要的列
            result = data[['date', 'm1_growth', 'm2_growth', 'm1m2_scissors', 
                          'm1_growth_ma3', 'm2_growth_ma3', 'scissors_ma3']].copy()
            
            # 按日期排序
            result = result.sort_values('date')
            
            logger.info(f"M1M2数据预处理完成: {len(result)} 行, "
                       f"日期范围: {result['date'].min()} 到 {result['date'].max()}")
            
            return result
            
        except Exception as e:
            logger.error(f"M1M2数据预处理失败: {e}")
            return pd.DataFrame()
    
    def preprocess_zz500_pe_data(self, pe_data: pd.DataFrame) -> pd.DataFrame:
        """预处理中证500 PE数据"""
        try:
            data = pe_data.copy()
            
            if 'date' not in data.columns:
                if '日期' in data.columns:
                    data['date'] = pd.to_datetime(data['日期'])
                else:
                    logger.error("中证500 PE数据中未找到日期列")
                    return pd.DataFrame()
            else:
                data['date'] = pd.to_datetime(data['date'])
            
            # 提取PE数据
            if '滚动市盈率' in data.columns:
                data['pe_ratio'] = pd.to_numeric(data['滚动市盈率'], errors='coerce')
            else:
                logger.error("中证500数据中未找到滚动市盈率列")
                return pd.DataFrame()
            
            # 转换为月度数据
            data.set_index('date', inplace=True)
            monthly_data = data.resample('ME').last()
            monthly_data = monthly_data.reset_index()
            
            # 将月末日期转换为月初，以便与宏观数据对齐
            monthly_data['date'] = monthly_data['date'].dt.to_period('M').dt.start_time
            
            # 计算PE的移动平均和分位数
            monthly_data['pe_ma3'] = monthly_data['pe_ratio'].rolling(3).mean()
            monthly_data['pe_ma12'] = monthly_data['pe_ratio'].rolling(12).mean()
            
            # 计算PE历史分位数（基于过去3年数据）
            monthly_data['pe_percentile'] = monthly_data['pe_ratio'].rolling(36).rank(pct=True) * 100
            
            # 选择需要的列
            result = monthly_data[['date', 'pe_ratio', 'pe_ma3', 'pe_ma12', 'pe_percentile']].copy()
            result = result.dropna(subset=['pe_ratio'])
            
            logger.info(f"中证500 PE数据预处理完成: {len(result)} 行, "
                       f"日期范围: {result['date'].min()} 到 {result['date'].max()}")
            
            return result
            
        except Exception as e:
            logger.error(f"中证500 PE数据预处理失败: {e}")
            return pd.DataFrame()
    
    def preprocess_zz500_price_data(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """预处理中证500价格数据，构建PE代理指标"""
        try:
            data = price_data.copy()
            
            if 'date' not in data.columns:
                logger.error("中证500价格数据中未找到date列")
                return pd.DataFrame()
            
            data['date'] = pd.to_datetime(data['date'])
            
            if 'close' not in data.columns:
                logger.error("中证500价格数据中未找到close列")
                return pd.DataFrame()
            
            # 转换为月度数据
            data.set_index('date', inplace=True)
            monthly_data = data.resample('ME').last()
            monthly_data = monthly_data.reset_index()
            
            # 将月末日期转换为月初
            monthly_data['date'] = monthly_data['date'].dt.to_period('M').dt.start_time
            
            # 计算价格相对估值指标
            monthly_data['price_ma12'] = monthly_data['close'].rolling(12).mean()
            monthly_data['price_ma24'] = monthly_data['close'].rolling(24).mean()
            
            # 价格相对历史均值的比率（作为估值代理）
            monthly_data['valuation_proxy'] = monthly_data['close'] / monthly_data['price_ma24']
            
            # 价格历史分位数
            monthly_data['price_percentile'] = monthly_data['close'].rolling(36).rank(pct=True) * 100
            
            # 选择需要的列
            result = monthly_data[['date', 'close', 'valuation_proxy', 'price_percentile']].copy()
            result = result.dropna(subset=['close'])
            
            logger.info(f"中证500价格数据预处理完成: {len(result)} 行, "
                       f"日期范围: {result['date'].min()} 到 {result['date'].max()}")
            
            return result
            
        except Exception as e:
            logger.error(f"中证500价格数据预处理失败: {e}")
            return pd.DataFrame()
    
    def calculate_m1m2_scissors(self) -> pd.DataFrame:
        """计算M1M2剪刀差流动性指标"""
        try:
            # 获取M1M2数据
            m1m2_data = self.db_manager.load_data(self.m1m2_indicator_key)
            if m1m2_data is None or m1m2_data.empty:
                logger.error("M1M2数据为空")
                return pd.DataFrame()
            
            # 预处理M1M2数据
            m1m2_processed = self.preprocess_m1m2_data(m1m2_data)
            if m1m2_processed.empty:
                logger.error("M1M2数据预处理失败")
                return pd.DataFrame()
            
            # 估值数据：同时准备官方PE与价格估值代理
            pe_data = self.db_manager.load_data(self.zz500_pe_indicator_key)
            pe_processed = pd.DataFrame()
            if pe_data is not None and not pe_data.empty:
                pe_processed = self.preprocess_zz500_pe_data(pe_data)
            price_data = self.db_manager.load_data(self.zz500_price_indicator_key)
            price_processed = pd.DataFrame()
            if price_data is not None and not price_data.empty:
                price_processed = self.preprocess_zz500_price_data(price_data)

            # 选择估值序列：若PE覆盖到最近月份则用PE，否则用价格
            chosen_valuation = pd.DataFrame()
            if not price_processed.empty:
                chosen_valuation = price_processed.copy()
                logger.info("默认使用价格估值代理")
            if not pe_processed.empty:
                last_pe_date = pe_processed['date'].max()
                last_m_date = m1m2_processed['date'].max()
                # 若PE数据足够新（距最新M1M2不超过31天），则优先使用PE
                if pd.notna(last_pe_date) and pd.notna(last_m_date) and (last_m_date - last_pe_date).days <= 31:
                    chosen_valuation = pe_processed.copy()
                    logger.info("使用官方PE数据（覆盖至最近月份）")
                else:
                    logger.info("官方PE数据较旧，使用价格估值代理")

            # 合并数据
            if not chosen_valuation.empty:
                combined_data = pd.merge(m1m2_processed, chosen_valuation, on='date', how='outer')
                combined_data = combined_data.sort_values('date')

                # 仅对M1/M2相关列做前向填充，避免估值列被无限前填
                fill_cols = [c for c in ['m1_growth','m2_growth','m1m2_scissors','m1_growth_ma3','m2_growth_ma3','scissors_ma3'] if c in combined_data.columns]
                combined_data[fill_cols] = combined_data[fill_cols].ffill()

                logger.info(f"M1M2剪刀差指标计算完成: {len(combined_data)} 行")
                return combined_data
            else:
                logger.info(f"仅M1M2剪刀差指标计算完成: {len(m1m2_processed)} 行（无可用估值数据）")
                return m1m2_processed
            
        except Exception as e:
            logger.error(f"M1M2剪刀差指标计算失败: {e}")
            return pd.DataFrame()
    
    def _ensure_source_indicators(self):
        """确保源指标配置存在"""
        try:
            indicators_to_add = [
                {
                    "indicator_key": self.m1m2_indicator_key,
                    "name": "中国M1M2货币供应量",
                    "description": "中国M1和M2货币供应量及增长率数据",
                    "source": "akshare",
                    "table_name": self.m1m2_indicator_key
                },
                {
                    "indicator_key": self.zz500_pe_indicator_key,
                    "name": "中证500滚动市盈率",
                    "description": "中证500指数滚动市盈率估值数据",
                    "source": "akshare",
                    "table_name": self.zz500_pe_indicator_key
                },
                {
                    "indicator_key": self.zz500_price_indicator_key,
                    "name": "中证500指数价格",
                    "description": "中证500指数历史价格数据",
                    "source": "akshare",
                    "table_name": self.zz500_price_indicator_key
                }
            ]
            
            for indicator in indicators_to_add:
                try:
                    self.db_manager.register_indicator(
                        indicator_key=indicator["indicator_key"],
                        name=indicator["name"],
                        description=indicator["description"],
                        source=indicator["source"],
                        table_name=indicator["table_name"]
                    )
                    logger.info(f"注册指标: {indicator['indicator_key']}")
                except Exception as e:
                    logger.warning(f"注册指标失败 {indicator['indicator_key']}: {e}")
                    
        except Exception as e:
            logger.error(f"源指标配置失败: {e}")
