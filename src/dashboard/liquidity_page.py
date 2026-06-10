"""
流动性指标页面
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

def show_liquidity_indicator():
    """显示流动性指标页面"""
    
    st.markdown("### 💧 流动性前瞻指标")
    st.markdown("**流动性前瞻指标 = BTC价格 ÷ 美元指数(DXY)**")
    st.markdown("该指标通过比特币价格与美元指数的比值来衡量全球流动性状况")
    
    try:
        from src.data_fetcher.composite_indicator import liquidity_indicator
        from src.database.db_manager import db_manager
        
        # 控制面板
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.markdown("#### 📊 数据控制")
            
        with col2:
            if st.button("🔄 更新数据", type="primary"):
                with st.spinner("正在更新流动性指标数据..."):
                    result = liquidity_indicator.update_and_calculate(force_update=True)
                    if result is not None:
                        st.success("✅ 数据更新成功!")
                        st.rerun()
                    else:
                        st.error("❌ 数据更新失败!")
        
        with col3:
            show_source_data = st.checkbox("显示源数据", value=False)
        
        # 获取流动性指标数据
        liquidity_data = db_manager.load_data("liquidity_indicator")
        
        if liquidity_data is None or liquidity_data.empty:
            st.warning("⚠️ 暂无流动性指标数据")
            
            # 显示快速开始指南
            st.markdown("#### 🚀 快速开始")
            st.markdown("""
            1. 点击上方"更新数据"按钮，系统将自动：
               - 获取比特币价格数据
               - 获取美元指数数据  
               - 计算流动性指标
            2. 数据获取完成后，将显示流动性指标图表
            3. 系统支持增量更新，后续更新将只获取新增数据
            """)
            
            if st.button("🎯 立即开始获取数据", type="primary"):
                with st.spinner("正在获取数据..."):
                    result = liquidity_indicator.update_and_calculate(force_update=True)
                    if result is not None:
                        st.success("✅ 数据获取成功!")
                        st.rerun()
                    else:
                        st.error("❌ 数据获取失败，请检查网络连接或数据源配置")
            
            return
        
        # 数据概览
        st.markdown("#### 📋 数据概览")
        
        # 获取最新值
        latest_values = liquidity_indicator.get_latest_values(liquidity_data)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if latest_values.get('liquidity_indicator'):
                st.metric(
                    "当前流动性指标", 
                    f"{latest_values['liquidity_indicator']:.6f}",
                    delta=f"{latest_values.get('change_1d', 0):.2f}%" if latest_values.get('change_1d') else None
                )
        
        with col2:
            if latest_values.get('btc_price'):
                st.metric(
                    "BTC价格", 
                    f"${latest_values['btc_price']:,.2f}"
                )
        
        with col3:
            if latest_values.get('dxy_value'):
                st.metric(
                    "美元指数", 
                    f"{latest_values['dxy_value']:.4f}"
                )
        
        with col4:
            if latest_values.get('date'):
                st.metric(
                    "数据日期", 
                    latest_values['date']
                )
        
        # 时间范围选择
        st.markdown("#### 📅 时间范围")
        
        min_date = liquidity_data['date'].min().date()
        max_date = liquidity_data['date'].max().date()
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "开始日期",
                value=max(min_date, max_date - timedelta(days=365)),
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
        filtered_data = liquidity_data[
            (liquidity_data['date'].dt.date >= start_date) &
            (liquidity_data['date'].dt.date <= end_date)
        ].copy()
        
        if filtered_data.empty:
            st.warning("所选时间范围内无数据")
            return
        
        # 主要图表
        st.markdown("#### 📈 流动性指标趋势")
        
        # 检查是否有纳斯达克数据
        has_nasdaq = 'nasdaq_value' in filtered_data.columns and not filtered_data['nasdaq_value'].isna().all()
        
        if has_nasdaq:
            # 双坐标轴图表：流动性指标 vs 纳斯达克指数
            st.markdown("##### 💧 流动性指标 vs 📊 纳斯达克指数 (双坐标轴)")
            
            fig_dual = go.Figure()
            
            # 添加流动性指标（左坐标轴）
            fig_dual.add_trace(
                go.Scatter(
                    x=filtered_data['date'],
                    y=filtered_data['liquidity_indicator'],
                    mode='lines',
                    name='流动性指标',
                    line=dict(color='#1f77b4', width=2),
                    yaxis='y',
                    hovertemplate='日期: %{x}<br>流动性指标: %{y:.6f}<extra></extra>'
                )
            )
            
            # 添加纳斯达克指数（右坐标轴，对数坐标）
            fig_dual.add_trace(
                go.Scatter(
                    x=filtered_data['date'],
                    y=filtered_data['nasdaq_value'],
                    mode='lines',
                    name='纳斯达克指数',
                    line=dict(color='#ff7f0e', width=2),
                    yaxis='y2',
                    hovertemplate='日期: %{x}<br>纳斯达克指数: %{y:,.0f}<extra></extra>'
                )
            )
            
            # 更新布局
            fig_dual.update_layout(
                title='流动性前瞻指标 vs 纳斯达克指数',
                xaxis_title='日期',
                yaxis=dict(
                    title='流动性指标',
                    side='left',
                    color='#1f77b4'
                ),
                yaxis2=dict(
                    title='纳斯达克指数',
                    side='right',
                    overlaying='y',
                    color='#ff7f0e',
                    type='log'  # 对数坐标
                ),
                height=500,
                template='plotly_white',
                legend=dict(x=0.01, y=0.99)
            )
            
            st.plotly_chart(fig_dual, use_container_width=True)
        
        # 详细三线图
        st.markdown("##### 📊 详细趋势分析")
        
        # 创建子图
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=('流动性前瞻指标', 'BTC价格 (USD)', '美元指数 (DXY)'),
            vertical_spacing=0.08,
            row_heights=[0.4, 0.3, 0.3]
        )
        
        # 流动性指标
        fig.add_trace(
            go.Scatter(
                x=filtered_data['date'],
                y=filtered_data['liquidity_indicator'],
                mode='lines',
                name='流动性指标',
                line=dict(color='#1f77b4', width=2),
                hovertemplate='日期: %{x}<br>流动性指标: %{y:.6f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # 添加移动平均线
        if 'liquidity_indicator_ma7' in filtered_data.columns:
            fig.add_trace(
                go.Scatter(
                    x=filtered_data['date'],
                    y=filtered_data['liquidity_indicator_ma7'],
                    mode='lines',
                    name='7日均线',
                    line=dict(color='orange', width=1, dash='dash'),
                    hovertemplate='日期: %{x}<br>7日均线: %{y:.6f}<extra></extra>'
                ),
                row=1, col=1
            )
        
        if 'liquidity_indicator_ma30' in filtered_data.columns:
            fig.add_trace(
                go.Scatter(
                    x=filtered_data['date'],
                    y=filtered_data['liquidity_indicator_ma30'],
                    mode='lines',
                    name='30日均线',
                    line=dict(color='red', width=1, dash='dot'),
                    hovertemplate='日期: %{x}<br>30日均线: %{y:.6f}<extra></extra>'
                ),
                row=1, col=1
            )
        
        # BTC价格
        fig.add_trace(
            go.Scatter(
                x=filtered_data['date'],
                y=filtered_data['btc_price'],
                mode='lines',
                name='BTC价格',
                line=dict(color='#ff7f0e', width=2),
                hovertemplate='日期: %{x}<br>BTC价格: $%{y:,.2f}<extra></extra>'
            ),
            row=2, col=1
        )
        
        # 美元指数
        fig.add_trace(
            go.Scatter(
                x=filtered_data['date'],
                y=filtered_data['dxy_value'],
                mode='lines',
                name='美元指数',
                line=dict(color='#2ca02c', width=2),
                hovertemplate='日期: %{x}<br>美元指数: %{y:.4f}<extra></extra>'
            ),
            row=3, col=1
        )
        
        # 更新布局
        fig.update_layout(
            height=800,
            title_text="流动性前瞻指标及其组成部分",
            showlegend=True,
            template='plotly_white'
        )
        
        # 更新x轴
        fig.update_xaxes(title_text="日期", row=3, col=1)
        
        # 更新y轴
        fig.update_yaxes(title_text="流动性指标", row=1, col=1)
        fig.update_yaxes(title_text="价格 (USD)", row=2, col=1)
        fig.update_yaxes(title_text="指数值", row=3, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 相关性分析
        st.markdown("#### 🔍 相关性分析")
        
        if has_nasdaq:
            # 带纳斯达克的相关性分析
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # 计算相关系数
                corr_btc_liquidity = filtered_data['btc_price'].corr(filtered_data['liquidity_indicator'])
                corr_dxy_liquidity = filtered_data['dxy_value'].corr(filtered_data['liquidity_indicator'])
                corr_nasdaq_liquidity = filtered_data['nasdaq_value'].corr(filtered_data['liquidity_indicator'])
                corr_btc_dxy = filtered_data['btc_price'].corr(filtered_data['dxy_value'])
                corr_btc_nasdaq = filtered_data['btc_price'].corr(filtered_data['nasdaq_value'])
                corr_dxy_nasdaq = filtered_data['dxy_value'].corr(filtered_data['nasdaq_value'])
                
                st.markdown("**📊 相关系数矩阵**")
                st.write(f"• BTC与流动性指标: {corr_btc_liquidity:.4f}")
                st.write(f"• 纳斯达克与流动性指标: {corr_nasdaq_liquidity:.4f}")
                st.write(f"• DXY与流动性指标: {corr_dxy_liquidity:.4f}")
                st.write(f"• BTC与纳斯达克: {corr_btc_nasdaq:.4f}")
                st.write(f"• BTC与DXY: {corr_btc_dxy:.4f}")
                st.write(f"• 纳斯达克与DXY: {corr_dxy_nasdaq:.4f}")
            
            with col2:
                # 领先滞后分析
                st.markdown("**⏱️ 领先滞后关系分析**")
                
                # 计算不同时间滞后的相关性
                lags = [-30, -15, -7, -3, -1, 0, 1, 3, 7, 15, 30]
                correlations_nasdaq = []
                
                for lag in lags:
                    if lag == 0:
                        corr = filtered_data['liquidity_indicator'].corr(filtered_data['nasdaq_value'])
                    elif lag > 0:
                        # 流动性指标领先纳斯达克
                        corr = filtered_data['liquidity_indicator'].shift(lag).corr(filtered_data['nasdaq_value'])
                    else:
                        # 纳斯达克领先流动性指标
                        corr = filtered_data['liquidity_indicator'].corr(filtered_data['nasdaq_value'].shift(-lag))
                    correlations_nasdaq.append(corr)
                
                # 找到最大相关性及其滞后期
                max_corr_idx = max(range(len(correlations_nasdaq)), key=lambda i: abs(correlations_nasdaq[i]))
                max_corr = correlations_nasdaq[max_corr_idx]
                max_lag = lags[max_corr_idx]
                
                st.write(f"**最强相关性**: {max_corr:.4f}")
                if max_lag > 0:
                    st.write(f"**关系**: 流动性指标领先纳斯达克 {max_lag} 天")
                elif max_lag < 0:
                    st.write(f"**关系**: 纳斯达克领先流动性指标 {-max_lag} 天")
                else:
                    st.write(f"**关系**: 同步变化")
                
                # 显示滞后相关性图
                fig_lag = go.Figure()
                fig_lag.add_trace(go.Scatter(
                    x=lags,
                    y=correlations_nasdaq,
                    mode='lines+markers',
                    name='相关系数',
                    line=dict(color='purple', width=2),
                    marker=dict(size=6)
                ))
                fig_lag.add_vline(x=max_lag, line_dash="dash", line_color="red")
                fig_lag.update_layout(
                    title='流动性指标与纳斯达克滞后相关性',
                    xaxis_title='滞后天数 (负值=纳斯达克领先, 正值=流动性指标领先)',
                    yaxis_title='相关系数',
                    height=300
                )
                st.plotly_chart(fig_lag, use_container_width=True)
            
            with col3:
                # 散点图
                fig_scatter = px.scatter(
                    filtered_data, 
                    x='nasdaq_value', 
                    y='liquidity_indicator',
                    color='date',
                    title='流动性指标 vs 纳斯达克指数',
                    labels={
                        'nasdaq_value': '纳斯达克指数',
                        'liquidity_indicator': '流动性指标',
                        'date': '日期'
                    },
                    color_continuous_scale='viridis'
                )
                fig_scatter.update_layout(height=400)
                st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            # 原有的相关性分析
            col1, col2 = st.columns(2)
            
            with col1:
                # 计算相关系数
                corr_btc_liquidity = filtered_data['btc_price'].corr(filtered_data['liquidity_indicator'])
                corr_dxy_liquidity = filtered_data['dxy_value'].corr(filtered_data['liquidity_indicator'])
                corr_btc_dxy = filtered_data['btc_price'].corr(filtered_data['dxy_value'])
                
                st.markdown("**相关系数分析**")
                st.write(f"• BTC与流动性指标: {corr_btc_liquidity:.4f}")
                st.write(f"• DXY与流动性指标: {corr_dxy_liquidity:.4f}")
                st.write(f"• BTC与DXY: {corr_btc_dxy:.4f}")
            
            with col2:
                # 散点图
                fig_scatter = px.scatter(
                    filtered_data, 
                    x='dxy_value', 
                    y='btc_price',
                    color='liquidity_indicator',
                    title='BTC价格 vs 美元指数',
                    labels={
                        'dxy_value': '美元指数',
                        'btc_price': 'BTC价格 (USD)',
                        'liquidity_indicator': '流动性指标'
                    },
                    color_continuous_scale='viridis'
                )
                fig_scatter.update_layout(height=400)
                st.plotly_chart(fig_scatter, use_container_width=True)
        
        # 统计信息
        st.markdown("#### 📊 统计信息")
        
        stats_df = filtered_data[['liquidity_indicator', 'btc_price', 'dxy_value']].describe()
        st.dataframe(stats_df, use_container_width=True)
        
        # 源数据展示
        if show_source_data:
            st.markdown("#### 📋 源数据")
            
            # 分页显示
            page_size = 100
            total_pages = (len(filtered_data) - 1) // page_size + 1
            
            if total_pages > 1:
                page = st.selectbox(
                    f"选择页码 (共 {total_pages} 页)", 
                    range(1, total_pages + 1)
                ) - 1
                start_idx = page * page_size
                end_idx = start_idx + page_size
                display_data = filtered_data.iloc[start_idx:end_idx]
            else:
                display_data = filtered_data
            
            st.dataframe(display_data, use_container_width=True)
        
        # 数据下载
        st.markdown("#### 💾 数据下载")
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv = filtered_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 下载 CSV",
                data=csv,
                file_name=f"liquidity_indicator_{start_date}_{end_date}.csv",
                mime="text/csv"
            )
        
        with col2:
            from io import BytesIO
            excel_buffer = BytesIO()
            filtered_data.to_excel(excel_buffer, index=False)
            st.download_button(
                label="📊 下载 Excel", 
                data=excel_buffer.getvalue(),
                file_name=f"liquidity_indicator_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
    except Exception as e:
        st.error(f"加载流动性指标页面失败: {e}")
        st.markdown("请检查系统配置和依赖包安装情况")
