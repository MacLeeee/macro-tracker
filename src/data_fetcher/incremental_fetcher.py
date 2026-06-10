"""
增量数据获取器 - 支持缓存和增量下载
"""
from __future__ import annotations
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger
import sqlite3
from pathlib import Path

from .base_fetcher import BaseFetcher

class IncrementalFetcher(BaseFetcher):
    """增量数据获取器基类"""
    
    def __init__(self, source_name: str, cache_db_path: str = "data/cache.db", rate_limit: int = 10):
        super().__init__(source_name, rate_limit)
        self.cache_db_path = Path(cache_db_path)
        self.cache_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_cache_db()
    
    def init_cache_db(self):
        """初始化缓存数据库"""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                # 创建缓存元信息表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS cache_meta (
                        table_name TEXT PRIMARY KEY,
                        last_update_date TEXT,
                        total_records INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
            
            logger.info(f"缓存数据库初始化完成: {self.cache_db_path}")
            
        except Exception as e:
            logger.error(f"缓存数据库初始化失败: {e}")
            raise
    
    def get_last_update_date(self, table_name: str) -> Optional[str]:
        """获取表的最后更新日期"""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.execute(
                    "SELECT last_update_date FROM cache_meta WHERE table_name = ?",
                    (table_name,)
                )
                result = cursor.fetchone()
                
                if result and result[0]:
                    return result[0]
                
                # 如果元信息不存在，尝试从数据表中获取最新日期
                try:
                    cursor = conn.execute(f"SELECT MAX(date) FROM {table_name}")
                    result = cursor.fetchone()
                    if result and result[0]:
                        return result[0]
                except sqlite3.OperationalError:
                    # 表不存在
                    pass
                
                return None
                
        except Exception as e:
            logger.debug(f"获取最后更新日期失败: {e}")
            return None
    
    def save_cache_data(self, data: pd.DataFrame, table_name: str) -> bool:
        """保存数据到缓存"""
        try:
            if data is None or data.empty:
                logger.warning("尝试保存空数据到缓存")
                return False
            
            # 确保日期列存在且格式正确
            if 'date' not in data.columns:
                logger.error("数据中缺少日期列")
                return False
            
            data = data.copy()
            data['date'] = pd.to_datetime(data['date']).dt.strftime('%Y-%m-%d')
            
            with sqlite3.connect(self.cache_db_path) as conn:
                # 保存数据
                data.to_sql(table_name, conn, if_exists='append', index=False)
                
                # 更新元信息
                max_date = data['date'].max()
                record_count = len(data)
                
                conn.execute('''
                    INSERT OR REPLACE INTO cache_meta 
                    (table_name, last_update_date, total_records, updated_at)
                    VALUES (?, ?, 
                           COALESCE((SELECT total_records FROM cache_meta WHERE table_name = ?), 0) + ?,
                           CURRENT_TIMESTAMP)
                ''', (table_name, max_date, table_name, record_count))
                
                conn.commit()
            
            logger.info(f"缓存数据保存成功: {table_name}, 新增 {record_count} 行, 最新日期: {max_date}")
            return True
            
        except Exception as e:
            logger.error(f"保存缓存数据失败: {e}")
            return False
    
    def load_cache_data(self, table_name: str, 
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """从缓存加载数据"""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                query = f"SELECT * FROM {table_name}"
                conditions = []
                
                if start_date:
                    conditions.append(f"date >= '{start_date}'")
                if end_date:
                    conditions.append(f"date <= '{end_date}'")
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY date"
                
                data = pd.read_sql(query, conn)
                
                if not data.empty:
                    data['date'] = pd.to_datetime(data['date'])
                    logger.info(f"从缓存加载数据: {table_name}, {len(data)} 行")
                
                return data if not data.empty else None
                
        except Exception as e:
            logger.debug(f"从缓存加载数据失败: {e}")
            return None
    
    def get_incremental_date_range(self, table_name: str, 
                                  default_start_date: str = "2020-01-01") -> Tuple[str, str]:
        """获取增量更新的日期范围"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 获取最后更新日期
        last_date = self.get_last_update_date(table_name)
        
        if last_date:
            # 从最后更新日期的下一天开始
            last_datetime = datetime.strptime(last_date, '%Y-%m-%d')
            start_date = (last_datetime + timedelta(days=1)).strftime('%Y-%m-%d')
            
            # 如果开始日期大于等于结束日期，说明数据已是最新
            if start_date >= end_date:
                logger.info(f"表 {table_name} 数据已是最新，无需更新")
                return None, None
        else:
            start_date = default_start_date
        
        logger.info(f"增量更新日期范围: {start_date} 到 {end_date}")
        return start_date, end_date
    
    def fetch_incremental_data(self, indicator_config: Dict[str, Any], 
                             table_name: str = None) -> Optional[pd.DataFrame]:
        """增量获取数据"""
        table_name = table_name or indicator_config.get('table_name', 'default_table')
        
        # 获取增量日期范围
        start_date, end_date = self.get_incremental_date_range(
            table_name, 
            indicator_config.get('default_start_date', '2020-01-01')
        )
        
        if not start_date or not end_date:
            # 数据已是最新，从缓存加载
            return self.load_cache_data(table_name)
        
        # 更新指标配置中的日期参数
        params = indicator_config.get('params', {}).copy()
        params.update({
            'start_date': start_date,
            'end_date': end_date
        })
        
        updated_config = indicator_config.copy()
        updated_config['params'] = params
        
        # 获取新数据
        new_data = self.fetch_data(updated_config)
        
        if new_data is not None and not new_data.empty:
            # 保存到缓存
            if self.save_cache_data(new_data, table_name):
                # 返回全部数据（缓存中的历史数据 + 新数据）
                return self.load_cache_data(table_name)
        
        # 如果获取新数据失败，返回缓存中的数据
        cached_data = self.load_cache_data(table_name)
        if cached_data is not None:
            logger.info(f"返回缓存数据: {table_name}")
            return cached_data
        
        return None
    
    def clear_cache(self, table_name: str = None):
        """清除缓存"""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                if table_name:
                    # 清除特定表
                    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                    conn.execute("DELETE FROM cache_meta WHERE table_name = ?", (table_name,))
                    logger.info(f"已清除表 {table_name} 的缓存")
                else:
                    # 清除所有缓存
                    cursor = conn.execute("SELECT table_name FROM cache_meta")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    for table in tables:
                        conn.execute(f"DROP TABLE IF EXISTS {table}")
                    
                    conn.execute("DELETE FROM cache_meta")
                    logger.info("已清除所有缓存")
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        try:
            with sqlite3.connect(self.cache_db_path) as conn:
                cursor = conn.execute('''
                    SELECT table_name, last_update_date, total_records, 
                           created_at, updated_at 
                    FROM cache_meta 
                    ORDER BY updated_at DESC
                ''')
                
                cache_info = []
                for row in cursor.fetchall():
                    cache_info.append({
                        'table_name': row[0],
                        'last_update_date': row[1],
                        'total_records': row[2],
                        'created_at': row[3],
                        'updated_at': row[4]
                    })
                
                return {
                    'cache_db_path': str(self.cache_db_path),
                    'tables': cache_info,
                    'total_tables': len(cache_info)
                }
                
        except Exception as e:
            logger.error(f"获取缓存信息失败: {e}")
            return {}
