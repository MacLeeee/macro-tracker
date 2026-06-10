"""
Streamlit Dashboard 主应用
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os
from io import BytesIO

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.data_fetcher.data_manager import data_manager
from src.utils.config import config_manager

# 页面配置
st.set_page_config(
    page_title="宏观经济数据库",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin-bottom: 1rem;
    }
    .sidebar-section {
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

def main():
    """主应用函数"""
    
    # 页面标题
    st.markdown('<h1 class="main-header">📊 宏观经济数据库</h1>', unsafe_allow_html=True)
    
    # 页面导航
    page = st.sidebar.selectbox(
        "📍 选择页面",
        ["🏠 首页", "💧 全球流动性指标", "🇨🇳 中国超额流动性", "📦 中国基本面数据", "🚢 贸易出口数据", "🇺🇸 美国基本面数据", "🛠️ 指标管理"],
        index=0
    )
    
    if page == "🏠 首页":
        from src.dashboard.home_page import show_home_page
        show_home_page()
        return
    elif page == "💧 全球流动性指标":
        from src.dashboard.liquidity_page import show_liquidity_indicator
        show_liquidity_indicator()
        return
    elif page == "🇨🇳 中国超额流动性":
        from src.dashboard.china_liquidity_page import show_china_liquidity_indicator
        show_china_liquidity_indicator()
        return
    elif page == "📦 中国基本面数据":
        from src.dashboard.china_fundamentals_page import show_china_fundamentals
        show_china_fundamentals()
        return
    elif page == "🚢 贸易出口数据":
        from src.dashboard.trade_export_page import show_trade_export
        show_trade_export()
        return
    elif page == "🇺🇸 美国基本面数据":
        from src.dashboard.us_fundamentals_page import show_us_fundamentals
        show_us_fundamentals()
        return
    elif page == "🛠️ 指标管理":
        from src.dashboard.indicator_manager import show_indicator_manager
        show_indicator_manager()
        return
    
    # 侧边栏
    with st.sidebar:
        st.markdown("### 🔧 控制面板")
        
        # 数据更新部分
        st.markdown("#### 数据管理")
        
        if st.button("🔄 更新所有数据", type="primary"):
            with st.spinner("正在更新数据..."):
                results = data_manager.update_all_indicators(force_update=True)
                successful = sum(results.values())
                total = len(results)
                
                if successful > 0:
                    st.success(f"✅ 成功更新 {successful}/{total} 个指标")
                else:
                    st.error("❌ 数据更新失败")
        
        # 指标选择
        st.markdown("#### 指标选择")
        available_indicators = data_manager.list_available_indicators()
        enabled_indicators = {k: v for k, v in available_indicators.items() 
                            if v.get('enabled', False)}
        
        if enabled_indicators:
            selected_indicator = st.selectbox(
                "选择指标",
                options=list(enabled_indicators.keys()),
                format_func=lambda x: enabled_indicators[x].get('name', x)
            )
        else:
            st.warning("⚠️ 暂无已启用的指标")
            selected_indicator = None
        
        # 时间范围选择
        st.markdown("#### 时间范围")
        date_range = st.date_input(
            "选择日期范围",
            value=(datetime.now() - timedelta(days=365), datetime.now()),
            max_value=datetime.now()
        )
    
    # 默认显示欢迎页面
    display_welcome_page()

def display_welcome_page():
    """显示欢迎页面"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        ### 🎯 欢迎使用宏观经济数据库系统
        
        这是一个基于 **AkShare** 和 **OpenBB** 的宏观经济数据收集、存储和可视化系统。
        
        #### 🚀 快速开始
        1. 在左侧控制面板添加或启用数据指标
        2. 点击"更新所有数据"获取最新数据  
        3. 选择指标查看数据可视化
        
        #### 💡 系统特点
        - **模块化设计**: 易于添加新的数据源和指标
        - **自动化更新**: 支持定时数据更新
        - **灵活配置**: 通过配置文件管理数据指标
        - **实时可视化**: 交互式图表展示
        """)
        
        # 显示系统状态
        st.markdown("#### 📈 系统状态")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            available_indicators = data_manager.list_available_indicators()
            enabled_count = sum(1 for v in available_indicators.values() if v.get('enabled', False))
            st.metric("已启用指标", enabled_count)
        
        with col_b:
            # 获取数据表数量
            from src.database.db_manager import db_manager
            tables = db_manager.list_tables()
            st.metric("数据表数量", len(tables))
        
        with col_c:
            # 显示数据源状态
            akshare_available = 'akshare' in data_manager.fetchers
            openbb_available = 'openbb' in data_manager.fetchers
            sources_count = akshare_available + openbb_available
            st.metric("可用数据源", sources_count)

def display_indicator_dashboard(indicator_key: str, indicator_config: dict, date_range):
    """显示指标仪表板"""
    
    # 指标信息
    st.markdown(f"### 📊 {indicator_config.get('name', indicator_key)}")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown(f"**描述**: {indicator_config.get('description', '暂无描述')}")
    
    with col2:
        st.markdown(f"**数据源**: {indicator_config.get('source', '未知').upper()}")
    
    with col3:
        st.markdown(f"**更新频率**: {indicator_config.get('update_frequency', '未知')}")
    
    # 获取数据
    start_date = date_range[0].strftime('%Y-%m-%d') if len(date_range) > 0 else None
    end_date = date_range[1].strftime('%Y-%m-%d') if len(date_range) > 1 else None
    
    data = data_manager.get_indicator_data(indicator_key, start_date, end_date)
    
    if data is None or data.empty:
        st.warning("⚠️ 暂无数据，请先更新数据")
        return
    
    # 数据概览
    st.markdown("#### 📋 数据概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("数据行数", len(data))
    
    with col2:
        st.metric("数据列数", len(data.columns))
    
    with col3:
        if 'date' in data.columns:
            st.metric("最早日期", data['date'].min().strftime('%Y-%m-%d'))
    
    with col4:
        if 'date' in data.columns:
            st.metric("最新日期", data['date'].max().strftime('%Y-%m-%d'))
    
    # 数据可视化
    st.markdown("#### 📈 数据可视化")
    
    # 自动生成图表
    if 'date' in data.columns:
        # 时间序列图表
        numeric_columns = data.select_dtypes(include=['number']).columns.tolist()
        
        if numeric_columns:
            # 多选框选择要显示的列
            selected_columns = st.multiselect(
                "选择要显示的数据列",
                numeric_columns,
                default=numeric_columns[:3] if len(numeric_columns) >= 3 else numeric_columns
            )
            
            if selected_columns:
                # 创建时间序列图
                fig = go.Figure()
                
                for col in selected_columns:
                    fig.add_trace(go.Scatter(
                        x=data['date'],
                        y=data[col],
                        mode='lines',
                        name=col,
                        line=dict(width=2)
                    ))
                
                fig.update_layout(
                    title=f"{indicator_config.get('name', indicator_key)} - 时间序列",
                    xaxis_title="日期",
                    yaxis_title="数值",
                    hovermode='x unified',
                    template='plotly_white',
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 统计信息
                st.markdown("#### 📊 统计信息")
                st.dataframe(data[selected_columns].describe(), use_container_width=True)
    
    # 原始数据表格
    st.markdown("#### 📋 原始数据")
    
    # 分页显示
    page_size = 50
    total_pages = (len(data) - 1) // page_size + 1
    
    if total_pages > 1:
        page = st.selectbox("选择页码", range(1, total_pages + 1)) - 1
        start_idx = page * page_size
        end_idx = start_idx + page_size
        display_data = data.iloc[start_idx:end_idx]
    else:
        display_data = data
    
    st.dataframe(display_data, use_container_width=True)
    
    # 数据下载
    st.markdown("#### 💾 数据下载")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 下载 CSV",
            data=csv,
            file_name=f"{indicator_key}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col2:
        excel_buffer = BytesIO()
        data.to_excel(excel_buffer, index=False)
        st.download_button(
            label="📊 下载 Excel",
            data=excel_buffer.getvalue(),
            file_name=f"{indicator_key}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"应用启动失败: {e}")
        st.markdown("请检查配置文件和依赖包是否正确安装")
