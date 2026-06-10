"""
AkShare 数据获取器
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
from typing import Dict, Any, Optional

from .base_fetcher import BaseFetcher


class AkShareFetcher(BaseFetcher):
    """AkShare 数据获取器"""
    
    def __init__(self, rate_limit: int = 10, **kwargs):
        super().__init__(source_name="akshare", rate_limit=rate_limit)
        self.source = "akshare"
        
        # 尝试导入akshare
        try:
            import akshare as ak
            self.ak = ak
            self.available = True
            logger.info("AkShare 导入成功")
        except ImportError:
            self.ak = None
            self.available = False
            logger.warning("AkShare 未安装，相关功能将不可用")
    
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        return self.available
    
    def fetch_data(self, indicator_config: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        获取指定指标的数据（适配基类接口）
        
        Args:
            indicator_config: 指标配置字典
            
        Returns:
            数据DataFrame，如果失败返回None
        """
        if not self.is_available():
            logger.error("AkShare 不可用")
            return None
        
        # 从配置中提取信息
        function_name = indicator_config.get("function")
        params = indicator_config.get("params", {})
        indicator_name = indicator_config.get("name", "未知指标")
        
        if not function_name:
            logger.error("指标配置中缺少function字段")
            return None
        
        try:
            logger.info(f"开始获取 {indicator_name} 数据...")
            
            # 获取函数
            if hasattr(self.ak, function_name):
                fetch_function = getattr(self.ak, function_name)
            else:
                logger.error(f"AkShare 中未找到函数: {function_name}")
                return None
            
            # 调用函数获取数据
            if params:
                data = fetch_function(**params)
            else:
                data = fetch_function()
            
            if data is None or data.empty:
                logger.warning(f"{indicator_name} 返回空数据")
                return None
            
            logger.info(f"AkShare 数据获取成功: {len(data)} 行")
            
            # 预处理数据
            processed_data = self.preprocess_data(data)
            
            # 验证数据
            if self.validate_data(processed_data):
                return processed_data
            else:
                logger.error("数据验证失败")
                return None
                
        except Exception as e:
            logger.error(f"AkShare 数据获取失败: {e}")
            return None

    def fetch_data_by_key(self, indicator_key: str, params: Dict[str, Any] = None) -> Optional[pd.DataFrame]:
        """
        根据指标键获取数据（便捷方法）
        
        Args:
            indicator_key: 指标标识符
            params: 额外参数字典
            
        Returns:
            数据DataFrame，如果失败返回None
        """
        if indicator_key not in AKSHARE_INDICATORS:
            logger.error(f"未知的指标: {indicator_key}")
            return None
        
        indicator_config = AKSHARE_INDICATORS[indicator_key].copy()
        
        # 合并参数
        if params:
            indicator_config["params"] = {**indicator_config.get("params", {}), **params}
        
        return self.fetch_data(indicator_config)


# AkShare 支持的指标配置
AKSHARE_INDICATORS = {
    "macro_china_m2": {
        "name": "中国M2货币供应量",
        "description": "中国广义货币M2供应量及同比增长率数据",
        "function": "macro_china_supply_of_money",
        "params": {}
    },
    "macro_china_m1m2": {
        "name": "中国M1M2货币供应量",
        "description": "中国M1和M2货币供应量及增长率数据",
        "function": "macro_china_supply_of_money",
        "params": {}
    },
    "macro_china_industrial": {
        "name": "中国工业增加值",
        "description": "中国工业增加值及增长率数据",
        "function": "macro_china_gyzjz",
        "params": {}
    },
    "stock_hs300_index": {
        "name": "沪深300指数",
        "description": "沪深300指数历史价格数据",
        "function": "stock_zh_index_daily_tx",
        "params": {
            "symbol": "sh000300"
        }
    },
    "stock_zz2000_index": {
        "name": "中证2000指数(国证2000)",
        "description": "中证2000指数(国证2000)历史价格数据",
        "function": "stock_zh_index_daily_tx", 
        "params": {
            "symbol": "sz399303"
        }
    },
    "stock_zz500_index": {
        "name": "中证500指数",
        "description": "中证500指数历史价格数据",
        "function": "stock_zh_index_daily_tx",
        "params": {
            "symbol": "sh000905"
        }
    },
    "stock_zz500_pe": {
        "name": "中证500滚动市盈率",
        "description": "中证500指数滚动市盈率估值数据",
        "function": "stock_zh_index_hist_csindex",
        "params": {
            "symbol": "000905"
        }
    },
    "macro_usa_ism_pmi": {
        "name": "美国ISM制造业PMI",
        "description": "美国ISM制造业采购经理人指数数据",
        "function": "macro_usa_ism_pmi",
        "params": {}
    },
    "macro_china_new_financial_credit": {
        "name": "社会融资规模增量",
        "description": "社会融资规模增量统计数据",
        "function": "macro_china_new_financial_credit",
        "params": {}
    },
    "macro_china_gdp": {
        "name": "中国GDP",
        "description": "中国季度GDP数据",
        "function": "macro_china_gdp",
        "params": {}
    },
    "macro_china_ppi": {
        "name": "中国PPI",
        "description": "中国工业生产者出厂价格指数(PPI)",
        "function": "macro_china_ppi",
        "params": {}
    }
}
