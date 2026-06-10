"""
数据库管理模块
"""
import sqlite3
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from loguru import logger
from typing import Optional, List, Dict, Any
import os

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "data/macro_economy.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f'sqlite:///{self.db_path}')
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        try:
            # 创建数据指标元信息表
            with self.engine.connect() as conn:
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS indicator_meta (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        indicator_key TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT,
                        source TEXT NOT NULL,
                        table_name TEXT NOT NULL,
                        last_update TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                '''))
                conn.commit()
            
            logger.info("数据库初始化完成")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def save_data(self, data: pd.DataFrame, table_name: str, 
                  if_exists: str = 'replace') -> bool:
        """保存数据到数据库"""
        try:
            # 确保日期列正确处理
            if 'date' in data.columns:
                data['date'] = pd.to_datetime(data['date'])
            
            # 保存数据
            data.to_sql(table_name, self.engine, if_exists=if_exists, 
                       index=False, method='multi')
            
            logger.info(f"数据已保存到表: {table_name}, 行数: {len(data)}")
            return True
            
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            return False
    
    def load_data(self, table_name: str, 
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """从数据库加载数据"""
        try:
            query = f"SELECT * FROM {table_name}"
            conditions = []
            
            if start_date:
                conditions.append(f"date >= '{start_date}'")
            if end_date:
                conditions.append(f"date <= '{end_date}'")
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY date"
            
            data = pd.read_sql(query, self.engine)
            
            # 转换日期列 - 使用更宽松的解析方式
            if 'date' in data.columns:
                try:
                    # 先尝试直接转换
                    data['date'] = pd.to_datetime(data['date'], errors='coerce')
                except Exception:
                    # 如果失败，尝试作为字符串处理
                    try:
                        data['date'] = pd.to_datetime(data['date'].astype(str), errors='coerce')
                    except Exception:
                        # 最后尝试，忽略错误
                        data['date'] = pd.to_datetime(data['date'], errors='coerce', infer_datetime_format=True)
            
            logger.info(f"从表 {table_name} 加载数据: {len(data)} 行")
            return data
            
        except Exception as e:
            error_msg = str(e)
            # 表不存在是预期情况，使用DEBUG级别
            if "no such table" in error_msg.lower():
                logger.debug(f"表 {table_name} 不存在，将尝试其他数据源")
            else:
                logger.error(f"加载数据失败: {e}")
            return None
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表信息"""
        try:
            with self.engine.connect() as conn:
                # 获取表结构
                result = conn.execute(text(f"PRAGMA table_info({table_name})"))
                columns = [row[1] for row in result.fetchall()]
                
                # 获取行数
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                row_count = result.fetchone()[0]
                
                # 获取最新和最早日期
                if 'date' in columns:
                    result = conn.execute(text(f"SELECT MIN(date), MAX(date) FROM {table_name}"))
                    min_date, max_date = result.fetchone()
                else:
                    min_date, max_date = None, None
            
            return {
                'columns': columns,
                'row_count': row_count,
                'min_date': min_date,
                'max_date': max_date
            }
            
        except Exception as e:
            logger.error(f"获取表信息失败: {e}")
            return {}
    
    def list_tables(self) -> List[str]:
        """列出所有数据表"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name != 'indicator_meta'"
                ))
                tables = [row[0] for row in result.fetchall()]
            
            return tables
            
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return []
    
    def register_indicator(self, indicator_key: str, name: str, 
                          description: str, source: str, table_name: str):
        """注册指标元信息"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text('''
                    INSERT OR REPLACE INTO indicator_meta 
                    (indicator_key, name, description, source, table_name, last_update)
                    VALUES (:key, :name, :desc, :source, :table, CURRENT_TIMESTAMP)
                '''), {"key": indicator_key, "name": name, "desc": description,
                       "source": source, "table": table_name})
                conn.commit()
            
            logger.info(f"指标 {indicator_key} 已注册")
            
        except Exception as e:
            logger.error(f"注册指标失败: {e}")
    
    def update_indicator_timestamp(self, indicator_key: str):
        """更新指标的最后更新时间"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text('''
                    UPDATE indicator_meta 
                    SET last_update = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE indicator_key = :key
                '''), {"key": indicator_key})
                conn.commit()
            
        except Exception as e:
            logger.error(f"更新指标时间戳失败: {e}")

# 全局数据库管理器实例
db_manager = DatabaseManager()
