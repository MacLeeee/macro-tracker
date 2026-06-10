"""
数据管理器 - 统一数据获取和管理接口
"""
import pandas as pd
from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime

from .akshare_fetcher import AkShareFetcher, AKSHARE_INDICATORS
from .yfinance_fetcher import YFinanceFetcher
from ..utils.config import config_manager
from ..database.db_manager import db_manager

class DataManager:
    """数据管理器"""
    
    def __init__(self):
        self.fetchers = {}
        self.init_fetchers()
    
    def init_fetchers(self):
        """初始化数据获取器"""
        try:
            # 初始化 AkShare
            akshare_config = config_manager.get_data_source('akshare')
            if akshare_config.get('enabled', True):
                try:
                    self.fetchers['akshare'] = AkShareFetcher(
                        rate_limit=akshare_config.get('rate_limit', 10)
                    )
                    logger.info("AkShare 获取器初始化成功")
                except ImportError as e:
                    logger.warning(f"AkShare 初始化失败: {e}")
            
            # 初始化 yfinance（沿用历史 'openbb' 数据源键，避免改动既有指标配置）
            openbb_config = config_manager.get_data_source('openbb')
            if openbb_config.get('enabled', True):
                try:
                    self.fetchers['openbb'] = YFinanceFetcher(
                        rate_limit=openbb_config.get('rate_limit', 5),
                        cache_db_path="data/cache.db"
                    )
                    logger.info("yfinance 获取器初始化成功（数据源键: openbb）")
                except ImportError as e:
                    logger.warning(f"yfinance 初始化失败: {e}")
                    
        except Exception as e:
            logger.error(f"数据获取器初始化失败: {e}")
    
    def fetch_indicator_data(self, indicator_key: str, 
                           force_update: bool = False) -> Optional[pd.DataFrame]:
        """获取指标数据"""
        try:
            # 获取指标配置
            indicator_config = config_manager.get_indicator(indicator_key)
            if not indicator_config:
                logger.error(f"未找到指标配置: {indicator_key}")
                return None
            
            source = indicator_config.get('source')
            if source not in self.fetchers:
                logger.error(f"数据源 {source} 不可用")
                return None
            
            # 检查是否需要更新
            if not force_update and self.is_data_fresh(indicator_key, indicator_config):
                logger.info(f"指标 {indicator_key} 数据是最新的，跳过更新")
                table_name = indicator_config.get('table_name', indicator_key)
                return db_manager.load_data(table_name)
            
            # 获取数据 - 优先使用增量获取
            fetcher = self.fetchers[source]
            table_name = indicator_config.get('table_name', indicator_key)
            
            # 如果获取器支持增量下载，使用增量方式
            if hasattr(fetcher, 'fetch_incremental_data'):
                data = fetcher.fetch_incremental_data(indicator_config, table_name)
            else:
                # 回退到传统方式
                data = fetcher.fetch_with_retry(
                    indicator_config, 
                    retry_times=config_manager.get_data_source(source).get('retry_times', 3)
                )
            
            if data is None or data.empty:
                logger.error(f"获取指标数据失败: {indicator_key}")
                return None
            
            # 保存数据
            table_name = indicator_config.get('table_name', indicator_key)
            if db_manager.save_data(data, table_name):
                # 注册/更新指标元信息
                db_manager.register_indicator(
                    indicator_key=indicator_key,
                    name=indicator_config.get('name', indicator_key),
                    description=indicator_config.get('description', ''),
                    source=source,
                    table_name=table_name
                )
                db_manager.update_indicator_timestamp(indicator_key)
                logger.info(f"指标 {indicator_key} 数据更新完成")
            
            return data
            
        except Exception as e:
            logger.error(f"获取指标数据失败: {indicator_key}, 错误: {e}")
            return None
    
    def is_data_fresh(self, indicator_key: str, indicator_config: Dict[str, Any]) -> bool:
        """检查数据是否需要更新"""
        try:
            # 获取上次更新时间
            with db_manager.engine.connect() as conn:
                from sqlalchemy import text
                result = conn.execute(text(
                    "SELECT last_update FROM indicator_meta WHERE indicator_key = :key"
                ), {"key": indicator_key})
                row = result.fetchone()
                
                if not row or not row[0]:
                    return False
                
                last_update = pd.to_datetime(row[0])
                current_time = pd.Timestamp.now()
                
                # 根据更新频率判断是否需要更新
                frequency = indicator_config.get('update_frequency', 'daily')
                if frequency == 'daily':
                    return (current_time - last_update).days < 1
                elif frequency == 'weekly':
                    return (current_time - last_update).days < 7
                elif frequency == 'monthly':
                    return (current_time - last_update).days < 30
                else:
                    return False
                    
        except Exception as e:
            logger.debug(f"检查数据新鲜度失败: {e}")
            return False
    
    def update_all_indicators(self, force_update: bool = False) -> Dict[str, bool]:
        """更新所有启用的指标"""
        results = {}
        indicators = config_manager.get_indicators()
        
        logger.info(f"开始更新 {len(indicators)} 个指标")
        
        for indicator_key in indicators:
            try:
                data = self.fetch_indicator_data(indicator_key, force_update)
                results[indicator_key] = data is not None
                
            except Exception as e:
                logger.error(f"更新指标失败 {indicator_key}: {e}")
                results[indicator_key] = False
        
        successful = sum(results.values())
        logger.info(f"指标更新完成: {successful}/{len(indicators)} 成功")
        
        return results
    
    def get_indicator_data(self, indicator_key: str, 
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """获取指标数据（从数据库）"""
        indicator_config = config_manager.get_indicator(indicator_key)
        if not indicator_config:
            return None
        
        table_name = indicator_config.get('table_name', indicator_key)
        return db_manager.load_data(table_name, start_date, end_date)
    
    def list_available_indicators(self) -> Dict[str, Dict[str, Any]]:
        """列出所有可用指标"""
        indicators = config_manager.get_indicators()
        
        # 添加预定义指标
        available_indicators = {}
        
        # AkShare 预定义指标
        for key, config in AKSHARE_INDICATORS.items():
            if key not in indicators:
                available_indicators[f"akshare_{key}"] = {
                    **config,
                    "source": "akshare",
                    "table_name": f"akshare_{key}",
                    "update_frequency": "daily",
                    "enabled": False
                }
        
        # 合并已配置的指标
        available_indicators.update(indicators)
        
        return available_indicators
    
    def add_indicator(self, indicator_key: str, indicator_config: Dict[str, Any]):
        """添加新指标"""
        try:
            # 验证配置
            required_fields = ['name', 'source', 'function']
            for field in required_fields:
                if field not in indicator_config:
                    raise ValueError(f"缺少必需字段: {field}")
            
            # 设置默认值
            indicator_config.setdefault('table_name', indicator_key)
            indicator_config.setdefault('update_frequency', 'daily')
            indicator_config.setdefault('enabled', True)
            indicator_config.setdefault('params', {})
            
            # 保存配置
            config_manager.add_indicator(indicator_key, indicator_config)
            
            logger.info(f"新增指标: {indicator_key}")
            return True
            
        except Exception as e:
            logger.error(f"添加指标失败: {e}")
            return False

# 全局数据管理器实例
data_manager = DataManager()
