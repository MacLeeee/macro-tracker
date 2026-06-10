"""
yfinance 数据获取器 - 轻量替代 OpenBB（仅用于行情类数据）

兼容原 OpenBB 指标配置：忽略 function 路径，直接使用 params.symbol 拉取日线行情，
输出列与原缓存表一致：date / open / high / low / close / volume
"""
import pandas as pd
from typing import Dict, Any, Optional
from loguru import logger

from .incremental_fetcher import IncrementalFetcher

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance 未安装，相关功能将不可用")


class YFinanceFetcher(IncrementalFetcher):
    """yfinance 数据获取器（支持增量缓存）"""

    def __init__(self, rate_limit: int = 5, cache_db_path: str = "data/cache.db"):
        super().__init__("yfinance", cache_db_path, rate_limit)

        if not YFINANCE_AVAILABLE:
            raise ImportError("yfinance 未安装，请运行: pip install yfinance")

    def fetch_data(self, indicator_config: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """按指标配置拉取日线行情"""
        try:
            params = indicator_config.get('params', {})
            symbol = params.get('symbol')
            if not symbol:
                logger.error("yfinance 指标配置缺少 symbol 参数")
                return None

            start_date = params.get('start_date') or indicator_config.get('default_start_date', '2020-01-01')
            end_date = params.get('end_date')

            logger.info(f"yfinance 拉取 {symbol}: {start_date} -> {end_date or 'latest'}")

            ticker = yf.Ticker(symbol)
            # end 为开区间，向后顺延一天以包含当日
            end_param = None
            if end_date:
                end_param = (pd.to_datetime(end_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')

            data = ticker.history(start=start_date, end=end_param, interval='1d', auto_adjust=False)

            if data is None or data.empty:
                logger.warning(f"yfinance 返回空数据: {symbol}")
                return None

            data = data.reset_index()
            # 统一列名并去除时区
            rename_map = {}
            for col in data.columns:
                lc = str(col).lower().replace(' ', '_')
                if lc in ('date', 'datetime'):
                    rename_map[col] = 'date'
                elif lc in ('open', 'high', 'low', 'close', 'volume'):
                    rename_map[col] = lc
            data = data.rename(columns=rename_map)

            keep_cols = [c for c in ['date', 'open', 'high', 'low', 'close', 'volume'] if c in data.columns]
            data = data[keep_cols]

            data['date'] = pd.to_datetime(data['date'])
            if getattr(data['date'].dt, 'tz', None) is not None:
                data['date'] = data['date'].dt.tz_localize(None)
            data['date'] = data['date'].dt.normalize()

            # 截掉 start_date 之前的数据，防止增量缓存出现重复行
            data = data[data['date'] >= pd.to_datetime(start_date)]
            data = data.drop_duplicates(subset=['date']).sort_values('date')

            if data.empty:
                return None

            if not self.validate_data(data):
                return None

            return data

        except Exception as e:
            logger.error(f"yfinance 数据获取失败: {e}")
            return None
