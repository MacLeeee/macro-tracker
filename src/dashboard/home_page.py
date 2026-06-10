"""
首页 - 所有图表汇总
"""
import streamlit as st
import sys, os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.dashboard.chart_generators import (
    get_global_liquidity_chart,
    get_china_excess_liquidity_chart,
    get_m1m2_scissors_chart,
    get_social_financing_chart,
    get_dxy_ppi_chart,
    get_m1_ppi_chart,
    get_cn_spread_m1_chart,
    get_profit_export_chart,
    get_wtm_chart,
    get_fedex_wtm_chart,
    get_us_spread_pmi_chart,
    get_lme_copper_pmi_chart,
    get_us_capacity_ppi_ratio_chart,
    get_china_inventory_chart,
    get_m0043718_m0043728_chart
)


def show_home_page():
    """显示首页 - 所有图表汇总"""
    st.markdown("# 📊 宏观经济数据库 - 总览")
    st.markdown("---")
    
    # 第一行：全球流动性 + 中国超额流动性
    st.markdown("## 🌍 全球与中国流动性指标")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💧 全球流动性指标")
        try:
            fig = get_global_liquidity_chart()
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("图表生成失败")
        except Exception as e:
            st.error(f"图表生成错误: {e}")
    
    with col2:
        st.markdown("### 🇨🇳 中国超额流动性")
        try:
            fig = get_china_excess_liquidity_chart()
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("图表生成失败")
        except Exception as e:
            st.error(f"图表生成错误: {e}")
    
    st.markdown("---")
    
    # 第二行：M1/M2剪刀差 + 社融/GDP
    st.markdown("## 💰 中国货币与信贷指标")
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("### ✂️ M1/M2剪刀差")
        fig = get_m1m2_scissors_chart()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")
    
    with col4:
        st.markdown("### 📈 社融同比增长")
        fig = get_social_financing_chart()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")
    
    st.markdown("---")
    
    # 第三行：美元指数vs PPI + M1 vs PPI
    st.markdown("## 📦 中国基本面数据")
    col5, col6 = st.columns(2)
    
    with col5:
        st.markdown("### 📉 美元指数vs中国PPI")
        fig = get_dxy_ppi_chart()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")
    
    with col6:
        st.markdown("### 💵 M1同比vs PPI")
        fig = get_m1_ppi_chart()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")
    
    st.markdown("---")
    
    # 第四行：国债利差vs M1 + 工业利润vs出口
    col7, col8 = st.columns(2)
    
    with col7:
        st.markdown("### 📊 国债利差vs M1")
        fig = get_cn_spread_m1_chart()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")
    
    with col8:
        st.markdown("### 🏭 工业利润vs出口")
        fig = get_profit_export_chart()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")
    
    st.markdown("---")
    
    # 第五行：WTM + FedEx vs WTM
    st.markdown("## 🚢 贸易出口数据")
    col9, col10 = st.columns(2)
    
    with col9:
        st.markdown("### 🌍 CPB世界贸易量")
        fig = get_wtm_chart()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")
    
    with col10:
        st.markdown("### ✈️ FedEx vs WTM")
        fig = get_fedex_wtm_chart()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")
    
    st.markdown("---")
    
    # 第六行：美国基本面
    st.markdown("## 🇺🇸 美国基本面数据")
    col11, col12 = st.columns(2)
    
    with col11:
        st.markdown("### 📉 美国10Y-2Y vs PMI")
        fig = get_us_spread_pmi_chart()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无数据")
    
    with col12:
        st.markdown("### 🥉 COMEX铜价 vs 美国PMI")
        try:
            fig = get_lme_copper_pmi_chart()
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("图表生成失败")
        except Exception as e:
            st.error(f"图表生成错误: {e}")
            st.info("请检查数据源是否可用")
    
    st.markdown("---")
    
    # 第七行：美国产能利用率/PPI
    col13, col14 = st.columns(2)
    
    with col13:
        st.markdown("### 🏭 美国产能利用率 vs PPI")
        try:
            fig = get_us_capacity_ppi_ratio_chart()
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("图表生成失败，请先同步Wind数据")
        except Exception as e:
            st.error(f"图表生成错误: {e}")
            st.info("请先在美国基本面数据页面同步Wind数据")
    
    with col14:
        st.info("💡 提示：如需更新数据，请前往'🇺🇸 美国基本面数据'页面点击'同步Wind数据'按钮")
    
    st.markdown("---")
    
    # 第八行：中国库存周期
    col15, col16 = st.columns(2)
    
    with col15:
        st.markdown("### 📦 中国库存同比变化（库存周期）")
        try:
            fig = get_china_inventory_chart()
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("图表生成失败，请先同步Wind数据")
        except Exception as e:
            st.error(f"图表生成错误: {e}")
            st.info("请先在中国基本面数据页面同步Wind库存数据")
    
    with col16:
        st.markdown("### 📊 中国朱格拉周期（5000户工业企业景气扩散指数）")
        try:
            fig = get_m0043718_m0043728_chart()
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("图表生成失败，请先同步Wind数据")
        except Exception as e:
            st.error(f"图表生成错误: {e}")
            st.info("请先在中国基本面数据页面同步Wind数据")

