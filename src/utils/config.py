"""
配置文件管理模块
"""
import yaml
import os
from pathlib import Path
from loguru import logger

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.indicators_config = None
        self.data_sources_config = None
        self.load_configs()
    
    def load_configs(self):
        """加载所有配置文件"""
        try:
            # 加载指标配置
            indicators_path = self.config_dir / "indicators.yaml"
            with open(indicators_path, 'r', encoding='utf-8') as f:
                self.indicators_config = yaml.safe_load(f)
            
            # 加载数据源配置
            data_sources_path = self.config_dir / "data_sources.yaml"
            with open(data_sources_path, 'r', encoding='utf-8') as f:
                self.data_sources_config = yaml.safe_load(f)
            
            logger.info("配置文件加载成功")
            
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            raise
    
    def get_indicators(self) -> dict:
        """获取所有启用的指标配置"""
        if not self.indicators_config:
            return {}
        
        enabled_indicators = {}
        for key, config in self.indicators_config.get('indicators', {}).items():
            if config.get('enabled', True):
                enabled_indicators[key] = config
        
        return enabled_indicators
    
    def get_indicator(self, indicator_key: str) -> dict:
        """获取特定指标配置"""
        indicators = self.get_indicators()
        return indicators.get(indicator_key, {})
    
    def get_data_source(self, source_name: str) -> dict:
        """获取数据源配置"""
        if not self.data_sources_config:
            return {}
        
        return self.data_sources_config.get('data_sources', {}).get(source_name, {})
    
    def get_database_config(self) -> dict:
        """获取数据库配置"""
        if not self.data_sources_config:
            return {}
        
        return self.data_sources_config.get('database', {})
    
    def add_indicator(self, indicator_key: str, config: dict):
        """添加新指标配置"""
        if not self.indicators_config:
            self.indicators_config = {'indicators': {}}
        
        self.indicators_config['indicators'][indicator_key] = config
        self.save_indicators_config()
        logger.info(f"新增指标配置: {indicator_key}")
    
    def save_indicators_config(self):
        """保存指标配置到文件"""
        indicators_path = self.config_dir / "indicators.yaml"
        with open(indicators_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.indicators_config, f, allow_unicode=True, default_flow_style=False)

# 全局配置管理器实例
config_manager = ConfigManager()
