"""
数据获取基础类
"""
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from loguru import logger
import time
import traceback

class BaseFetcher(ABC):
    """数据获取基础类"""
    
    def __init__(self, source_name: str, rate_limit: int = 10):
        self.source_name = source_name
        self.rate_limit = rate_limit  # 每秒请求限制
        self.last_request_time = 0
    
    def _rate_limit_check(self):
        """请求速率限制检查"""
        current_time = time.time()
        time_diff = current_time - self.last_request_time
        min_interval = 1.0 / self.rate_limit
        
        if time_diff < min_interval:
            sleep_time = min_interval - time_diff
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    @abstractmethod
    def fetch_data(self, indicator_config: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """获取数据的抽象方法"""
        pass
    
    def fetch_with_retry(self, indicator_config: Dict[str, Any], 
                        retry_times: int = 3) -> Optional[pd.DataFrame]:
        """带重试的数据获取"""
        for attempt in range(retry_times):
            try:
                self._rate_limit_check()
                data = self.fetch_data(indicator_config)
                
                if data is not None and not data.empty:
                    logger.info(f"成功获取数据: {indicator_config.get('name', '未知指标')}")
                    return data
                else:
                    logger.warning(f"获取到空数据: {indicator_config.get('name', '未知指标')}")
                    return None
                    
            except Exception as e:
                logger.error(f"第 {attempt + 1} 次尝试失败: {e}")
                if attempt < retry_times - 1:
                    wait_time = (attempt + 1) * 2  # 指数退避
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"所有重试失败，放弃获取数据: {traceback.format_exc()}")
        
        return None
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """数据验证"""
        if data is None or data.empty:
            return False
        
        # 检查是否有日期列
        date_columns = ['date', 'Date', 'DATE', '日期']
        has_date = any(col in data.columns for col in date_columns)
        
        if not has_date:
            logger.warning("数据中未找到日期列")
        
        # 检查数据行数
        if len(data) == 0:
            logger.warning("数据为空")
            return False
        
        logger.info(f"数据验证通过: {len(data)} 行, {len(data.columns)} 列")
        return True
    
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        if data is None or data.empty:
            return data
        
        # 处理日期索引
        if isinstance(data.index, pd.DatetimeIndex):
            # 如果索引是日期，将其转为列
            data = data.reset_index()
        elif data.index.name == 'date' or (isinstance(data.index, pd.Index) and hasattr(data.index, 'name') and data.index.name == 'date'):
            # 如果索引名为date，也重置索引
            data = data.reset_index()
        
        # 确保有date列
        if 'date' not in data.columns:
            # 检查是否有月份或季度列
            if '月份' in data.columns:
                # 处理月份格式，如"2025年07月份"
                data['date'] = data['月份'].apply(self.parse_month_format)
            elif '季度' in data.columns:
                # 处理季度格式，如"2025年第1季度"
                data['date'] = data['季度'].apply(self.parse_quarter_format)
            else:
                # 寻找可能的日期列
                for col in data.columns:
                    if data[col].dtype == 'datetime64[ns]' or 'date' in col.lower():
                        data = data.rename(columns={col: 'date'})
                        break
                else:
                    # 如果还是没有找到，检查第一列是否可以转为日期
                    if len(data.columns) > 0:
                        first_col = data.columns[0]
                        try:
                            pd.to_datetime(data[first_col])
                            data = data.rename(columns={first_col: 'date'})
                        except:
                            pass
        
        # 标准化日期列名
        date_columns = ['Date', 'DATE', '日期', 'index']
        for col in date_columns:
            if col in data.columns:
                data = data.rename(columns={col: 'date'})
                break
        
        # 转换日期格式
        if 'date' in data.columns:
            try:
                data['date'] = pd.to_datetime(data['date'])
            except Exception as e:
                logger.warning(f"日期转换失败: {e}")
        
        # 去除重复行
        original_len = len(data)
        data = data.drop_duplicates()
        if len(data) < original_len:
            logger.info(f"移除了 {original_len - len(data)} 行重复数据")
        
        # 按日期排序
        if 'date' in data.columns:
            data = data.sort_values('date')
        
        return data
        
    def parse_month_format(self, month_str):
        """解析月份格式，如'2025年07月份'"""
        try:
            if pd.isna(month_str) or not month_str:
                return None
                
            month_str = str(month_str).strip()
            
            # 处理"2025年07月份"格式
            if '年' in month_str and '月' in month_str:
                parts = month_str.split('年')
                year = int(parts[0])
                
                month_part = parts[1].split('月')[0]
                month = int(month_part)
                
                return f'{year}-{month:02d}-01'
            
            logger.warning(f"无法解析月份格式: {month_str}")
            return None
            
        except Exception as e:
            logger.error(f"月份解析错误: {e}")
            return None
            
    def parse_quarter_format(self, quarter_str):
        """解析季度格式，如'2025年第1季度'"""
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
                
                return f'{year}-{month:02d}-01'
            
            logger.warning(f"无法解析季度格式: {quarter_str}")
            return None
            
        except Exception as e:
            logger.error(f"季度解析错误: {e}")
            return None
