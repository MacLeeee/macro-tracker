"""
中国超额流动性指标页面
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# 导入社融/GDP指标
from src.data_fetcher.social_financing_indicator import init_social_financing_indicator
from src.database.db_manager import db_manager as _global_db

def show_china_liquidity_indicator():
    """显示中国超额流动性指标页面"""
    
    st.markdown("### 🇨🇳 中国流动性指标分析")
    st.markdown("**超额流动性 = M2同比增长率 - 工业增加值增长率 | M1M2剪刀差 = M1增长率 - M2增长率**")
    
    try:
        from src.data_fetcher.china_liquidity_indicator import china_liquidity_indicator
        from src.database.db_manager import db_manager
        
        # 控制面板
        col1, col2 = st.columns([3, 1])
        
        with col2:
            if st.button("🔄 更新数据", type="primary"):
                with st.spinner("正在更新流动性指标数据..."):
                    result = china_liquidity_indicator.update_and_calculate(force_update=True)
                    if result is not None:
                        st.success("✅ 数据更新成功!")
                        st.rerun()
                    else:
                        st.error("❌ 数据更新失败!")
        
        # 获取中国超额流动性指标数据
        china_liquidity_data = db_manager.load_data("china_excess_liquidity")
        
        if china_liquidity_data is None or china_liquidity_data.empty:
            st.warning("⚠️ 暂无中国超额流动性指标数据")
            
            # 显示快速开始指南
            st.markdown("#### 🚀 快速开始")
            st.markdown("""
            1. 点击上方"更新数据"按钮，系统将自动：
               - 获取中国M2货币供应量数据
               - 获取中国工业增加值数据  
               - 计算超额流动性指标
            2. 数据获取完成后，将显示超额流动性指标图表
            3. 该指标以月度频率更新
            """)
            
            if st.button("🎯 立即开始获取数据", type="primary"):
                with st.spinner("正在获取数据..."):
                    result = china_liquidity_indicator.update_and_calculate(force_update=True)
                    if result is not None:
                        st.success("✅ 数据获取成功!")
                        st.rerun()
                    else:
                        st.error("❌ 数据获取失败，请检查网络连接或数据源配置")
            
            return
        
        # 获取最新值
        latest_values = china_liquidity_indicator.get_latest_values(china_liquidity_data)
        
        # 时间范围选择
        min_date = china_liquidity_data['date'].min().date()
        max_date = china_liquidity_data['date'].max().date()
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "开始日期",
                value=max(min_date, max_date - timedelta(days=365*3)),  # 默认显示3年
                min_value=min_date,
                max_value=max_date
            )
        
        with col2:
            end_date = st.date_input(
                "结束日期", 
                value=max_date,
                min_value=min_date,
                max_value=max_date
            )
        
        # 筛选数据
        filtered_data = china_liquidity_data[
            (china_liquidity_data['date'].dt.date >= start_date) &
            (china_liquidity_data['date'].dt.date <= end_date)
        ].copy()
        
        if filtered_data.empty:
            st.warning("所选时间范围内无数据")
            return
        
        # 主要图表
        st.markdown("#### 📈 超额流动性指标 vs 中证2000/沪深300比值")
        
        # 检查是否有股票指数比值数据
        has_stock_ratio = 'zz2000_hs300_ratio' in filtered_data.columns and not filtered_data['zz2000_hs300_ratio'].isna().all()
        
        if has_stock_ratio:
            # 双坐标轴图表：超额流动性指标 vs 中证2000/沪深300比值
            fig_dual = go.Figure()
            
            # 添加超额流动性指标（左坐标轴）
            fig_dual.add_trace(
                go.Scatter(
                    x=filtered_data['date'],
                    y=filtered_data['china_excess_liquidity'],
                    mode='lines',
                    name='超额流动性指标',
                    line=dict(color='#e74c3c', width=3),
                    yaxis='y',
                    hovertemplate='日期: %{x}<br>超额流动性: %{y:.2f}%<extra></extra>'
                )
            )
            
            # 添加6个月移动平均线
            if 'excess_liquidity_ma6' in filtered_data.columns:
                fig_dual.add_trace(
                    go.Scatter(
                        x=filtered_data['date'],
                        y=filtered_data['excess_liquidity_ma6'],
                        mode='lines',
                        name='超额流动性6月均线',
                        line=dict(color='orange', width=1, dash='dash'),
                        yaxis='y',
                        hovertemplate='日期: %{x}<br>6月均线: %{y:.2f}%<extra></extra>'
                    )
                )
            
            # 添加中证2000/沪深300比值（右坐标轴）
            fig_dual.add_trace(
                go.Scatter(
                    x=filtered_data['date'],
                    y=filtered_data['zz2000_hs300_ratio'],
                    mode='lines',
                    name='中证2000/沪深300',
                    line=dict(color='#3498db', width=2),
                    yaxis='y2',
                    hovertemplate='日期: %{x}<br>比值: %{y:.3f}<extra></extra>'
                )
            )
            
            # 添加比值移动平均线
            if 'ratio_ma6' in filtered_data.columns:
                fig_dual.add_trace(
                    go.Scatter(
                        x=filtered_data['date'],
                        y=filtered_data['ratio_ma6'],
                        mode='lines',
                        name='比值6月均线',
                        line=dict(color='#2ecc71', width=1, dash='dot'),
                        yaxis='y2',
                        hovertemplate='日期: %{x}<br>比值6月均线: %{y:.3f}<extra></extra>'
                    )
                )
            
            # 更新布局
            fig_dual.update_layout(
                title='中国超额流动性指标 vs 中证2000/沪深300比值',
                xaxis_title='日期',
                yaxis=dict(
                    title='超额流动性 (%)',
                    side='left',
                    color='#e74c3c'
                ),
                yaxis2=dict(
                    title='中证2000/沪深300比值',
                    side='right',
                    overlaying='y',
                    color='#3498db'
                ),
                height=500,
                template='plotly_white',
                legend=dict(x=0.01, y=0.99)
            )
            
            # 添加零线
            fig_dual.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.5)
            
            st.plotly_chart(fig_dual, use_container_width=True)

        # ======================
        # M1/M2 剪刀差 子板块
        # ======================
        st.markdown("---")
        st.markdown("#### ✂️ M1/M2 剪刀差 与 中证500 对比")

        # 切换显示开关与右轴选择
        col_left, col_right = st.columns([2, 1])
        with col_right:
            valuation_choice = st.radio(
                "右轴显示",
                options=["指数(收盘)", "滚动PE"],
                index=0,
                horizontal=True,
                help="优先使用指数收盘；如选择滚动PE而数据较旧，将自动回退到指数"
            )

        # 计算剪刀差数据
        from src.data_fetcher.m1m2_scissors_indicator import M1M2ScissorsIndicator
        from src.database.db_manager import db_manager as _global_db
        try:
            scissors_indicator = M1M2ScissorsIndicator(_global_db)
            scissors_df = scissors_indicator.calculate_m1m2_scissors()
        except Exception as _e:
            st.warning(f"M1/M2剪刀差数据计算失败: {_e}")
            scissors_df = None

        if scissors_df is not None and not scissors_df.empty:
            # 对齐所选日期范围
            s_filtered = scissors_df[(scissors_df['date'].dt.date >= start_date) & (scissors_df['date'].dt.date <= end_date)].copy()
            if s_filtered.empty:
                st.info("所选时间范围内无剪刀差数据")
            else:
                # 构建双轴图
                fig_scissors = go.Figure()

                # 左轴：M1、M2、剪刀差
                fig_scissors.add_trace(go.Scatter(x=s_filtered['date'], y=s_filtered['m1_growth'], name='M1增长率', line=dict(color='blue', width=2)))
                fig_scissors.add_trace(go.Scatter(x=s_filtered['date'], y=s_filtered['m2_growth'], name='M2增长率', line=dict(color='green', width=2)))
                fig_scissors.add_trace(go.Scatter(x=s_filtered['date'], y=s_filtered['m1m2_scissors'], name='M1/M2剪刀差', line=dict(color='red', width=3)))

                # 右轴：根据切换选择显示滚动PE或指数
                right_series = None
                right_name = None
                if valuation_choice == "滚动PE" and 'pe_ratio' in s_filtered.columns and not s_filtered['pe_ratio'].isna().all():
                    right_series = s_filtered['pe_ratio']
                    right_name = '中证500 滚动PE'
                elif 'close' in s_filtered.columns and not s_filtered['close'].isna().all():
                    right_series = s_filtered['close']
                    right_name = '中证500 指数(收盘)'
                elif 'valuation_proxy' in s_filtered.columns and not s_filtered['valuation_proxy'].isna().all():
                    right_series = s_filtered['valuation_proxy']
                    right_name = '中证500 估值代理'

                if right_series is not None:
                    fig_scissors.add_trace(go.Scatter(x=s_filtered['date'], y=right_series, name=right_name, yaxis='y2', line=dict(color='orange', width=2)))

                # 轴与布局
                fig_scissors.update_layout(
                    title='M1/M2剪刀差 与 中证500 对比 (双轴)',
                    xaxis=dict(title='日期'),
                    yaxis=dict(title='增速 / 剪刀差 (%)'),
                    yaxis2=dict(title='指数 / 估值', overlaying='y', side='right'),
                    height=520,
                    template='plotly_white',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )

                fig_scissors.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.5)
                st.plotly_chart(fig_scissors, use_container_width=True)
        else:
            st.info("暂无M1/M2剪刀差数据，请在首页或此处先更新相关数据后再查看。")
            
        # ======================
        # 社融/GDP 与 沪深300 子板块
        # ======================
        st.markdown("---")
        st.markdown("### 📈 社融同比增长率 与 沪深300指数对比")
        
        # 初始化社融/GDP指标
        sf_indicator = init_social_financing_indicator(_global_db)
        
        # 更新按钮
        col_sf_left, col_sf_right = st.columns([3, 1])
        with col_sf_right:
            if st.button("🔄 更新社融数据", key="update_sf_data"):
                with st.spinner("正在更新社融/GDP数据..."):
                    try:
                        result = sf_indicator.update_and_calculate(force_update=True)
                        if result is not None and not result.empty:
                            st.success("✅ 社融/GDP数据更新成功!")
                            st.rerun()
                        else:
                            st.error("❌ 社融/GDP数据更新失败!")
                    except Exception as e:
                        st.error(f"❌ 数据更新错误: {e}")
        
        # 计算社融/GDP数据
        sf_gdp_data, message = sf_indicator.calculate_social_financing_gdp()
        
        if sf_gdp_data.empty:
            st.warning(f"⚠️ {message}")
            st.info("请点击上方「更新社融数据」按钮获取数据")
        else:
            # 对齐所选日期范围
            sf_filtered = sf_gdp_data[(sf_gdp_data['date'].dt.date >= start_date) & (sf_gdp_data['date'].dt.date <= end_date)].copy()
            
            if sf_filtered.empty:
                st.info("所选时间范围内无社融/GDP数据")
            else:
                # 构建双轴图
                fig_sf_hs300 = go.Figure()
                
                # 左轴：社融同比增长率
                fig_sf_hs300.add_trace(go.Scatter(
                    x=sf_filtered['date'], 
                    y=sf_filtered['social_financing_gdp_ratio'], 
                    name='社融同比增长率', 
                    line=dict(color='red', width=3),
                    hovertemplate='%{x}<br>社融同比增长: %{y:.2f}%<extra></extra>'
                ))
                
                # 添加移动平均线
                if 'sf_gdp_ratio_ma6' in sf_filtered.columns:
                    fig_sf_hs300.add_trace(go.Scatter(
                        x=sf_filtered['date'], 
                        y=sf_filtered['sf_gdp_ratio_ma6'], 
                        name='社融同比增长 6月均线', 
                        line=dict(color='orange', width=1, dash='dash'),
                        hovertemplate='%{x}<br>6月均线: %{y:.2f}%<extra></extra>'
                    ))
                
                # 右轴：沪深300指数
                if 'close' in sf_filtered.columns:
                    # 计算沪深300指数的适当显示范围
                    hs300_min = sf_filtered['close'].min()
                    hs300_max = sf_filtered['close'].max()
                    hs300_range = hs300_max - hs300_min
                    
                    # 添加沪深300指数曲线
                    fig_sf_hs300.add_trace(go.Scatter(
                        x=sf_filtered['date'], 
                        y=sf_filtered['close'], 
                        name='沪深300指数', 
                        line=dict(color='blue', width=2),
                        yaxis='y2',
                        hovertemplate='%{x}<br>沪深300: %{y:.2f}<extra></extra>'
                    ))
                
                # 计算动态轴范围以增强波动可见性
                left_series = sf_filtered['social_financing_gdp_ratio'].dropna()
                left_min, left_max = left_series.min(), left_series.max()
                left_pad = (left_max - left_min) * 0.1 if left_max > left_min else 1
                
                right_range = None
                if 'close' in sf_filtered.columns:
                    right_series = sf_filtered['close'].dropna()
                    if not right_series.empty:
                        rmin, rmax = right_series.min(), right_series.max()
                        rpad = (rmax - rmin) * 0.1 if rmax > rmin else 1
                        right_range = [rmin - rpad, rmax + rpad]

                # 更新布局（移除右轴tozero，使范围更贴合数据）
                fig_sf_hs300.update_layout(
                    title='社融同比增长率 vs 沪深300指数',
                    xaxis=dict(title='日期'),
                    yaxis=dict(title='社融同比增长率 (%)', range=[left_min - left_pad, left_max + left_pad]),
                    yaxis2=dict(
                        title='沪深300指数', 
                        overlaying='y', 
                        side='right',
                        range=right_range
                    ),
                    height=500,
                    template='plotly_white',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )
                
                st.plotly_chart(fig_sf_hs300, use_container_width=True)
                
                # 显示最新数据
                latest_sf = sf_indicator.get_latest_values(sf_filtered)
                if latest_sf:
                    st.markdown("#### 📊 最新数据")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            "社融同比增长率", 
                            f"{latest_sf.get('social_financing_gdp_ratio', 0):.2f}%",
                            delta=f"{latest_sf.get('change_1m', 0):.2f}%" if 'change_1m' in latest_sf else None
                        )
                    
                    with col2:
                        if 'social_financing' in latest_sf:
                            st.metric("社融规模(亿元)", f"{latest_sf['social_financing']:,.0f}")
                    
                    with col3:
                        if 'hs300_index' in latest_sf:
                            st.metric("沪深300指数", f"{latest_sf['hs300_index']:.2f}")
        
    except Exception as e:
        st.error(f"加载中国超额流动性指标页面失败: {e}")
        st.markdown("请检查系统配置和依赖包安装情况")