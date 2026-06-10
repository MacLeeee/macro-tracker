"""
社融/GDP与沪深300指标计算模块
"""

import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from loguru import logger
from typing import Dict, Any, Optional, Tuple

from .base_fetcher import BaseFetcher
from ..database.db_manager import DatabaseManager


class SocialFinancingIndicator:
    """社融/GDP与沪深300指标"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
        # 数据源配置
        self.social_financing_key = "macro_china_new_financial_credit"
        self.gdp_key = "macro_china_gdp"
        self.hs300_key = "stock_hs300_index"
        
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
            
            # 获取社融数据
            logger.info("获取社融数据...")
            sf_data = fetcher.fetch_data_by_key(self.social_financing_key)
            if sf_data is not None and not sf_data.empty:
                self.db_manager.save_data(sf_data, self.social_financing_key)
                success_count += 1
                logger.info("社融数据保存成功")
            
            # 获取GDP数据
            logger.info("获取GDP数据...")
            gdp_data = fetcher.fetch_data_by_key(self.gdp_key)
            if gdp_data is not None and not gdp_data.empty:
                self.db_manager.save_data(gdp_data, self.gdp_key)
                success_count += 1
                logger.info("GDP数据保存成功")
            
            # 获取沪深300数据
            logger.info("获取沪深300数据...")
            hs300_data = fetcher.fetch_data_by_key(self.hs300_key)
            if hs300_data is not None and not hs300_data.empty:
                self.db_manager.save_data(hs300_data, self.hs300_key)
                success_count += 1
                logger.info("沪深300数据保存成功")
            
            return success_count >= 3  # 需要所有三个数据源
            
        except Exception as e:
            logger.error(f"源数据获取失败: {e}")
            return False
    
    def parse_quarter(self, quarter_str: str) -> Optional[datetime]:
        """解析季度字符串"""
        try:
            if pd.isna(quarter_str) or not quarter_str:
                return None
                
            quarter_str = str(quarter_str).strip()
            
            # 处理"2025年第1-4季度"格式
            if "年第" in quarter_str and "季度" in quarter_str:
                parts = quarter_str.split("年第")
                year = int(parts[0])
                
                quarter_part = parts[1].split("季度")[0]
                
                # 处理"1-4"格式
                if "-" in quarter_part:
                    quarter_range = quarter_part.split("-")
                    end_quarter = int(quarter_range[1])
                    # 使用最后一个季度的结束月份
                    month = end_quarter * 3
                else:
                    # 单季度，如"第1季度"
                    quarter = int(quarter_part)
                    month = quarter * 3
                
                return datetime(year, month, 1)
            
            logger.warning(f"无法解析季度格式: {quarter_str}")
            return None
            
        except Exception as e:
            logger.error(f"季度解析错误: {e}")
            return None
    
    def parse_month(self, month_str: str) -> Optional[datetime]:
        """解析月份字符串"""
        try:
            if pd.isna(month_str) or not month_str:
                return None
                
            month_str = str(month_str).strip()
            
            # 处理"2025年07月份"格式
            if "年" in month_str and "月" in month_str:
                parts = month_str.split("年")
                year = int(parts[0])
                
                month_part = parts[1].split("月")[0]
                month = int(month_part)
                
                return datetime(year, month, 1)
            
            logger.warning(f"无法解析月份格式: {month_str}")
            return None
            
        except Exception as e:
            logger.error(f"月份解析错误: {e}")
            return None
    
    def preprocess_social_financing(self, sf_data: pd.DataFrame) -> pd.DataFrame:
        """预处理社融数据"""
        try:
            data = sf_data.copy()
            
            # 转换月份
            if '月份' in data.columns:
                data['date'] = data['月份'].apply(self.parse_month)
            else:
                logger.error("社融数据中未找到月份列")
                return pd.DataFrame()
            
            # 提取社融规模数据 - 使用'当月'或'累计'列
            if '当月' in data.columns:
                data['social_financing'] = pd.to_numeric(data['当月'], errors='coerce')
                logger.info("使用'当月'列作为社融数据")
            elif '累计' in data.columns:
                data['social_financing'] = pd.to_numeric(data['累计'], errors='coerce')
                logger.info("使用'累计'列作为社融数据")
            else:
                logger.error("社融数据中未找到当月或累计列")
                return pd.DataFrame()
            
            # 按日期排序
            data = data.dropna(subset=['date', 'social_financing'])
            data = data.sort_values('date')
            
            # 如果使用的是当月数据，计算累计社融规模（12个月滚动总和）
            if '当月' in data.columns:
                data['social_financing_cumulative'] = data['social_financing'].rolling(12).sum()
            else:
                # 如果使用的是累计数据，直接使用
                data['social_financing_cumulative'] = data['social_financing']
            
            # 计算同比增长率
            if '当月-同比增长' in data.columns:
                data['social_financing_yoy'] = pd.to_numeric(data['当月-同比增长'], errors='coerce')
            elif '累计-同比增长' in data.columns:
                data['social_financing_yoy'] = pd.to_numeric(data['累计-同比增长'], errors='coerce')
            else:
                data['social_financing_yoy'] = data['social_financing'].pct_change(12) * 100
            
            # 计算移动平均
            data['social_financing_ma6'] = data['social_financing'].rolling(6).mean()
            data['social_financing_yoy_ma6'] = data['social_financing_yoy'].rolling(6).mean()
            
            # 选择需要的列
            result = data[['date', 'social_financing', 'social_financing_cumulative', 
                          'social_financing_yoy', 'social_financing_ma6', 
                          'social_financing_yoy_ma6']].copy()
            
            logger.info(f"社融数据预处理完成: {len(result)} 行, "
                       f"日期范围: {result['date'].min()} 到 {result['date'].max()}")
            
            return result
            
        except Exception as e:
            logger.error(f"社融数据预处理失败: {e}")
            return pd.DataFrame()
    
    def preprocess_gdp(self, gdp_data: pd.DataFrame) -> pd.DataFrame:
        """预处理GDP数据"""
        try:
            data = gdp_data.copy()
            
            # 转换季度
            if '季度' in data.columns:
                data['date'] = data['季度'].apply(self.parse_quarter)
            else:
                logger.error("GDP数据中未找到季度列")
                return pd.DataFrame()
            
            # 提取GDP数据
            if '国内生产总值-绝对值' in data.columns:
                data['gdp'] = pd.to_numeric(data['国内生产总值-绝对值'], errors='coerce')
            else:
                logger.error("GDP数据中未找到国内生产总值-绝对值列")
                return pd.DataFrame()
            
            # 提取GDP同比增长率
            if '国内生产总值-同比增长' in data.columns:
                data['gdp_yoy'] = pd.to_numeric(data['国内生产总值-同比增长'], errors='coerce')
            
            # 按日期排序并选择需要的列
            data = data.dropna(subset=['date', 'gdp'])
            data = data.sort_values('date')
            
            # 选择需要的列
            result = data[['date', 'gdp', 'gdp_yoy']].copy()
            
            logger.info(f"GDP数据预处理完成: {len(result)} 行, "
                       f"日期范围: {result['date'].min()} 到 {result['date'].max()}")
            
            return result
            
        except Exception as e:
            logger.error(f"GDP数据预处理失败: {e}")
            return pd.DataFrame()
    
    def preprocess_hs300(self, hs300_data: pd.DataFrame) -> pd.DataFrame:
        """预处理沪深300指数数据"""
        try:
            data = hs300_data.copy()
            
            if 'date' not in data.columns:
                logger.error("沪深300数据中未找到date列")
                return pd.DataFrame()
            
            data['date'] = pd.to_datetime(data['date'])
            
            if 'close' not in data.columns:
                logger.error("沪深300数据中未找到close列")
                return pd.DataFrame()
            
            # 转换为月度数据（对齐到月初）
            data.set_index('date', inplace=True)
            # 使用月末聚合后，将日期统一映射到该月月初，便于与宏观月度数据对齐
            monthly_data = data.resample('ME').last()
            monthly_data = monthly_data.reset_index()
            # 将月末日期统一转换为当月月初，以便和宏观数据对齐
            monthly_data['date'] = monthly_data['date'].dt.to_period('M').dt.start_time
            
            # 计算收益率
            monthly_data['hs300_return'] = monthly_data['close'].pct_change() * 100
            monthly_data['hs300_yoy_return'] = monthly_data['close'].pct_change(12) * 100
            
            # 计算移动平均
            monthly_data['hs300_ma6'] = monthly_data['close'].rolling(6).mean()
            monthly_data['hs300_yoy_ma6'] = monthly_data['hs300_yoy_return'].rolling(6).mean()
            
            # 选择需要的列
            result = monthly_data[['date', 'close', 'hs300_return', 'hs300_yoy_return', 
                                  'hs300_ma6', 'hs300_yoy_ma6']].copy()
            
            logger.info(f"沪深300数据预处理完成: {len(result)} 行, "
                       f"日期范围: {result['date'].min()} 到 {result['date'].max()}")
            
            return result
            
        except Exception as e:
            logger.error(f"沪深300数据预处理失败: {e}")
            return pd.DataFrame()
    
    def _interpolate_quarterly_to_monthly(self, quarterly_data: pd.DataFrame) -> pd.DataFrame:
        """将季度数据插值为月度数据"""
        try:
            if quarterly_data.empty:
                return pd.DataFrame()
            
            # 确保日期列是datetime类型
            quarterly_data['date'] = pd.to_datetime(quarterly_data['date'])
            
            # 设置日期为索引
            data = quarterly_data.set_index('date')
            
            # 创建月度日期范围
            min_date = data.index.min()
            max_date = data.index.max()
            
            # 创建月度日期序列
            monthly_dates = pd.date_range(start=min_date, end=max_date, freq='MS')
            monthly_df = pd.DataFrame(index=monthly_dates)
            
            # 合并季度数据
            merged = monthly_df.join(data)
            
            # 线性插值填充缺失值
            interpolated = merged.interpolate(method='linear')
            
            # 重置索引
            interpolated = interpolated.reset_index()
            interpolated = interpolated.rename(columns={'index': 'date'})
            
            return interpolated
            
        except Exception as e:
            logger.error(f"季度数据插值失败: {e}")
            return quarterly_data
    
    def calculate_social_financing_gdp(self) -> Tuple[pd.DataFrame, str]:
        """计算社融/GDP指标"""
        try:
            # 获取社融数据 - 直接使用SQL查询，不依赖date列
            try:
                conn = sqlite3.connect(str(self.db_manager.db_path))
                sf_data = pd.read_sql(f"SELECT * FROM {self.social_financing_key}", conn)
                conn.close()
                if sf_data.empty:
                    logger.error("社融数据为空")
                    return pd.DataFrame(), "社融数据缺失"
            except Exception as e:
                logger.error(f"直接加载社融数据失败: {e}")
                return pd.DataFrame(), f"社融数据加载失败: {e}"
            
            # 预处理社融数据
            sf_processed = self.preprocess_social_financing(sf_data)
            if sf_processed.empty:
                logger.error("社融数据预处理失败")
                return pd.DataFrame(), "社融数据处理失败"
            
            # 获取GDP数据 - 直接使用SQL查询，不依赖date列
            try:
                conn = sqlite3.connect(str(self.db_manager.db_path))
                gdp_data = pd.read_sql(f"SELECT * FROM {self.gdp_key}", conn)
                conn.close()
                if gdp_data.empty:
                    logger.error("GDP数据为空")
                    return pd.DataFrame(), "GDP数据缺失"
            except Exception as e:
                logger.error(f"直接加载GDP数据失败: {e}")
                return pd.DataFrame(), f"GDP数据加载失败: {e}"
            
            # 预处理GDP数据
            gdp_processed = self.preprocess_gdp(gdp_data)
            if gdp_processed.empty:
                logger.error("GDP数据预处理失败")
                return pd.DataFrame(), "GDP数据处理失败"
            
            # 将季度GDP数据插值为月度数据
            gdp_monthly = self._interpolate_quarterly_to_monthly(gdp_processed)
            
            # 获取沪深300数据
            hs300_data = self.db_manager.load_data(self.hs300_key)
            if hs300_data is None or hs300_data.empty:
                logger.warning("沪深300数据为空，仅计算社融/GDP")
                hs300_processed = pd.DataFrame()
            else:
                # 预处理沪深300数据
                hs300_processed = self.preprocess_hs300(hs300_data)
            
            # 合并社融和GDP数据
            merged_data = pd.merge(sf_processed, gdp_monthly, on='date', how='inner')
            
            if merged_data.empty:
                logger.error("社融和GDP数据无法合并，可能日期不匹配")
                return pd.DataFrame(), "社融和GDP数据无法合并"
            
            # 计算社融/GDP比率（使用同比增长值）
            merged_data['social_financing_gdp_ratio'] = merged_data['social_financing_yoy']
            
            # 计算移动平均
            merged_data['sf_gdp_ratio_ma6'] = merged_data['social_financing_gdp_ratio'].rolling(6).mean()
            
            # 如果有沪深300数据，合并
            if not hs300_processed.empty:
                final_data = pd.merge(merged_data, hs300_processed, on='date', how='left')
                message = "社融/GDP与沪深300指数计算完成"
            else:
                final_data = merged_data
                message = "仅社融/GDP计算完成，沪深300数据缺失"
            
            logger.info(f"{message}: {len(final_data)} 行")
            return final_data, message
            
        except Exception as e:
            logger.error(f"社融/GDP指标计算失败: {e}")
            return pd.DataFrame(), f"计算失败: {e}"
    
    def update_and_calculate(self, force_update: bool = False) -> Optional[pd.DataFrame]:
        """更新数据并计算指标"""
        try:
            if force_update:
                # 强制更新数据
                success = self.ensure_source_data()
                if not success:
                    logger.warning("数据更新失败，尝试使用现有数据计算")
            
            # 计算指标
            result, _ = self.calculate_social_financing_gdp()
            return result
            
        except Exception as e:
            logger.error(f"更新和计算失败: {e}")
            return None
    
    def get_latest_values(self, data: pd.DataFrame) -> Dict[str, Any]:
        """获取最新值"""
        if data.empty:
            return {}
        
        latest = data.iloc[-1]
        
        result = {
            'date': latest['date'].strftime('%Y-%m-%d'),
            'social_financing': latest.get('social_financing'),
            'social_financing_yoy': latest.get('social_financing_yoy'),
            'gdp': latest.get('gdp'),
            'social_financing_gdp_ratio': latest.get('social_financing_gdp_ratio'),
        }
        
        # 添加沪深300数据（如果有）
        if 'close' in latest:
            result['hs300_index'] = latest.get('close')
        
        # 计算变化率
        if len(data) > 1:
            prev = data.iloc[-2]
            result['change_1m'] = latest.get('social_financing_gdp_ratio') - prev.get('social_financing_gdp_ratio')
        
        return result
    
    def _ensure_source_indicators(self):
        """确保源指标配置存在"""
        try:
            indicators_to_add = [
                {
                    "indicator_key": self.social_financing_key,
                    "name": "社会融资规模",
                    "description": "社会融资规模增量统计数据",
                    "source": "akshare",
                    "table_name": self.social_financing_key
                },
                {
                    "indicator_key": self.gdp_key,
                    "name": "国内生产总值",
                    "description": "中国季度GDP数据",
                    "source": "akshare",
                    "table_name": self.gdp_key
                },
                {
                    "indicator_key": self.hs300_key,
                    "name": "沪深300指数",
                    "description": "沪深300指数历史价格数据",
                    "source": "akshare",
                    "table_name": self.hs300_key
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


# 全局实例
social_financing_indicator = None

def init_social_financing_indicator(db_manager: DatabaseManager):
    """初始化社融/GDP指标"""
    global social_financing_indicator
    social_financing_indicator = SocialFinancingIndicator(db_manager)
    return social_financing_indicator
