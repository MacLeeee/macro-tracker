"""
复合指标计算器 - 用于创建由多个数据源合成的指标
"""
import pandas as pd
from typing import Dict, Any, Optional, List, Callable
from loguru import logger
from datetime import datetime

from .data_manager import data_manager

class CompositeIndicator:
    """复合指标计算器"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def calculate(self, source_data: Dict[str, pd.DataFrame], 
                 calculation_func: Callable, **kwargs) -> Optional[pd.DataFrame]:
        """计算复合指标"""
        try:
            result = calculation_func(source_data, **kwargs)
            
            if result is not None and not result.empty:
                logger.info(f"复合指标 {self.name} 计算完成，{len(result)} 行数据")
                return result
            else:
                logger.warning(f"复合指标 {self.name} 计算结果为空")
                return None
                
        except Exception as e:
            logger.error(f"复合指标 {self.name} 计算失败: {e}")
            return None

class LiquidityIndicator(CompositeIndicator):
    """流动性前瞻指标 (BTC价格 ÷ 美元指数)"""
    
    def __init__(self):
        super().__init__(
            name="流动性前瞻指标",
            description="比特币价格除以美元指数，用于衡量全球流动性状况"
        )
        self.btc_indicator_key = "openbb_btc_price"
        self.dxy_indicator_key = "openbb_dxy_index"
        self.nasdaq_indicator_key = "openbb_nasdaq_index"
    
    def ensure_source_data(self, force_update: bool = False) -> Dict[str, pd.DataFrame]:
        """确保源数据可用"""
        source_data = {}
        
        # 获取BTC数据
        logger.info("获取比特币价格数据...")
        btc_data = data_manager.fetch_indicator_data(self.btc_indicator_key, force_update)
        if btc_data is not None and not btc_data.empty:
            source_data['btc'] = btc_data
            logger.info(f"BTC数据: {len(btc_data)} 行, 日期范围: {btc_data['date'].min()} 到 {btc_data['date'].max()}")
        else:
            logger.error("BTC数据获取失败")
        
        # 获取美元指数数据
        logger.info("获取美元指数数据...")
        dxy_data = data_manager.fetch_indicator_data(self.dxy_indicator_key, force_update)
        if dxy_data is not None and not dxy_data.empty:
            source_data['dxy'] = dxy_data
            logger.info(f"DXY数据: {len(dxy_data)} 行, 日期范围: {dxy_data['date'].min()} 到 {dxy_data['date'].max()}")
        else:
            logger.error("美元指数数据获取失败")
        
        # 获取纳斯达克指数数据
        logger.info("获取纳斯达克指数数据...")
        nasdaq_data = data_manager.fetch_indicator_data(self.nasdaq_indicator_key, force_update)
        if nasdaq_data is not None and not nasdaq_data.empty:
            source_data['nasdaq'] = nasdaq_data
            logger.info(f"NASDAQ数据: {len(nasdaq_data)} 行, 日期范围: {nasdaq_data['date'].min()} 到 {nasdaq_data['date'].max()}")
        else:
            logger.error("纳斯达克指数数据获取失败")
        
        return source_data
    
    def calculate_liquidity_ratio(self, source_data: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
        """计算流动性比率"""
        try:
            if 'btc' not in source_data or 'dxy' not in source_data:
                missing = [k for k in ['btc', 'dxy'] if k not in source_data]
                logger.error(f"缺少必要的源数据: {missing}")
                return None
            
            btc_data = source_data['btc'].copy()
            dxy_data = source_data['dxy'].copy()
            nasdaq_data = source_data.get('nasdaq', pd.DataFrame()).copy() if 'nasdaq' in source_data else None
            
            # 确保日期列格式一致
            btc_data['date'] = pd.to_datetime(btc_data['date']).dt.date
            dxy_data['date'] = pd.to_datetime(dxy_data['date']).dt.date
            if nasdaq_data is not None and not nasdaq_data.empty:
                nasdaq_data['date'] = pd.to_datetime(nasdaq_data['date']).dt.date
            
            # 选择需要的列
            btc_clean = btc_data[['date', 'close']].rename(columns={'close': 'btc_price'})
            dxy_clean = dxy_data[['date', 'close']].rename(columns={'close': 'dxy_value'})
            
            # 合并数据，只保留两个数据集都有的日期
            merged = pd.merge(btc_clean, dxy_clean, on='date', how='inner')
            
            # 如果有纳斯达克数据，也加入合并
            if nasdaq_data is not None and not nasdaq_data.empty:
                nasdaq_clean = nasdaq_data[['date', 'close']].rename(columns={'close': 'nasdaq_value'})
                merged = pd.merge(merged, nasdaq_clean, on='date', how='left')
            
            if merged.empty:
                logger.error("合并后数据为空，可能是日期不匹配")
                return None
            
            # 计算流动性指标
            merged['liquidity_indicator'] = merged['btc_price'] / merged['dxy_value']
            
            # 计算一些衍生指标
            merged['btc_price_ma7'] = merged['btc_price'].rolling(window=7).mean()
            merged['dxy_value_ma7'] = merged['dxy_value'].rolling(window=7).mean()
            merged['liquidity_indicator_ma7'] = merged['liquidity_indicator'].rolling(window=7).mean()
            merged['liquidity_indicator_ma30'] = merged['liquidity_indicator'].rolling(window=30).mean()
            
            # 如果有纳斯达克数据，计算相关衍生指标
            if 'nasdaq_value' in merged.columns and not merged['nasdaq_value'].isna().all():
                merged['nasdaq_ma7'] = merged['nasdaq_value'].rolling(window=7).mean()
                merged['nasdaq_ma30'] = merged['nasdaq_value'].rolling(window=30).mean()
                merged['nasdaq_change_1d'] = merged['nasdaq_value'].pct_change()
                merged['nasdaq_change_7d'] = merged['nasdaq_value'].pct_change(7)
                merged['nasdaq_change_30d'] = merged['nasdaq_value'].pct_change(30)
            
            # 计算变化率
            merged['liquidity_change_1d'] = merged['liquidity_indicator'].pct_change()
            merged['liquidity_change_7d'] = merged['liquidity_indicator'].pct_change(7)
            merged['liquidity_change_30d'] = merged['liquidity_indicator'].pct_change(30)
            
            # 重新设置日期为datetime格式
            merged['date'] = pd.to_datetime(merged['date'])
            
            # 按日期排序
            merged = merged.sort_values('date').reset_index(drop=True)
            
            logger.info(f"流动性指标计算完成: {len(merged)} 行, 日期范围: {merged['date'].min()} 到 {merged['date'].max()}")
            
            return merged
            
        except Exception as e:
            logger.error(f"计算流动性指标失败: {e}")
            return None
    
    def get_latest_values(self, data: pd.DataFrame) -> Dict[str, Any]:
        """获取最新的指标值"""
        if data is None or data.empty:
            return {}
        
        latest = data.iloc[-1]
        
        return {
            'date': latest['date'].strftime('%Y-%m-%d'),
            'btc_price': round(latest['btc_price'], 2),
            'dxy_value': round(latest['dxy_value'], 4),
            'liquidity_indicator': round(latest['liquidity_indicator'], 6),
            'liquidity_ma7': round(latest['liquidity_indicator_ma7'], 6) if pd.notna(latest['liquidity_indicator_ma7']) else None,
            'liquidity_ma30': round(latest['liquidity_indicator_ma30'], 6) if pd.notna(latest['liquidity_indicator_ma30']) else None,
            'change_1d': round(latest['liquidity_change_1d'] * 100, 2) if pd.notna(latest['liquidity_change_1d']) else None,
            'change_7d': round(latest['liquidity_change_7d'] * 100, 2) if pd.notna(latest['liquidity_change_7d']) else None,
            'change_30d': round(latest['liquidity_change_30d'] * 100, 2) if pd.notna(latest['liquidity_change_30d']) else None
        }
    
    def update_and_calculate(self, force_update: bool = False) -> Optional[pd.DataFrame]:
        """更新源数据并计算流动性指标"""
        try:
            # 1. 确保源指标已配置
            self._ensure_source_indicators()
            
            # 2. 获取源数据
            source_data = self.ensure_source_data(force_update)
            
            if 'btc' not in source_data or 'dxy' not in source_data:
                missing = [k for k in ['btc', 'dxy'] if k not in source_data]
                logger.error(f"源数据不完整，缺少必要数据: {missing}")
                return None
            
            # 3. 计算流动性指标
            result = self.calculate_liquidity_ratio(source_data)
            
            if result is not None:
                # 4. 保存结果到数据库
                from ..database.db_manager import db_manager
                table_name = "liquidity_indicator"
                
                if db_manager.save_data(result, table_name):
                    # 注册指标信息
                    db_manager.register_indicator(
                        indicator_key="liquidity_indicator",
                        name=self.name,
                        description=self.description,
                        source="composite",
                        table_name=table_name
                    )
                    db_manager.update_indicator_timestamp("liquidity_indicator")
                    
                    logger.info("流动性指标已保存到数据库")
            
            return result
            
        except Exception as e:
            logger.error(f"更新和计算流动性指标失败: {e}")
            return None
    
    def _ensure_source_indicators(self):
        """确保源指标已配置"""
        from ..utils.config import config_manager
        
        indicators = config_manager.get_indicators()
        
        # 检查BTC指标
        if self.btc_indicator_key not in indicators:
            logger.info("添加BTC价格指标配置...")
            btc_config = {
                "name": "比特币价格",
                "description": "比特币对美元的历史价格数据", 
                "source": "openbb",
                "function": "crypto.price.historical",
                "params": {
                    "symbol": "BTC-USD",
                    "provider": "yfinance",
                    "interval": "1d"
                },
                "default_start_date": "2020-01-01",
                "table_name": "btc_price_data",
                "update_frequency": "daily",
                "enabled": True
            }
            config_manager.add_indicator(self.btc_indicator_key, btc_config)
        
        # 检查美元指数指标
        if self.dxy_indicator_key not in indicators:
            logger.info("添加美元指数指标配置...")
            dxy_config = {
                "name": "美元指数",
                "description": "美元指数(DXY)历史数据",
                "source": "openbb", 
                "function": "equity.price.historical",
                "params": {
                    "symbol": "DX-Y.NYB",
                    "provider": "yfinance",
                    "interval": "1d"
                },
                "default_start_date": "2020-01-01",
                "table_name": "dxy_index_data",
                "update_frequency": "daily",
                "enabled": True
            }
            config_manager.add_indicator(self.dxy_indicator_key, dxy_config)
        
        # 检查纳斯达克指标
        if self.nasdaq_indicator_key not in indicators:
            logger.info("添加纳斯达克指数指标配置...")
            nasdaq_config = {
                "name": "纳斯达克指数",
                "description": "纳斯达克综合指数历史数据",
                "source": "openbb", 
                "function": "equity.price.historical",
                "params": {
                    "symbol": "^IXIC",
                    "provider": "yfinance",
                    "interval": "1d"
                },
                "default_start_date": "2020-01-01",
                "table_name": "nasdaq_index_data",
                "update_frequency": "daily",
                "enabled": True
            }
            config_manager.add_indicator(self.nasdaq_indicator_key, nasdaq_config)

# 全局流动性指标实例
liquidity_indicator = LiquidityIndicator()
