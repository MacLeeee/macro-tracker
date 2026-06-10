"""
OpenBB 数据获取器
"""
import pandas as pd
from typing import Dict, Any, Optional
from loguru import logger
from .base_fetcher import BaseFetcher
from .incremental_fetcher import IncrementalFetcher

try:
    from openbb import obb as openbb
    OPENBB_AVAILABLE = True
except ImportError:
    try:
        from openbb_terminal.sdk import openbb
        OPENBB_AVAILABLE = True
    except ImportError:
        OPENBB_AVAILABLE = False
        logger.warning("OpenBB 未安装，相关功能将不可用")

class OpenBBFetcher(IncrementalFetcher):
    """OpenBB 数据获取器"""
    
    def __init__(self, rate_limit: int = 5, cache_db_path: str = "data/cache.db"):
        super().__init__("openbb", cache_db_path, rate_limit)
        
        if not OPENBB_AVAILABLE:
            raise ImportError("OpenBB 未安装，请运行: pip install openbb")
    
    def fetch_data(self, indicator_config: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """从 OpenBB 获取数据"""
        try:
            function_path = indicator_config.get('function')
            params = indicator_config.get('params', {})
            
            if not function_path:
                logger.error("未指定 OpenBB 函数路径")
                return None
            
            # 解析函数路径 (例如: "crypto.price.historical")
            path_parts = function_path.split('.')
            
            # 获取 OpenBB 函数
            current_module = openbb
            for i, part in enumerate(path_parts):
                if hasattr(current_module, part):
                    current_module = getattr(current_module, part)
                    logger.debug(f"找到模块路径 {'.'.join(path_parts[:i+1])}")
                else:
                    logger.error(f"OpenBB 中未找到路径: {'.'.join(path_parts[:i+1])}")
                    logger.debug(f"可用属性: {[attr for attr in dir(current_module) if not attr.startswith('_')]}")
                    return None
            
            logger.info(f"调用 OpenBB 函数: {function_path}, 参数: {params}")
            
            # 调用函数
            data = current_module(**params)
            
            if data is None:
                logger.warning(f"OpenBB 返回空数据: {function_path}")
                return None
            
            # 转换为 DataFrame
            if hasattr(data, 'to_df'):
                data = data.to_df()
            elif not isinstance(data, pd.DataFrame):
                logger.error(f"OpenBB 返回不支持的数据类型: {type(data)}")
                return None
            
            if data.empty:
                logger.warning(f"OpenBB 返回空 DataFrame: {function_path}")
                return None
            
            # 数据预处理 (在验证前进行，确保日期列正确)
            data = self.preprocess_data(data)
            
            # 数据验证
            if not self.validate_data(data):
                return None
            
            return data
            
        except Exception as e:
            logger.error(f"OpenBB 数据获取失败: {e}")
            return None
    
    def get_available_functions(self) -> dict:
        """获取可用的 OpenBB 函数列表"""
        if not OPENBB_AVAILABLE:
            return {}
        
        functions = {}
        
        # 遍历主要模块
        main_modules = ['economy', 'stocks', 'crypto', 'forex', 'funds', 'etf']
        
        for module_name in main_modules:
            if hasattr(openbb, module_name):
                module = getattr(openbb, module_name)
                module_functions = [name for name in dir(module) 
                                  if not name.startswith('_') and callable(getattr(module, name))]
                functions[module_name] = module_functions
        
        return functions
    
    def test_function(self, function_path: str, params: Dict[str, Any] = None) -> bool:
        """测试 OpenBB 函数是否可用"""
        if not OPENBB_AVAILABLE:
            return False
        
        try:
            path_parts = function_path.split('.')
            current_module = openbb
            
            for part in path_parts:
                if hasattr(current_module, part):
                    current_module = getattr(current_module, part)
                else:
                    return False
            
            # 尝试调用函数（使用默认或测试参数）
            test_params = params or {}
            data = current_module(**test_params)
            return data is not None
            
        except Exception as e:
            logger.debug(f"函数测试失败 {function_path}: {e}")
            return False

# 预定义的一些常用 OpenBB 指标配置
OPENBB_INDICATORS = {
    "btc_price": {
        "name": "比特币价格",
        "description": "比特币对美元的历史价格数据",
        "function": "crypto.price.historical",
        "params": {
            "symbol": "BTC-USD",
            "provider": "yfinance",
            "interval": "1d"
        },
        "default_start_date": "2020-01-01"
    },
    "dxy_index": {
        "name": "美元指数",
        "description": "美元指数(DXY)历史数据",
        "function": "equity.price.historical", 
        "params": {
            "symbol": "DX-Y.NYB",
            "provider": "yfinance",
            "interval": "1d"
        },
        "default_start_date": "2020-01-01"
    },
    "economy_gdp": {
        "name": "GDP数据",
        "description": "国内生产总值数据", 
        "function": "economy.gdp",
        "params": {
            "country": "united_states",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31"
        }
    },
    "economy_inflation": {
        "name": "通胀率数据",
        "description": "消费者价格指数和通胀率",
        "function": "economy.cpi",
        "params": {
            "country": "united_states",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31"
        }
    },
    "economy_unemployment": {
        "name": "失业率数据",
        "description": "失业率统计数据",
        "function": "economy.unemp",
        "params": {
            "country": "united_states",
            "start_date": "2020-01-01", 
            "end_date": "2024-12-31"
        }
    },
    "stocks_sp500": {
        "name": "标普500指数",
        "description": "标普500指数历史数据",
        "function": "equity.price.historical",
        "params": {
            "symbol": "SPY",
            "provider": "yfinance",
            "start_date": "2020-01-01",
            "end_date": "2024-12-31"
        }
    },
    "nasdaq_index": {
        "name": "纳斯达克指数",
        "description": "纳斯达克综合指数历史数据",
        "function": "equity.price.historical",
        "params": {
            "symbol": "^IXIC",
            "provider": "yfinance",
            "interval": "1d"
        },
        "default_start_date": "2020-01-01"
    }
}
