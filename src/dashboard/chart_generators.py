"""
图表生成器模块 - 为首页汇总提供统一的图表生成接口
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.database.db_manager import db_manager


# ============ 全球流动性指标 ============
def get_global_liquidity_chart():
    """获取全球流动性指标图表"""
    try:
        liquidity_data = db_manager.load_data("liquidity_indicator")
        if liquidity_data is None or liquidity_data.empty:
            return None
        
        # 取最近3年数据
        end_date = liquidity_data['date'].max()
        start_date = end_date - pd.DateOffset(years=3)
        data = liquidity_data[(liquidity_data['date'] >= start_date) & (liquidity_data['date'] <= end_date)]
        
        if data.empty:
            return None
        
        has_nasdaq = 'nasdaq_value' in data.columns and not data['nasdaq_value'].isna().all()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data['date'], y=data['liquidity_indicator'],
            name='流动性指标', line=dict(color='#1f77b4', width=2)
        ))
        
        if has_nasdaq:
            fig.add_trace(go.Scatter(
                x=data['date'], y=data['nasdaq_value'],
                name='纳斯达克', line=dict(color='#ff7f0e', width=2),
                yaxis='y2'
            ))
            fig.update_layout(
                yaxis2=dict(title='纳斯达克', side='right', overlaying='y', type='log')
            )
        
        fig.update_layout(
            title='全球流动性(BTC/DXY)', xaxis=dict(title='日期'),
            yaxis=dict(title='流动性指标'), template='plotly_white',
            height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ 中国超额流动性 ============
def get_china_excess_liquidity_chart():
    """获取中国超额流动性图表"""
    try:
        data = db_manager.load_data("china_excess_liquidity")
        if data is None or data.empty:
            return None
        
        # 取最近3年
        end_date = data['date'].max()
        start_date = end_date - pd.DateOffset(years=3)
        data = data[(data['date'] >= start_date) & (data['date'] <= end_date)]
        
        if data.empty:
            return None
        
        has_ratio = 'zz2000_hs300_ratio' in data.columns and not data['zz2000_hs300_ratio'].isna().all()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data['date'], y=data['china_excess_liquidity'],
            name='超额流动性', line=dict(color='#e74c3c', width=3)
        ))
        
        if has_ratio:
            fig.add_trace(go.Scatter(
                x=data['date'], y=data['zz2000_hs300_ratio'],
                name='中证2000/沪深300', line=dict(color='#3498db', width=2),
                yaxis='y2'
            ))
            fig.update_layout(
                yaxis2=dict(title='比值', side='right', overlaying='y')
            )
        
        fig.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.5)
        fig.update_layout(
            title='中国超额流动性(M2-工业增加值)', xaxis=dict(title='日期'),
            yaxis=dict(title='超额流动性(%)'), template='plotly_white',
            height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ M1/M2剪刀差 ============
def get_m1m2_scissors_chart():
    """获取M1/M2剪刀差图表"""
    try:
        from src.data_fetcher.m1m2_scissors_indicator import M1M2ScissorsIndicator
        scissors_indicator = M1M2ScissorsIndicator(db_manager)
        data = scissors_indicator.calculate_m1m2_scissors()
        
        if data is None or data.empty:
            return None
        
        # 取最近3年
        end_date = data['date'].max()
        start_date = end_date - pd.DateOffset(years=3)
        data = data[(data['date'] >= start_date) & (data['date'] <= end_date)]
        
        if data.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data['date'], y=data['m1m2_scissors'],
            name='M1/M2剪刀差', line=dict(color='red', width=3)
        ))
        
        if 'close' in data.columns and not data['close'].isna().all():
            fig.add_trace(go.Scatter(
                x=data['date'], y=data['close'],
                name='中证500', line=dict(color='orange', width=2),
                yaxis='y2'
            ))
            fig.update_layout(
                yaxis2=dict(title='中证500', side='right', overlaying='y')
            )
        
        fig.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.5)
        fig.update_layout(
            title='M1/M2剪刀差', xaxis=dict(title='日期'),
            yaxis=dict(title='剪刀差(%)'), template='plotly_white',
            height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ 社融/GDP ============
def get_social_financing_chart():
    """获取社融同比增长图表"""
    try:
        from src.data_fetcher.social_financing_indicator import init_social_financing_indicator
        sf_indicator = init_social_financing_indicator(db_manager)
        data, _ = sf_indicator.calculate_social_financing_gdp()
        
        if data.empty:
            return None
        
        # 取最近3年
        end_date = data['date'].max()
        start_date = end_date - pd.DateOffset(years=3)
        data = data[(data['date'] >= start_date) & (data['date'] <= end_date)]
        
        if data.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data['date'], y=data['social_financing_gdp_ratio'],
            name='社融同比增长', line=dict(color='red', width=3)
        ))
        
        if 'close' in data.columns and not data['close'].isna().all():
            fig.add_trace(go.Scatter(
                x=data['date'], y=data['close'],
                name='沪深300', line=dict(color='blue', width=2),
                yaxis='y2'
            ))
            fig.update_layout(
                yaxis2=dict(title='沪深300', side='right', overlaying='y')
            )
        
        fig.update_layout(
            title='社融同比增长 vs 沪深300', xaxis=dict(title='日期'),
            yaxis=dict(title='社融同比(%)'), template='plotly_white',
            height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ 美元指数vs PPI ============
def get_dxy_ppi_chart():
    """获取美元指数vs PPI图表"""
    try:
        from src.data_fetcher.akshare_fetcher import AkShareFetcher
        
        fetcher = AkShareFetcher()
        
        # 获取PPI
        ppi = db_manager.load_data('macro_china_ppi')
        if ppi is None or ppi.empty:
            ppi = fetcher.fetch_data_by_key("macro_china_ppi")
        if ppi is None or ppi.empty:
            return None
        
        ppi['date'] = pd.to_datetime(ppi['date'], errors='coerce')
        ppi_col = next((c for c in ppi.columns if '同比' in str(c)), None)
        if ppi_col:
            ppi = ppi[['date', ppi_col]].rename(columns={ppi_col: 'ppi_yoy'})
        
        # 获取DXY
        dxy = db_manager.load_data('dxy_index_data')
        if dxy is None or dxy.empty:
            return None
        
        dxy['date'] = pd.to_datetime(dxy['date'], errors='coerce')
        dxy = dxy.set_index('date').resample('ME').last().reset_index()
        dxy['date'] = dxy['date'].dt.to_period('M').dt.start_time
        dxy['dxy_yoy'] = dxy['close'].pct_change(12) * 100
        dxy['date'] = dxy['date'] + pd.offsets.DateOffset(months=6)
        dxy['dxy_yoy_inv'] = -dxy['dxy_yoy']
        
        merged = pd.merge(ppi, dxy[['date', 'dxy_yoy_inv']], on='date', how='outer').sort_values('date')
        
        # 取最近10年
        end_date = merged['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        merged = merged[(merged['date'] >= start_date) & (merged['date'] <= end_date)]
        
        if merged.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['ppi_yoy'],
            name='PPI同比', line=dict(color='red', width=3), connectgaps=False
        ))
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['dxy_yoy_inv'],
            name='DXY同比(逆,领先6月)', line=dict(color='black', width=2),
            yaxis='y2', connectgaps=False
        ))
        
        fig.update_layout(
            title='美元指数vs中国PPI', xaxis=dict(title='日期'),
            yaxis=dict(title='PPI同比(%)'),
            yaxis2=dict(title='DXY同比(%)', side='right', overlaying='y'),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ M1 vs PPI ============
def get_m1_ppi_chart():
    """获取M1同比vs PPI图表"""
    try:
        from src.data_fetcher.akshare_fetcher import AkShareFetcher
        
        fetcher = AkShareFetcher()
        lead_months = 6  # 默认领先6个月
        
        # 获取PPI
        ppi = db_manager.load_data('macro_china_ppi')
        if ppi is None or ppi.empty:
            return None
        ppi['date'] = pd.to_datetime(ppi['date'], errors='coerce')
        ppi_col = next((c for c in ppi.columns if '同比' in str(c)), None)
        if ppi_col:
            ppi = ppi[['date', ppi_col]].rename(columns={ppi_col: 'ppi_yoy'})
        
        # 获取M1
        m1 = db_manager.load_data('macro_china_m1m2')
        if m1 is None or m1.empty:
            return None
        m1['date'] = pd.to_datetime(m1['date'], errors='coerce')
        m1_yoy_col = next((c for c in m1.columns if 'M1' in str(c) and '同比' in str(c)), None)
        if m1_yoy_col:
            m1 = m1[['date', m1_yoy_col]].rename(columns={m1_yoy_col: 'm1_yoy'})
        
        if m1.empty or ppi.empty:
            return None
        
        # M1领先
        m1_lead = m1.copy()
        m1_lead['date'] = m1_lead['date'] + pd.offsets.DateOffset(months=lead_months)
        
        merged = pd.merge(m1_lead, ppi, on='date', how='outer').sort_values('date')
        
        # 取最近10年
        end_date = merged['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        merged = merged[(merged['date'] >= start_date) & (merged['date'] <= end_date)]
        
        if merged.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['m1_yoy'],
            name=f'M1同比(领先{lead_months}月)', line=dict(color='teal', width=3),
            connectgaps=False
        ))
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['ppi_yoy'],
            name='PPI同比', line=dict(color='red', width=2),
            yaxis='y2', connectgaps=False
        ))
        
        fig.update_layout(
            title='M1同比vs PPI', xaxis=dict(title='日期'),
            yaxis=dict(title='M1同比(%)'),
            yaxis2=dict(title='PPI同比(%)', side='right', overlaying='y'),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ 国债利差vs M1 ============
def get_cn_spread_m1_chart():
    """获取中国10Y-2Y利差vs M1图表"""
    try:
        # 获取国债收益率 - 数据库优先，接口兜底
        bond = db_manager.load_data('bond_zh_us_rate')
        if bond is None or bond.empty:
            import akshare as ak
            bond = ak.bond_zh_us_rate(start_date="19900101")
        if 'date' not in bond.columns:
            bond['date'] = pd.to_datetime(bond['日期'], errors='coerce')
        else:
            bond['date'] = pd.to_datetime(bond['date'], errors='coerce')
        
        col_10y = next((c for c in bond.columns if '中国' in str(c) and '10' in str(c)), None)
        col_2y = next((c for c in bond.columns if '中国' in str(c) and '2' in str(c)), None)
        
        if not col_10y or not col_2y:
            return None
        
        bond[col_10y] = pd.to_numeric(bond[col_10y], errors='coerce')
        bond[col_2y] = pd.to_numeric(bond[col_2y], errors='coerce')
        bond = bond.set_index('date').resample('ME').last().reset_index()
        bond['date'] = bond['date'].dt.to_period('M').dt.start_time
        bond['spread'] = bond[col_10y] - bond[col_2y]
        
        # 获取M1
        m1 = db_manager.load_data('macro_china_m1m2')
        if m1 is None or m1.empty:
            return None
        m1['date'] = pd.to_datetime(m1['date'], errors='coerce')
        m1_yoy_col = next((c for c in m1.columns if 'M1' in str(c) and '同比' in str(c)), None)
        if m1_yoy_col:
            m1 = m1[['date', m1_yoy_col]].rename(columns={m1_yoy_col: 'm1_yoy'})
        
        lead_months = 11  # 默认领先11个月
        spread_lead = bond[['date', 'spread']].copy()
        spread_lead['date'] = spread_lead['date'] + pd.offsets.DateOffset(months=lead_months)
        
        merged = pd.merge(spread_lead, m1, on='date', how='outer').sort_values('date')
        
        # 取最近10年
        end_date = merged['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        merged = merged[(merged['date'] >= start_date) & (merged['date'] <= end_date)]
        
        if merged.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['spread'],
            name=f'10Y-2Y利差(领先{lead_months}月)', line=dict(color='royalblue', width=3),
            connectgaps=False
        ))
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['m1_yoy'],
            name='M1同比', line=dict(color='teal', width=2),
            yaxis='y2', connectgaps=False
        ))
        
        fig.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.5)
        fig.update_layout(
            title='国债利差vs M1', xaxis=dict(title='日期'),
            yaxis=dict(title='利差(%)'),
            yaxis2=dict(title='M1同比(%)', side='right', overlaying='y'),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ 工业利润vs出口 ============
def get_profit_export_chart():
    """获取工业利润vs出口图表"""
    try:
        # 获取出口数据
        export = db_manager.load_data('china_export_12m_yoy')
        if export is None or export.empty:
            return None
        export['date'] = pd.to_datetime(export['date'], errors='coerce')
        
        # 获取利润数据
        profit = db_manager.load_data('china_industrial_profit_cuml_yoy')
        if profit is None or profit.empty:
            return None
        profit['date'] = pd.to_datetime(profit['date'], errors='coerce')
        
        # 利润领先6个月
        profit_lead = profit.copy()
        profit_lead['date'] = profit_lead['date'] + pd.offsets.DateOffset(months=6)
        
        merged = pd.merge(export, profit_lead, on='date', how='outer').sort_values('date')
        
        # 取最近10年
        end_date = merged['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        merged = merged[(merged['date'] >= start_date) & (merged['date'] <= end_date)]
        
        if merged.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['export_12m_yoy'],
            name='出口12月累计增速', line=dict(color='orange', width=3),
            connectgaps=False
        ))
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['profit_12m_cuml_yoy'],
            name='利润12月累计增速(领先6月)', line=dict(color='purple', width=2),
            yaxis='y2', connectgaps=False
        ))
        
        fig.update_layout(
            title='工业利润vs出口', xaxis=dict(title='日期'),
            yaxis=dict(title='出口增速(%)'),
            yaxis2=dict(title='利润增速(%)', side='right', overlaying='y'),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ WTM ============
def get_wtm_chart():
    """获取CPB世界贸易量图表"""
    try:
        wtm = db_manager.load_data('cpb_wtm_world_trade')
        if wtm is None or wtm.empty:
            return None
        
        wtm['date'] = pd.to_datetime(wtm['date'], errors='coerce')
        
        # 取最近10年
        end_date = wtm['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        wtm = wtm[(wtm['date'] >= start_date) & (wtm['date'] <= end_date)]
        
        if wtm.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=wtm['date'], y=wtm['wtv_index'],
            name='世界贸易量', line=dict(color='#2a9d8f', width=3)
        ))
        
        fig.update_layout(
            title='CPB世界贸易量', xaxis=dict(title='日期'),
            yaxis=dict(title='指数'), template='plotly_white',
            height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ FedEx vs WTM ============
def get_fedex_wtm_chart():
    """获取FedEx vs WTM图表"""
    try:
        # 获取FedEx
        fdx = db_manager.load_data('openbb_fdx_price')
        if fdx is None or fdx.empty:
            return None
        fdx['date'] = pd.to_datetime(fdx['date'], errors='coerce')
        fdx['date'] = fdx['date'].dt.to_period('M').dt.start_time
        fdx = fdx.groupby('date', as_index=False)['close'].last()
        fdx['log_12m_pct'] = (np.log(fdx['close']) - np.log(fdx['close'].shift(12))) * 100
        
        # 获取WTM
        wtm = db_manager.load_data('cpb_wtm_world_trade')
        if wtm is None or wtm.empty:
            return None
        wtm['date'] = pd.to_datetime(wtm['date'], errors='coerce')
        wtm['yoy'] = wtm['wtv_index'].pct_change(12) * 100
        
        lead_months = 3
        fdx_lead = fdx[['date', 'log_12m_pct']].copy()
        fdx_lead['date'] = fdx_lead['date'] + pd.offsets.DateOffset(months=lead_months)
        
        merged = pd.merge(wtm[['date', 'yoy']], fdx_lead, on='date', how='outer').sort_values('date')
        
        # 取最近10年
        end_date = merged['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        merged = merged[(merged['date'] >= start_date) & (merged['date'] <= end_date)]
        
        if merged.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['yoy'],
            name='WTM同比', line=dict(color='#e76f51', width=3),
            connectgaps=False
        ))
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['log_12m_pct'],
            name=f'FedEx对数12月变动(领先{lead_months}月)', line=dict(color='#264653', width=2),
            yaxis='y2', connectgaps=False
        ))
        
        fig.update_layout(
            title='FedEx vs WTM', xaxis=dict(title='日期'),
            yaxis=dict(title='WTM同比(%)'),
            yaxis2=dict(title='FedEx变动(%)', side='right', overlaying='y'),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ 美国10Y-2Y vs PMI ============
def get_us_spread_pmi_chart(lead_months: int = 12):
    """获取美国10Y-2Y vs PMI图表"""
    try:
        import akshare as ak
        
        # 获取美国国债收益率 - 优先使用数据库
        ten = db_manager.load_data('us_yield_10y')
        two = db_manager.load_data('us_yield_2y')
        
        if ten is None or ten.empty or two is None or two.empty:
            # 从AkShare获取
            bond = ak.bond_zh_us_rate(start_date="19900101")
            bond['date'] = pd.to_datetime(bond['日期'], errors='coerce')
            
            col_10y = next((c for c in bond.columns if '美国' in str(c) and '10' in str(c)), None)
            col_2y = next((c for c in bond.columns if '美国' in str(c) and '2' in str(c)), None)
            
            if not col_10y or not col_2y:
                return None
            
            bond[col_10y] = pd.to_numeric(bond[col_10y], errors='coerce')
            bond[col_2y] = pd.to_numeric(bond[col_2y], errors='coerce')
            ten = bond[['date', col_10y]].rename(columns={col_10y: 'value'})
            two = bond[['date', col_2y]].rename(columns={col_2y: 'value'})
        
        # 处理数据
        ten = ten[['date','value']].rename(columns={'value':'y10'})
        two = two[['date','value']].rename(columns={'value':'y2'})
        
        # 转月度数据
        ten['date'] = pd.to_datetime(ten['date'], errors='coerce')
        two['date'] = pd.to_datetime(two['date'], errors='coerce')
        
        ten_m = ten.set_index('date').resample('ME').last().reset_index()
        two_m = two.set_index('date').resample('ME').last().reset_index()
        ten_m['date'] = ten_m['date'].dt.to_period('M').dt.start_time
        two_m['date'] = two_m['date'].dt.to_period('M').dt.start_time
        
        merged = pd.merge(ten_m, two_m, on='date', how='inner').dropna().sort_values('date')
        merged['spread'] = merged['y10'] - merged['y2']
        merged['spread_z'] = (merged['spread'] - merged['spread'].rolling(12, min_periods=6).mean()) / merged['spread'].rolling(12, min_periods=6).std()
        
        # 获取PMI
        pmi = db_manager.load_data('macro_usa_pmi')
        if pmi is None or pmi.empty:
            pmi = ak.macro_usa_pmi()
        if pmi is None or pmi.empty:
            return None
        
        pmi['date'] = pd.to_datetime(pmi['date'], errors='coerce')
        pmi_col = next((c for c in pmi.columns if 'PMI' in str(c).upper()), None)
        if pmi_col:
            pmi = pmi[['date', pmi_col]].rename(columns={pmi_col: 'pmi'})
        elif 'value' in pmi.columns:
            pmi = pmi[['date', 'value']].rename(columns={'value': 'pmi'})
        
        # 利差领先
        spread_lead = merged[['date', 'spread_z']].copy()
        spread_lead['date'] = spread_lead['date'] + pd.offsets.DateOffset(months=lead_months)
        
        final_merged = pd.merge(spread_lead, pmi, on='date', how='outer').sort_values('date')
        
        # 取最近15年
        end_date = final_merged['date'].max()
        start_date = end_date - pd.DateOffset(years=15)
        final_merged = final_merged[(final_merged['date'] >= start_date) & (final_merged['date'] <= end_date)]
        
        if final_merged.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=final_merged['date'], y=final_merged['spread_z'],
            name=f'10Y-2Y(领先{lead_months}月,Z分数)', line=dict(color='#1f77b4', width=2),
            connectgaps=False
        ))
        fig.add_trace(go.Scatter(
            x=final_merged['date'], y=final_merged['pmi'],
            name='ISM PMI', line=dict(color='#d62728', width=2),
            yaxis='y2', connectgaps=False
        ))
        
        fig.update_layout(
            title='美国10Y-2Y vs PMI', xaxis=dict(title='日期'),
            yaxis=dict(title='Z分数', range=[-5, 5], zeroline=True),
            yaxis2=dict(title='PMI', side='right', overlaying='y'),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ COMEX铜 vs 美国PMI ============
def get_lme_copper_pmi_chart():
    """获取COMEX铜 vs 美国PMI图表"""
    try:
        import akshare as ak
        
        # 获取COMEX铜数据
        copper = db_manager.load_data('comex_copper')
        if copper is None or copper.empty:
            # 从AkShare获取COMEX铜数据
            copper = ak.futures_global_hist_em(symbol="HG00Y")  # COMEX铜主力合约
            if copper is not None and not copper.empty:
                copper['date'] = pd.to_datetime(copper['日期'], errors='coerce')
                # 使用最新价作为收盘价
                copper = copper[['date', '最新价']].rename(columns={'最新价': 'close'})
                copper['close'] = pd.to_numeric(copper['close'], errors='coerce')
                copper = copper.dropna().sort_values('date')
                # 保存到数据库
                try:
                    db_manager.save_data(copper, 'comex_copper', if_exists='replace')
                except Exception:
                    pass
        
        if copper is None or copper.empty:
            return None
        
        copper['date'] = pd.to_datetime(copper['date'], errors='coerce')
        # 转月度数据
        copper_monthly = copper.set_index('date').resample('ME').last().reset_index()
        copper_monthly['date'] = copper_monthly['date'].dt.to_period('M').dt.start_time
        
        # 获取美国PMI
        pmi = db_manager.load_data('macro_usa_pmi')
        if pmi is None or pmi.empty:
            pmi = ak.macro_usa_pmi()
        if pmi is None or pmi.empty:
            return None
        
        pmi['date'] = pd.to_datetime(pmi['date'], errors='coerce')
        pmi_col = next((c for c in pmi.columns if 'PMI' in str(c).upper()), None)
        if pmi_col:
            pmi = pmi[['date', pmi_col]].rename(columns={pmi_col: 'pmi'})
        elif 'value' in pmi.columns:
            pmi = pmi[['date', 'value']].rename(columns={'value': 'pmi'})
        
        # 合并数据
        merged = pd.merge(copper_monthly[['date', 'close']], pmi, on='date', how='outer').sort_values('date')
        
        # 取最近10年
        end_date = merged['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        merged = merged[(merged['date'] >= start_date) & (merged['date'] <= end_date)]
        
        if merged.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['close'],
            name='COMEX铜价', line=dict(color='#ff7f0e', width=3),
            connectgaps=False
        ))
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['pmi'],
            name='美国PMI', line=dict(color='#2ca02c', width=2),
            yaxis='y2', connectgaps=False
        ))
        
        fig.update_layout(
            title='COMEX铜价 vs 美国PMI', xaxis=dict(title='日期'),
            yaxis=dict(title='铜价(USD/磅)'),
            yaxis2=dict(title='PMI', side='right', overlaying='y'),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    except Exception:
        return None


# ============ 美国产能利用率 vs PPI ============
def get_us_capacity_ppi_ratio_chart():
    """获取美国产能利用率 vs PPI对比图表（双折线图）"""
    try:
        # 从us_fundamentals_page导入函数
        from src.dashboard.us_fundamentals_page import _load_us_capacity_utilization, _load_us_ppi
        
        capacity = _load_us_capacity_utilization()
        ppi = _load_us_ppi()
        
        if capacity.empty or ppi.empty:
            return None
        
        # 合并数据
        merged = pd.merge(capacity, ppi, on='date', how='inner').dropna().sort_values('date')
        
        # 取最近10年
        end_date = merged['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        merged = merged[(merged['date'] >= start_date) & (merged['date'] <= end_date)]
        
        if merged.empty:
            return None
        
        fig = go.Figure()
        
        # 产能利用率折线（左Y轴）
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['capacity_util'],
            name='产能利用率(%)', line=dict(color='#2ecc71', width=2),
            connectgaps=False, yaxis='y'
        ))
        
        # PPI折线（右Y轴）
        fig.add_trace(go.Scatter(
            x=merged['date'], y=merged['ppi'],
            name='PPI(%)', line=dict(color='#e74c3c', width=2),
            connectgaps=False, yaxis='y2'
        ))
        
        # 计算Y轴范围
        cap_range = merged['capacity_util'].dropna()
        ppi_range = merged['ppi'].dropna()
        
        cap_pad = (cap_range.max() - cap_range.min()) * 0.05 if not cap_range.empty else 1
        ppi_pad = (ppi_range.max() - ppi_range.min()) * 0.05 if not ppi_range.empty else 1
        
        fig.update_layout(
            title='美国工业产能利用率 vs PPI', xaxis=dict(title='日期'),
            yaxis=dict(title='产能利用率(%)', range=[cap_range.min()-cap_pad, cap_range.max()+cap_pad] if not cap_range.empty else None),
            yaxis2=dict(title='PPI(%)', side='right', overlaying='y', range=[ppi_range.min()-ppi_pad, ppi_range.max()+ppi_pad] if not ppi_range.empty else None),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50),
            legend=dict(x=0.02, y=0.98)
        )
        return fig
    except Exception:
        return None


# ============ 中国库存同比变化 ============
def get_china_inventory_chart():
    """获取中国库存同比变化图表"""
    try:
        # 从china_fundamentals_page导入函数
        from src.dashboard.china_fundamentals_page import _load_china_inventory_yoy
        
        inventory = _load_china_inventory_yoy()
        
        if inventory.empty:
            return None
        
        # 取最近10年
        end_date = inventory['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        inventory = inventory[(inventory['date'] >= start_date) & (inventory['date'] <= end_date)]
        
        if inventory.empty:
            return None
        
        fig = go.Figure()
        
        # 库存同比折线
        fig.add_trace(go.Scatter(
            x=inventory['date'], y=inventory['inventory_yoy'],
            name='库存同比(%)', line=dict(color='#3498db', width=2),
            connectgaps=False
        ))
        
        # 添加零线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        # 计算Y轴范围
        inv_range = inventory['inventory_yoy'].dropna()
        inv_pad = (inv_range.max() - inv_range.min()) * 0.05 if not inv_range.empty else 1
        
        fig.update_layout(
            title='中国库存同比变化（库存周期）', xaxis=dict(title='日期'),
            yaxis=dict(title='库存同比(%)', range=[inv_range.min()-inv_pad, inv_range.max()+inv_pad] if not inv_range.empty else None, zeroline=True),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50),
            legend=dict(x=0.02, y=0.98)
        )
        return fig
    except Exception:
        return None


# ============ M0043718 vs M0043728 ============
def get_m0043718_m0043728_chart():
    """获取M0043718 vs M0043728对比图表（双折线图）"""
    try:
        # 从china_fundamentals_page导入函数
        from src.dashboard.china_fundamentals_page import _load_m0043718_m0043728
        
        data_df = _load_m0043718_m0043728()
        
        if data_df.empty:
            return None
        
        # 取最近10年
        end_date = data_df['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        data_df = data_df[(data_df['date'] >= start_date) & (data_df['date'] <= end_date)]
        
        if data_df.empty:
            return None
        
        fig = go.Figure()
        
        # M0043718折线（左Y轴）
        fig.add_trace(go.Scatter(
            x=data_df['date'], y=data_df['m0043718'],
            name='固定资产投资情况', line=dict(color='#3498db', width=2),
            connectgaps=False, yaxis='y'
        ))
        
        # M0043728折线（右Y轴）
        fig.add_trace(go.Scatter(
            x=data_df['date'], y=data_df['m0043728'],
            name='设备能力利用水平', line=dict(color='#e74c3c', width=2),
            connectgaps=False, yaxis='y2'
        ))
        
        # 计算Y轴范围
        range1 = data_df['m0043718'].dropna()
        range2 = data_df['m0043728'].dropna()
        
        pad1 = (range1.max() - range1.min()) * 0.05 if not range1.empty else 1
        pad2 = (range2.max() - range2.min()) * 0.05 if not range2.empty else 1
        
        fig.update_layout(
            title='中国朱格拉周期（5000户工业企业景气扩散指数）', xaxis=dict(title='日期'),
            yaxis=dict(title='固定资产投资情况', range=[range1.min()-pad1, range1.max()+pad1] if not range1.empty else None),
            yaxis2=dict(title='设备能力利用水平', side='right', overlaying='y', range=[range2.min()-pad2, range2.max()+pad2] if not range2.empty else None),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50),
            legend=dict(x=0.02, y=0.98)
        )
        return fig
    except Exception:
        return None



# ============ 中国GDP ============
def get_china_gdp_chart():
    """获取中国GDP图表"""
    try:
        # 从china_fundamentals_page导入函数
        from src.dashboard.china_fundamentals_page import _load_china_gdp
        
        gdp = _load_china_gdp()
        
        if gdp.empty:
            return None
        
        # 取最近10年
        end_date = gdp['date'].max()
        start_date = end_date - pd.DateOffset(years=10)
        gdp = gdp[(gdp['date'] >= start_date) & (gdp['date'] <= end_date)]
        
        if gdp.empty:
            return None
        
        fig = go.Figure()
        
        # GDP折线
        fig.add_trace(go.Scatter(
            x=gdp['date'], y=gdp['gdp'],
            name='中国GDP', line=dict(color='#3498db', width=2),
            connectgaps=False
        ))
        
        # 计算Y轴范围
        gdp_range = gdp['gdp'].dropna()
        gdp_pad = (gdp_range.max() - gdp_range.min()) * 0.05 if not gdp_range.empty else 1
        
        fig.update_layout(
            title='中国GDP', xaxis=dict(title='日期'),
            yaxis=dict(title='GDP', range=[gdp_range.min()-gdp_pad, gdp_range.max()+gdp_pad] if not gdp_range.empty else None),
            template='plotly_white', height=400, margin=dict(l=50, r=50, t=50, b=50),
            legend=dict(x=0.02, y=0.98)
        )
        return fig
    except Exception:
        return None
