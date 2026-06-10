#!/usr/bin/env python3
"""
宏观经济数据库系统启动脚本
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    """主函数"""
    
    # 获取项目根目录
    project_root = Path(__file__).parent
    
    # 检查依赖
    print("🔍 检查系统依赖...")
    
    try:
        import streamlit
        print("✅ Streamlit 已安装")
    except ImportError:
        print("❌ Streamlit 未安装，请运行: pip install -r requirements.txt")
        return
    
    try:
        import pandas
        print("✅ Pandas 已安装")
    except ImportError:
        print("❌ Pandas 未安装，请运行: pip install -r requirements.txt")
        return
    
    # 检查配置文件
    config_dir = project_root / "config"
    if not config_dir.exists():
        print("❌ 配置目录不存在")
        return
    
    indicators_config = config_dir / "indicators.yaml"
    if not indicators_config.exists():
        print("❌ 指标配置文件不存在")
        return
    
    print("✅ 配置文件检查通过")
    
    # 创建必要目录
    data_dir = project_root / "data"
    logs_dir = project_root / "logs"
    
    data_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    
    print("✅ 目录结构检查通过")
    
    # 启动 Streamlit 应用
    app_path = project_root / "src" / "dashboard" / "app.py"
    
    print(f"🚀 启动宏观经济数据库系统...")
    print(f"📍 应用路径: {app_path}")
    print(f"🌐 浏览器将自动打开: http://localhost:8501")
    print("🔄 按 Ctrl+C 停止应用")
    print("-" * 50)
    
    try:
        # 使用 subprocess 启动 streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run", str(app_path),
            "--server.port", "8501",
            "--server.address", "localhost",
            "--server.headless", "false"
        ]
        
        subprocess.run(cmd, cwd=project_root)
        
    except KeyboardInterrupt:
        print("\n👋 应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    main()
