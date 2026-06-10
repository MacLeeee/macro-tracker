"""
M1M2剪刀差与中证500 PE流动性页面
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta

from ..data_fetcher.m1m2_scissors_indicator import M1M2ScissorsIndicator
from ..database.db_manager import DatabaseManager


def show_m1m2_scissors_indicator():
    """显示M1M2剪刀差与中证500 PE流动性指标页面"""
    
    st.title("🪙 M1M2剪刀差与中证500估值分析")
    
    # 获取数据库管理器
    try:
        db_manager = DatabaseManager()
        scissors_indicator = M1M2ScissorsIndicator(db_manager)
    except Exception as e:
        st.error(f"数据库连接失败: {e}")
        return
    
    # 数据更新控制
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 更新数据", key="update_m1m2_data"):
            with st.spinner("正在更新M1M2剪刀差数据..."):
                try:
                    success = scissors_indicator.ensure_source_data()
                    if success:
                        st.success("数据更新成功！")
                        st.rerun()
                    else:
                        st.error("数据更新失败")
                except Exception as e:
                    st.error(f"数据更新错误: {e}")
    
    # 获取计算结果
    try:
        scissors_data = scissors_indicator.calculate_m1m2_scissors()
        
        if scissors_data.empty:
            st.warning("暂无M1M2剪刀差数据，请先更新数据")
            return
            
    except Exception as e:
        st.error(f"M1M2剪刀差计算失败: {e}")
        return
    
    # 显示数据概览
    with col1:
        st.subheader("📊 数据概览")
        
        col_a, col_b, col_c, col_d = st.columns(4)
        
        latest_data = scissors_data.iloc[-1]
        
        with col_a:
            m1_growth = latest_data.get('m1_growth', 0)
            st.metric("M1增长率", f"{m1_growth:.1f}%")
        
        with col_b:
            m2_growth = latest_data.get('m2_growth', 0)
            st.metric("M2增长率", f"{m2_growth:.1f}%")
        
        with col_c:
            scissors = latest_data.get('m1m2_scissors', 0)
            st.metric("M1M2剪刀差", f"{scissors:.1f}%")
        
        with col_d:
            if 'pe_ratio' in scissors_data.columns:
                pe_ratio = latest_data.get('pe_ratio', 0)
                st.metric("中证500 PE", f"{pe_ratio:.1f}倍")
            elif 'valuation_proxy' in scissors_data.columns:
                val_proxy = latest_data.get('valuation_proxy', 1) 
                st.metric("估值代理", f"{val_proxy:.2f}")
    
    # 时间范围选择
    st.subheader("📅 时间范围选择")
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "开始日期",
            value=datetime.now() - timedelta(days=365*5),  # 默认5年
            key="m1m2_start_date"
        )
    
    with col2:
        end_date = st.date_input(
            "结束日期", 
            value=datetime.now(),
            key="m1m2_end_date"
        )
    
    # 过滤数据
    scissors_data['date'] = pd.to_datetime(scissors_data['date'])
    filtered_data = scissors_data[
        (scissors_data['date'] >= pd.to_datetime(start_date)) &
        (scissors_data['date'] <= pd.to_datetime(end_date))
    ].copy()
    
    if filtered_data.empty:
        st.warning("所选时间范围内无数据")
        return
    
    # 主图表：M1M2剪刀差与估值对比
    st.subheader("📈 M1M2剪刀差与中证500估值对比")
    
    # 创建双轴图表
    fig = make_subplots(
        rows=1, cols=1,
        specs=[[{"secondary_y": True}]],
        subplot_titles=["M1M2剪刀差 vs 中证500估值"]
    )
    
    # M1增长率
    fig.add_trace(
        go.Scatter(
            x=filtered_data['date'],
            y=filtered_data['m1_growth'],
            name="M1增长率",
            line=dict(color='blue', width=2),
            opacity=0.7
        ),
        secondary_y=False
    )
    
    # M2增长率
    fig.add_trace(
        go.Scatter(
            x=filtered_data['date'],
            y=filtered_data['m2_growth'],
            name="M2增长率",
            line=dict(color='green', width=2),
            opacity=0.7
        ),
        secondary_y=False
    )
    
    # M1M2剪刀差
    fig.add_trace(
        go.Scatter(
            x=filtered_data['date'],
            y=filtered_data['m1m2_scissors'],
            name="M1M2剪刀差",
            line=dict(color='red', width=3),
            fill='tonexty' if len(filtered_data) > 1 else None,
            fillcolor='rgba(255, 0, 0, 0.1)'
        ),
        secondary_y=False
    )
    
    # 添加零线
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, secondary_y=False)
    
    # 中证500估值（右轴）
    if 'pe_ratio' in filtered_data.columns:
        pe_data = filtered_data.dropna(subset=['pe_ratio'])
        if not pe_data.empty:
            fig.add_trace(
                go.Scatter(
                    x=pe_data['date'],
                    y=pe_data['pe_ratio'],
                    name="中证500 PE",
                    line=dict(color='orange', width=2),
                    yaxis='y2'
                ),
                secondary_y=True
            )
    elif 'valuation_proxy' in filtered_data.columns:
        val_data = filtered_data.dropna(subset=['valuation_proxy'])
        if not val_data.empty:
            fig.add_trace(
                go.Scatter(
                    x=val_data['date'],
                    y=val_data['valuation_proxy'],
                    name="估值代理",
                    line=dict(color='orange', width=2),
                    yaxis='y2'
                ),
                secondary_y=True
            )
    
    # 设置Y轴标签
    fig.update_yaxes(title_text="增长率 (%)", secondary_y=False)
    if 'pe_ratio' in filtered_data.columns:
        fig.update_yaxes(title_text="市盈率 (倍)", secondary_y=True)
    else:
        fig.update_yaxes(title_text="估值指标", secondary_y=True)
    
    # 更新布局
    fig.update_layout(
        title="M1M2剪刀差与中证500估值走势",
        height=600,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 分析说明
    st.subheader("📋 指标说明")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **M1M2剪刀差含义：**
        - M1M2剪刀差 = M1增长率 - M2增长率
        - 正值：流动性充裕，资金活跃
        - 负值：流动性收紧，资金沉淀
        - 扩大：流动性改善趋势
        - 收窄：流动性收紧趋势
        """)
    
    with col2:
        st.markdown("""
        **投资含义：**
        - 剪刀差扩大 + PE下降：投资机会出现
        - 剪刀差收窄 + PE上升：投资风险增加
        - 剪刀差领先PE变化约3-6个月
        - 配合其他指标综合判断
        """)
    
    # 相关性分析
    if 'pe_ratio' in filtered_data.columns or 'valuation_proxy' in filtered_data.columns:
        st.subheader("📊 相关性分析")
        
        # 计算相关性
        val_col = 'pe_ratio' if 'pe_ratio' in filtered_data.columns else 'valuation_proxy'
        correlation_data = filtered_data[['m1m2_scissors', val_col]].dropna()
        
        if len(correlation_data) > 10:
            # 当期相关性
            current_corr = correlation_data['m1m2_scissors'].corr(correlation_data[val_col])
            
            # 滞后相关性分析
            lags = list(range(-6, 7))  # -6到+6个月
            correlations = []
            
            for lag in lags:
                if lag == 0:
                    corr = correlation_data['m1m2_scissors'].corr(correlation_data[val_col])
                elif lag > 0:
                    # 剪刀差领先估值
                    corr = correlation_data['m1m2_scissors'].shift(lag).corr(correlation_data[val_col])
                else:
                    # 估值领先剪刀差
                    corr = correlation_data['m1m2_scissors'].corr(correlation_data[val_col].shift(-lag))
                
                correlations.append(corr if not pd.isna(corr) else 0)
            
            # 找到最强相关性
            max_corr_idx = max(range(len(correlations)), key=lambda i: abs(correlations[i]))
            max_corr = correlations[max_corr_idx]
            max_lag = lags[max_corr_idx]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("当期相关性", f"{current_corr:.3f}")
            
            with col2:
                st.metric("最强相关性", f"{max_corr:.3f}")
            
            with col3:
                if max_lag > 0:
                    st.metric("领先关系", f"剪刀差领先{max_lag}月")
                elif max_lag < 0:
                    st.metric("领先关系", f"估值领先{-max_lag}月")
                else:
                    st.metric("领先关系", "同步变化")
            
            # 滞后相关性图表
            lag_fig = go.Figure()
            lag_fig.add_trace(
                go.Scatter(
                    x=lags,
                    y=correlations,
                    mode='lines+markers',
                    name='相关系数',
                    line=dict(color='blue', width=2),
                    marker=dict(size=8)
                )
            )
            
            lag_fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            lag_fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
            
            lag_fig.update_layout(
                title="M1M2剪刀差与估值的滞后相关性",
                xaxis_title="滞后期数 (月)",
                yaxis_title="相关系数",
                height=400
            )
            
            st.plotly_chart(lag_fig, use_container_width=True)
    
    # 数据表格
    with st.expander("📋 查看原始数据"):
        st.dataframe(
            filtered_data.round(3),
            use_container_width=True
        )
