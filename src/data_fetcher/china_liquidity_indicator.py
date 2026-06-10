"""
中国超额流动性指标计算器
超额流动性 = M2同比增长率 - 工业增加值增长率
"""
import pandas as pd
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime
import re

from .composite_indicator import CompositeIndicator
from .data_manager import data_manager

class ChinaLiquidityIndicator(CompositeIndicator):
    """中国超额流动性指标 (M2同比增长率 - 工业增加值增长率)"""
    
    def __init__(self):
        super().__init__(
            name="中国超额流动性指标",
            description="中国M2同比增长率减去工业增加值增长率，反映中国经济超额流动性状况"
        )
        self.m2_indicator_key = "akshare_china_m2"
        self.industrial_indicator_key = "akshare_china_industrial"
        self.hs300_indicator_key = "akshare_hs300_index"
        self.zz2000_indicator_key = "akshare_zz2000_index"
    
    def ensure_source_data(self, force_update: bool = False) -> Dict[str, pd.DataFrame]:
        """确保源数据可用"""
        source_data = {}
        
        # 获取M2数据
        logger.info("获取中国M2货币供应量数据...")
        m2_data = data_manager.fetch_indicator_data(self.m2_indicator_key, force_update)
        if m2_data is not None and not m2_data.empty:
            source_data['m2'] = m2_data
            logger.info(f"M2数据: {len(m2_data)} 行")
        else:
            logger.error("M2数据获取失败")
        
        # 获取工业增加值数据
        logger.info("获取中国工业增加值数据...")
        industrial_data = data_manager.fetch_indicator_data(self.industrial_indicator_key, force_update)
        if industrial_data is not None and not industrial_data.empty:
            source_data['industrial'] = industrial_data
            logger.info(f"工业增加值数据: {len(industrial_data)} 行")
        else:
            logger.error("工业增加值数据获取失败")
        
        # 获取沪深300指数数据
        logger.info("获取沪深300指数数据...")
        hs300_data = data_manager.fetch_indicator_data(self.hs300_indicator_key, force_update)
        if hs300_data is not None and not hs300_data.empty:
            source_data['hs300'] = hs300_data
            logger.info(f"沪深300数据: {len(hs300_data)} 行")
        else:
            logger.warning("沪深300指数数据获取失败")
        
        # 获取中证2000指数数据
        logger.info("获取中证2000指数数据...")
        zz2000_data = data_manager.fetch_indicator_data(self.zz2000_indicator_key, force_update)
        if zz2000_data is not None and not zz2000_data.empty:
            source_data['zz2000'] = zz2000_data
            logger.info(f"中证2000数据: {len(zz2000_data)} 行")
        else:
            logger.warning("中证2000指数数据获取失败")
        
        return source_data
    
    def parse_time_period(self, time_str: str) -> Optional[pd.Timestamp]:
        """解析时间字符串，支持多种格式"""
        if pd.isna(time_str) or time_str is None:
            return None
        
        time_str = str(time_str).strip()
        
        try:
            # 处理 "2020.8" 格式
            if '.' in time_str:
                year, month = time_str.split('.')
                return pd.Timestamp(f"{year}-{month.zfill(2)}-01")
            
            # 处理 "2020年8月" 格式
            if '年' in time_str and '月' in time_str:
                year_match = re.search(r'(\d{4})年', time_str)
                month_match = re.search(r'(\d{1,2})月', time_str)
                if year_match and month_match:
                    year = year_match.group(1)
                    month = month_match.group(1)
                    return pd.Timestamp(f"{year}-{month.zfill(2)}-01")
            
            # 处理 "202008" 格式
            if len(time_str) == 6 and time_str.isdigit():
                year = time_str[:4]
                month = time_str[4:6]
                return pd.Timestamp(f"{year}-{month}-01")
            
            # 尝试直接解析
            return pd.to_datetime(time_str)
            
        except Exception as e:
            logger.debug(f"解析时间字符串失败: {time_str}, 错误: {e}")
            return None
    
    def preprocess_m2_data(self, m2_data: pd.DataFrame) -> pd.DataFrame:
        """预处理M2数据"""
        try:
            data = m2_data.copy()
            
            # 查找时间列
            time_col = None
            for col in ['统计时间', 'date', '时间', '日期']:
                if col in data.columns:
                    time_col = col
                    break
            
            if time_col is None:
                logger.error("M2数据中未找到时间列")
                return pd.DataFrame()
            
            # 查找M2同比增长率列
            growth_col = None
            for col in data.columns:
                if 'M2' in col and ('同比' in col or 'yoy' in col.lower() or '增长' in col):
                    growth_col = col
                    break
            
            if growth_col is None:
                logger.error("M2数据中未找到同比增长率列")
                return pd.DataFrame()
            
            # 解析时间
            data['date'] = data[time_col].apply(self.parse_time_period)
            
            # 清理增长率数据
            data['m2_growth_rate'] = pd.to_numeric(data[growth_col], errors='coerce')
            
            # 过滤有效数据
            valid_data = data[data['date'].notna() & data['m2_growth_rate'].notna()].copy()
            valid_data = valid_data.sort_values('date')
            
            logger.info(f"M2数据预处理完成: {len(valid_data)} 行有效数据, "
                       f"日期范围: {valid_data['date'].min()} 到 {valid_data['date'].max()}")
            
            return valid_data[['date', 'm2_growth_rate']]
            
        except Exception as e:
            logger.error(f"M2数据预处理失败: {e}")
            return pd.DataFrame()
    
    def preprocess_industrial_data(self, industrial_data: pd.DataFrame) -> pd.DataFrame:
        """预处理工业增加值数据"""
        try:
            data = industrial_data.copy()
            
            # 查找时间列
            time_col = None
            for col in ['月份', '统计时间', 'date', '时间', '日期']:
                if col in data.columns:
                    time_col = col
                    break
            
            if time_col is None:
                logger.error("工业增加值数据中未找到时间列")
                logger.info(f"可用列: {list(data.columns)}")
                return pd.DataFrame()
            
            # 查找工业增加值增长率列 - 优先使用同比增长
            growth_col = None
            for col in ['同比增长', '同比', 'yoy']:
                if col in data.columns:
                    growth_col = col
                    break
            
            # 如果没找到，尝试其他可能的列名
            if growth_col is None:
                for col in data.columns:
                    if ('工业增加值' in col or '同比' in col or 'yoy' in col.lower()) and '增长' in col:
                        growth_col = col
                        break
            
            # 再尝试更广泛的搜索
            if growth_col is None:
                for col in data.columns:
                    col_lower = col.lower()
                    if any(keyword in col_lower for keyword in ['growth', 'rate', '增长', '比率']):
                        growth_col = col
                        break
            
            if growth_col is None:
                logger.error("工业增加值数据中未找到增长率列")
                logger.info(f"可用列: {list(data.columns)}")
                return pd.DataFrame()
            
            # 解析时间
            data['date'] = data[time_col].apply(self.parse_time_period)
            
            # 清理增长率数据
            data['industrial_growth_rate'] = pd.to_numeric(data[growth_col], errors='coerce')
            
            # 过滤有效数据
            valid_data = data[data['date'].notna() & data['industrial_growth_rate'].notna()].copy()
            valid_data = valid_data.sort_values('date')
            
            logger.info(f"工业增加值数据预处理完成: {len(valid_data)} 行有效数据, "
                       f"日期范围: {valid_data['date'].min()} 到 {valid_data['date'].max()}")
            
            return valid_data[['date', 'industrial_growth_rate']]
            
        except Exception as e:
            logger.error(f"工业增加值数据预处理失败: {e}")
            return pd.DataFrame()
    
    def preprocess_stock_index_data(self, stock_data: pd.DataFrame, index_name: str) -> pd.DataFrame:
        """预处理股票指数数据"""
        try:
            data = stock_data.copy()
            
            # 确保有date列
            if 'date' not in data.columns:
                logger.error(f"{index_name}数据中未找到date列")
                return pd.DataFrame()
            
            # 转换日期格式
            data['date'] = pd.to_datetime(data['date'])
            
            # 选择收盘价作为指数值
            if 'close' not in data.columns:
                logger.error(f"{index_name}数据中未找到close列")
                return pd.DataFrame()
            
            # 转换为月度数据（取每月最后一个交易日）
            data.set_index('date', inplace=True)
            monthly_data = data.resample('ME').last()  # 使用ME代替已弃用的M
            monthly_data = monthly_data.reset_index()
            
            # 将月末日期转换为下个月的月初日期，以便与宏观数据对齐
            # 例如：2025-07-31 -> 2025-08-01
            monthly_data['date'] = monthly_data['date'] + pd.DateOffset(days=1)
            monthly_data['date'] = monthly_data['date'].dt.to_period('M').dt.start_time
            
            # 计算月度收益率
            monthly_data['monthly_return'] = monthly_data['close'].pct_change()
            
            # 重命名列
            column_mapping = {
                'close': f'{index_name}_close',
                'monthly_return': f'{index_name}_return'
            }
            monthly_data = monthly_data.rename(columns=column_mapping)
            
            # 只保留需要的列
            keep_columns = ['date', f'{index_name}_close', f'{index_name}_return']
            monthly_data = monthly_data[keep_columns]
            
            # 过滤有效数据
            valid_data = monthly_data[monthly_data[f'{index_name}_close'].notna()].copy()
            
            logger.info(f"{index_name}指数数据预处理完成: {len(valid_data)} 行有效数据, "
                       f"日期范围: {valid_data['date'].min()} 到 {valid_data['date'].max()}")
            
            return valid_data
            
        except Exception as e:
            logger.error(f"{index_name}指数数据预处理失败: {e}")
            return pd.DataFrame()
    
    def calculate_china_excess_liquidity(self, source_data: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
        """计算中国超额流动性指标"""
        try:
            if 'm2' not in source_data or 'industrial' not in source_data:
                missing = [k for k in ['m2', 'industrial'] if k not in source_data]
                logger.error(f"缺少必要的源数据: {missing}")
                return None
            
            # 预处理数据
            m2_processed = self.preprocess_m2_data(source_data['m2'])
            industrial_processed = self.preprocess_industrial_data(source_data['industrial'])
            
            if m2_processed.empty or industrial_processed.empty:
                logger.error("预处理后数据为空")
                return None
            
            # 合并数据，按月对齐
            merged = pd.merge(m2_processed, industrial_processed, on='date', how='inner')
            
            # 处理股票指数数据
            if 'hs300' in source_data and 'zz2000' in source_data:
                hs300_processed = self.preprocess_stock_index_data(source_data['hs300'], 'hs300')
                zz2000_processed = self.preprocess_stock_index_data(source_data['zz2000'], 'zz2000')
                
                if not hs300_processed.empty and not zz2000_processed.empty:
                    # 合并股票指数数据
                    stock_merged = pd.merge(hs300_processed, zz2000_processed, on='date', how='inner')
                    if not stock_merged.empty:
                        # 计算中证2000/沪深300比值
                        stock_merged['zz2000_hs300_ratio'] = stock_merged['zz2000_close'] / stock_merged['hs300_close']
                        stock_merged['ratio_ma3'] = stock_merged['zz2000_hs300_ratio'].rolling(window=3).mean()
                        stock_merged['ratio_ma6'] = stock_merged['zz2000_hs300_ratio'].rolling(window=6).mean()
                        
                        # 合并到主数据
                        merged = pd.merge(merged, stock_merged, on='date', how='left')
                        logger.info(f"股票指数数据合并完成，包含比值数据: {merged['zz2000_hs300_ratio'].notna().sum()} 行")
            
            if merged.empty:
                logger.error("合并后数据为空，可能是日期不匹配")
                return None
            
            # 计算超额流动性指标
            merged['china_excess_liquidity'] = merged['m2_growth_rate'] - merged['industrial_growth_rate']
            
            # 计算移动平均
            merged['excess_liquidity_ma3'] = merged['china_excess_liquidity'].rolling(window=3).mean()
            merged['excess_liquidity_ma6'] = merged['china_excess_liquidity'].rolling(window=6).mean()
            merged['excess_liquidity_ma12'] = merged['china_excess_liquidity'].rolling(window=12).mean()
            
            # 计算变化率
            merged['excess_liquidity_change_1m'] = merged['china_excess_liquidity'].diff()
            merged['excess_liquidity_change_3m'] = merged['china_excess_liquidity'].diff(3)
            merged['excess_liquidity_change_12m'] = merged['china_excess_liquidity'].diff(12)
            
            # 按日期排序
            merged = merged.sort_values('date').reset_index(drop=True)
            
            logger.info(f"中国超额流动性指标计算完成: {len(merged)} 行, "
                       f"日期范围: {merged['date'].min()} 到 {merged['date'].max()}")
            
            return merged
            
        except Exception as e:
            logger.error(f"计算中国超额流动性指标失败: {e}")
            return None
    
    def get_latest_values(self, data: pd.DataFrame) -> Dict[str, Any]:
        """获取最新的指标值"""
        if data is None or data.empty:
            return {}
        
        latest = data.iloc[-1]
        
        return {
            'date': latest['date'].strftime('%Y-%m-%d'),
            'm2_growth_rate': round(latest['m2_growth_rate'], 2),
            'industrial_growth_rate': round(latest['industrial_growth_rate'], 2),
            'china_excess_liquidity': round(latest['china_excess_liquidity'], 2),
            'excess_liquidity_ma3': round(latest['excess_liquidity_ma3'], 2) if pd.notna(latest['excess_liquidity_ma3']) else None,
            'excess_liquidity_ma6': round(latest['excess_liquidity_ma6'], 2) if pd.notna(latest['excess_liquidity_ma6']) else None,
            'excess_liquidity_ma12': round(latest['excess_liquidity_ma12'], 2) if pd.notna(latest['excess_liquidity_ma12']) else None,
            'change_1m': round(latest['excess_liquidity_change_1m'], 2) if pd.notna(latest['excess_liquidity_change_1m']) else None,
            'change_3m': round(latest['excess_liquidity_change_3m'], 2) if pd.notna(latest['excess_liquidity_change_3m']) else None,
            'change_12m': round(latest['excess_liquidity_change_12m'], 2) if pd.notna(latest['excess_liquidity_change_12m']) else None
        }
    
    def update_and_calculate(self, force_update: bool = False) -> Optional[pd.DataFrame]:
        """更新源数据并计算中国超额流动性指标"""
        try:
            # 1. 确保源指标已配置
            self._ensure_source_indicators()
            
            # 2. 获取源数据
            source_data = self.ensure_source_data(force_update)
            
            if 'm2' not in source_data or 'industrial' not in source_data:
                missing = [k for k in ['m2', 'industrial'] if k not in source_data]
                logger.error(f"源数据不完整，缺少必要数据: {missing}")
                return None
            
            # 3. 计算超额流动性指标
            result = self.calculate_china_excess_liquidity(source_data)
            
            if result is not None:
                # 4. 保存结果到数据库
                from ..database.db_manager import db_manager
                table_name = "china_excess_liquidity"
                
                if db_manager.save_data(result, table_name):
                    # 注册指标信息
                    db_manager.register_indicator(
                        indicator_key="china_excess_liquidity",
                        name=self.name,
                        description=self.description,
                        source="composite",
                        table_name=table_name
                    )
                    db_manager.update_indicator_timestamp("china_excess_liquidity")
                    
                    logger.info("中国超额流动性指标已保存到数据库")
            
            return result
            
        except Exception as e:
            logger.error(f"更新和计算中国超额流动性指标失败: {e}")
            return None
    
    def _ensure_source_indicators(self):
        """确保源指标已配置"""
        from ..utils.config import config_manager
        
        indicators = config_manager.get_indicators()
        
        # 检查M2指标
        if self.m2_indicator_key not in indicators:
            logger.info("添加中国M2指标配置...")
            m2_config = {
                "name": "中国M2货币供应量",
                "description": "中国广义货币M2供应量及同比增长率数据",
                "source": "akshare",
                "function": "macro_china_supply_of_money",
                "params": {},
                "table_name": "china_m2_data",
                "update_frequency": "monthly",
                "enabled": True
            }
            config_manager.add_indicator(self.m2_indicator_key, m2_config)
        
        # 检查工业增加值指标
        if self.industrial_indicator_key not in indicators:
            logger.info("添加中国工业增加值指标配置...")
            industrial_config = {
                "name": "中国工业增加值",
                "description": "中国工业增加值及增长率数据",
                "source": "akshare", 
                "function": "macro_china_gyzjz",
                "params": {},
                "table_name": "china_industrial_data",
                "update_frequency": "monthly",
                "enabled": True
            }
            config_manager.add_indicator(self.industrial_indicator_key, industrial_config)
        
        # 检查沪深300指标
        if self.hs300_indicator_key not in indicators:
            logger.info("添加沪深300指数指标配置...")
            hs300_config = {
                "name": "沪深300指数",
                "description": "沪深300指数历史价格数据",
                "source": "akshare",
                "function": "stock_zh_index_daily_tx",
                "params": {"symbol": "sh000300"},
                "table_name": "hs300_index_data",
                "update_frequency": "daily",
                "enabled": True
            }
            config_manager.add_indicator(self.hs300_indicator_key, hs300_config)
        
        # 检查中证2000指标
        if self.zz2000_indicator_key not in indicators:
            logger.info("添加中证2000指数指标配置...")
            zz2000_config = {
                "name": "中证2000指数(国证2000)",
                "description": "中证2000指数(国证2000)历史价格数据",
                "source": "akshare",
                "function": "stock_zh_index_daily_tx",
                "params": {"symbol": "sz399303"},
                "table_name": "zz2000_index_data",
                "update_frequency": "daily",
                "enabled": True
            }
            config_manager.add_indicator(self.zz2000_indicator_key, zz2000_config)

# 全局中国超额流动性指标实例
china_liquidity_indicator = ChinaLiquidityIndicator()
