"""
中国基本面数据页面
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import sys, os
import time

# 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.data_fetcher.akshare_fetcher import AkShareFetcher
from src.database.db_manager import db_manager


def _ensure_month_start(s: pd.Series) -> pd.Series:
    s = pd.to_datetime(s, errors='coerce')
    return s.dt.to_period('M').dt.start_time


def _parse_month_str(x: str):
    try:
        x = str(x)
        if '年' in x and '月' in x:
            y = int(x.split('年')[0])
            m = int(x.split('年')[1].split('月')[0])
            return pd.Timestamp(year=y, month=m, day=1)
        return pd.to_datetime(x, errors='coerce')
    except Exception:
        return pd.NaT

def _ensure_date_column(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    cols = [str(c).strip() for c in df.columns]
    df.columns = cols
    date_series = None
    if 'date' in df.columns:
        date_series = pd.to_datetime(df['date'], errors='coerce')
    elif '月份' in df.columns:
        date_series = df['月份'].apply(_parse_month_str)
    elif '统计时间' in df.columns:
        date_series = df['统计时间'].apply(_parse_month_str)
    else:
        if isinstance(df.index, pd.DatetimeIndex):
            date_series = pd.to_datetime(df.index, errors='coerce')
        else:
            # 尝试把首列当作日期
            candidate = df.columns[0]
            date_series = pd.to_datetime(df[candidate], errors='coerce')
    df['date'] = date_series
    return df

def show_china_fundamentals():
    st.markdown("### 🇨🇳 中国基本面数据")
    
    # 添加数据更新按钮
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button('🔄 更新数据'):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # 更新PPI数据
                status_text.text('正在更新PPI数据...')
                progress_bar.progress(25)
                fetcher = AkShareFetcher()
                if fetcher.is_available():
                    ppi_df = fetcher.fetch_data_by_key("macro_china_ppi")
                    if ppi_df is not None and not ppi_df.empty:
                        ppi_df = _ensure_date_column(ppi_df)
                        db_manager.save_data(ppi_df, 'macro_china_ppi', if_exists='replace')
                
                # 更新M1/M2数据
                status_text.text('正在更新M1/M2数据...')
                progress_bar.progress(50)
                m1m2_df = fetcher.fetch_data_by_key("macro_china_m1m2")
                if m1m2_df is not None and not m1m2_df.empty:
                    m1m2_df = _ensure_date_column(m1m2_df)
                    db_manager.save_data(m1m2_df, 'macro_china_m1m2', if_exists='replace')
                
                # 更新国债收益率数据
                status_text.text('正在更新国债收益率数据...')
                progress_bar.progress(75)
                try:
                    import akshare as ak
                    bond = ak.bond_zh_us_rate(start_date="19900101")
                    if bond is not None and not bond.empty:
                        db_manager.save_data(bond, 'bond_zh_us_rate', if_exists='replace')
                except Exception:
                    pass
                
                progress_bar.progress(100)
                status_text.text('数据更新完成')
                time.sleep(0.5)
                
                progress_bar.empty()
                status_text.empty()
                st.success('✅ 数据更新成功')
                st.balloons()
                
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f'❌ 数据更新失败：{str(e)}')

    # 展示窗口：最近 10 年
    window_years = 10

    st.markdown("#### 📈 美元指数同比(逆序, 领先6个月) vs 中国PPI同比")

    fetcher = AkShareFetcher()
    if not fetcher.is_available():
        st.error("AkShare不可用")
        return

    # 获取PPI
    def _load_ppi_yoy_db_first() -> pd.DataFrame:
        # DB优先
        try:
            df = db_manager.load_data('macro_china_ppi')
            if df is not None and not df.empty:
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                elif '月份' in df.columns:
                    df['date'] = df['月份'].apply(_parse_month_str)
                # 识别同比列
                for c in ['ppi_yoy', '当月同比增长', '当月同比', 'PPI:当月同比']:
                    if c in df.columns:
                        df['ppi_yoy'] = pd.to_numeric(df[c], errors='coerce')
                        break
                out = df[['date', 'ppi_yoy']].dropna().sort_values('date')
                if not out.empty:
                    return out
        except Exception:
            pass
        # 接口兜底
        df = fetcher.fetch_data_by_key("macro_china_ppi")
        if df is None or df.empty:
            return pd.DataFrame(columns=['date', 'ppi_yoy'])
        df = _ensure_date_column(df)
        df = df.rename(columns={'当月同比': 'ppi_yoy', 'PPI:当月同比': 'ppi_yoy', '当月同比增长': 'ppi_yoy'})
        if 'ppi_yoy' not in df.columns:
            yoy_cols = [c for c in df.columns if '同比' in c]
            if yoy_cols:
                df['ppi_yoy'] = pd.to_numeric(df[yoy_cols[0]], errors='coerce')
        df['date'] = pd.to_datetime(df['date'])
        # 将原始结构写入DB，便于后续稳定读取
        try:
            db_manager.save_data(df, 'macro_china_ppi', if_exists='replace')
        except Exception:
            pass
        return df[['date', 'ppi_yoy']].dropna().sort_values('date')

    ppi = _load_ppi_yoy_db_first()
    if ppi is None or ppi.empty:
        st.error("PPI数据获取失败")
        return

    # 获取美元指数（多源合并，延长历史）
    dxy_candidates = ['dxy_index_data', 'dxy_index', 'openbb_dxy', 'macro_dxy_cache']
    dxy_parts: list[pd.DataFrame] = []
    for t in dxy_candidates:
        try:
            tmp = db_manager.load_data(t)
            if tmp is not None and not tmp.empty and 'date' in tmp.columns:
                dxy_parts.append(tmp[['date', 'close']].rename(columns={'close': 'dxy'}))
        except Exception:
            continue
    # FRED 兜底（DTWEXBGS）- 无依赖方案：直接请求CSV
    try:
        import urllib.request
        url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS'
        with urllib.request.urlopen(url, timeout=10) as resp:
            df = pd.read_csv(resp)
        # 列兼容
        if 'DATE' in df.columns and 'DTWEXBGS' in df.columns:
            df = df.rename(columns={'DATE': 'date', 'DTWEXBGS': 'dxy'})
            df['date'] = pd.to_datetime(df['date'])
            dxy_parts.append(df[['date', 'dxy']])
    except Exception:
        pass
    # AkShare 兜底（部分环境无该接口，异常忽略）
    try:
        import akshare as ak
        dxy_raw = getattr(ak, 'index_us_dollar')()
        if dxy_raw is not None and not dxy_raw.empty:
            dxy_raw = dxy_raw.rename(columns={'日期': 'date', '美元指数': 'dxy'})
            dxy_raw['date'] = pd.to_datetime(dxy_raw['date'])
            dxy_parts.append(dxy_raw[['date', 'dxy']])
    except Exception:
        pass

    if not dxy_parts:
        st.error("美元指数数据获取失败")
        return

    # 合并去重
    dxy = pd.concat(dxy_parts, ignore_index=True)
    dxy = dxy.dropna(subset=['date', 'dxy']).drop_duplicates(subset=['date']).sort_values('date')

    # 转月度（对齐月初）、同比、领先6个月并逆序
    dxy = dxy.set_index('date').resample('ME').last().reset_index()
    dxy['date'] = dxy['date'].dt.to_period('M').dt.start_time
    dxy['dxy_yoy'] = dxy['dxy'].pct_change(12) * 100
    dxy['date'] = dxy['date'] + pd.offsets.DateOffset(months=6)
    dxy['dxy_yoy_lead6_inv'] = -dxy['dxy_yoy']
    dxy = dxy[['date', 'dxy_yoy_lead6_inv']]

    # 使用外连接保留两条曲线的完整时间范围（PPI最晚到~2025-07，DXY向后平移后可到~2026-02）
    merged = pd.merge(ppi[['date', 'ppi_yoy']], dxy, on='date', how='outer')
    merged = merged.sort_values('date')
    # 有效可视范围提示与过滤
    if not merged.empty:
        min_d, max_d = merged['date'].min(), merged['date'].max()
        st.info(f"有效数据区间: {min_d.date()} 至 {max_d.date()}（DXY同比已向后平移6个月并取反）")
        end_d = max_d
        start_d = end_d - pd.DateOffset(years=window_years)
        merged = merged[(merged['date'] >= start_d) & (merged['date'] <= end_d)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=merged['date'], y=merged['ppi_yoy'], name='PPI同比', line=dict(color='red', width=3), connectgaps=False))
    fig.add_trace(go.Scatter(x=merged['date'], y=merged['dxy_yoy_lead6_inv'], name='美元指数同比(领先6个月, 逆序)', line=dict(color='black', width=2), yaxis='y2', connectgaps=False))

    l = merged['ppi_yoy'].dropna(); r = merged['dxy_yoy_lead6_inv'].dropna()
    lpad = (l.max()-l.min())*0.1 if not l.empty else 1
    rpad = (r.max()-r.min())*0.1 if not r.empty else 1

    fig.update_layout(
        title='美元指数同比(领先6个月, 逆序) vs 中国PPI同比',
        xaxis=dict(title='日期'),
        yaxis=dict(title='PPI同比(%)', range=[l.min()-lpad, l.max()+lpad] if not l.empty else None),
        yaxis2=dict(title='美元指数同比(%)', overlaying='y', side='right', range=[r.min()-rpad, r.max()+rpad] if not r.empty else None),
        template='plotly_white', height=520,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    st.plotly_chart(fig, use_container_width=True)


    # =============================
    # M1 同比 vs PPI 同比（测试领先关系）
    # =============================
    st.markdown("#### 📈 M1同比变化 与 中国PPI同比（可调领先期）")

    # 获取 M1（数据库优先，接口兜底）
    m1_series = pd.DataFrame(columns=['date', 'm1_yoy'])
    try:
        _m1db = db_manager.load_data('macro_china_m1m2')
    except Exception:
        _m1db = None
    if _m1db is not None and not _m1db.empty:
        _m1db.columns = [str(c).strip() for c in _m1db.columns]
        if 'date' in _m1db.columns:
            _m1db['date'] = pd.to_datetime(_m1db['date'], errors='coerce')
        elif '月份' in _m1db.columns:
            _m1db['date'] = _m1db['月份'].apply(_parse_month_str)
        m1_yoy_col = None
        _cands = ['货币(M1)-同比增长','M1-同比增长','货币(M1)同比增长','货币(M1)-同比','货币(狭义货币M1)同比增长','M1同比','M1 当月同比','m1_yoy']
        for c in _cands:
            if c in _m1db.columns:
                m1_yoy_col = c; break
        if m1_yoy_col is None:
            # 从数量列计算同比，优先级顺序
            level_candidates = ['货币(M1)-数量(亿元)', '货币(狭义货币M1)', 'M1', '货币(M1)']
            for lc in level_candidates:
                if lc in _m1db.columns:
                    _m1db = _m1db.sort_values('date')
                    _m1db['m1_yoy'] = pd.to_numeric(_m1db[lc], errors='coerce').pct_change(12)*100
                    break
        elif m1_yoy_col is not None:
            _m1db['m1_yoy'] = pd.to_numeric(_m1db[m1_yoy_col], errors='coerce')
        m1_series = _m1db[['date','m1_yoy']].dropna().sort_values('date')
    if m1_series.empty:
        m1_df = fetcher.fetch_data_by_key("macro_china_m1m2")
        if m1_df is not None and not m1_df.empty:
            m1_df = _ensure_date_column(m1_df)
            # 兼容不同列名
            m1_yoy_col_candidates = [
                '货币(M1)-同比增长', 'M1-同比增长', '货币(M1)同比增长', '货币(M1)-同比',
                '货币(M1) 当月同比', 'M1同比', 'M1 当月同比'
            ]
            m1_yoy_col = next((c for c in m1_yoy_col_candidates if c in m1_df.columns), None)
            if m1_yoy_col is None:
                fuzzy = [c for c in m1_df.columns if (("M1" in c) and ('同比' in c))]
                m1_yoy_col = fuzzy[0] if fuzzy else None
            if m1_yoy_col is not None:
                m1_series = m1_df[['date', m1_yoy_col]].rename(columns={m1_yoy_col: 'm1_yoy'})
                m1_series['m1_yoy'] = pd.to_numeric(m1_series['m1_yoy'], errors='coerce')
            else:
                # 用数量列推导
                level_candidates = ['货币(M1)-数量(亿元)', '货币(狭义货币M1)', 'M1', '货币(M1)']
                tmp = m1_df.sort_values('date').copy()
                for lc in level_candidates:
                    if lc in tmp.columns:
                        tmp['m1_yoy'] = pd.to_numeric(tmp[lc], errors='coerce').pct_change(12) * 100
                        m1_series = tmp[['date', 'm1_yoy']]
                        break
            m1_series['date'] = pd.to_datetime(m1_series['date'])
            m1_series = m1_series.dropna(subset=['date']).sort_values('date')
            # 将原始结构写入DB，便于后续稳定读取
            try:
                db_manager.save_data(m1_df, 'macro_china_m1m2', if_exists='replace')
            except Exception:
                pass

    # 计算最近10年相关性表（0..12 个月领先），并提供自动最佳领先按钮
    # 先确定最近10年窗口（以两者共有的最晚日期为准）
    if not m1_series.empty and not ppi.empty:
        end_common = min(m1_series['date'].max(), ppi['date'].max())
        start_common = end_common - pd.DateOffset(years=window_years)
        m1_10 = m1_series[(m1_series['date'] >= start_common) & (m1_series['date'] <= end_common)].copy()
        ppi_10 = ppi[(ppi['date'] >= start_common) & (ppi['date'] <= end_common)].copy()
    else:
        m1_10 = m1_series.copy()
        ppi_10 = ppi.copy()

    if not m1_series.empty and not ppi.empty:
        corr_rows = []
        for lead in range(0, 13):
            m_shift = m1_10.copy()
            m_shift['date'] = m_shift['date'] + pd.offsets.DateOffset(months=lead)
            merged10 = pd.merge(
                m_shift[['date', 'm1_yoy']].dropna(),
                ppi_10[['date', 'ppi_yoy']].dropna(),
                on='date', how='inner'
            )
            n = len(merged10)
            if n >= 24:
                corr = merged10['m1_yoy'].corr(merged10['ppi_yoy'])
                corr_rows.append({'领先(月)': lead, '样本数': n, '相关系数': corr})

        best = None
        if corr_rows:
            best = max(corr_rows, key=lambda r: abs(r['相关系数']))

        # 使用会话状态保存/驱动滑块的默认值：若存在最佳值，首次进入即采用最佳值
        if 'm1_lead_months' not in st.session_state:
            st.session_state['m1_lead_months'] = int(best['领先(月)']) if best is not None else 6

        cols = st.columns([2, 1])
        with cols[1]:
            if st.button("自动最佳领先（最近10年）"):
                if best is not None:
                    st.session_state['m1_lead_months'] = int(best['领先(月)'])

        if best is not None:
            st.caption(
                f"最近10年最佳领先 = {int(best['领先(月)'])} 个月；相关系数 = {best['相关系数']:.3f}；样本数 = {int(best['样本数'])}"
            )

        with st.expander("最近10年相关性表（0-12个月领先）", expanded=False):
            if corr_rows:
                df_corr = pd.DataFrame(corr_rows).sort_values(by='领先(月)')
                st.dataframe(df_corr, use_container_width=True)

        # 领先期调节器（受会话状态影响）
        lead_months = st.slider(
            "选择M1领先PPI的月份数", min_value=0, max_value=12,
            value=int(st.session_state.get('m1_lead_months', 6)), step=1
        )
        m1_lead = m1_series.copy()
        m1_lead['date'] = m1_lead['date'] + pd.offsets.DateOffset(months=lead_months)

        # 合并
        m1_ppi = pd.merge(
            m1_lead[['date', 'm1_yoy']].dropna(),
            ppi[['date', 'ppi_yoy']], on='date', how='outer'
        ).sort_values('date')

        # 固定展示区间
        if not m1_ppi.empty:
            min_d2, max_d2 = m1_ppi['date'].min(), m1_ppi['date'].max()
            end2 = max_d2
            start2 = end2 - pd.DateOffset(years=window_years)
            m1_ppi = m1_ppi[(m1_ppi['date'] >= start2) & (m1_ppi['date'] <= end2)]

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=m1_ppi['date'], y=m1_ppi['m1_yoy'], name=f'M1同比（领先{lead_months}个月）',
                line=dict(color='teal', width=3), connectgaps=False
            ))
            fig2.add_trace(go.Scatter(
                x=m1_ppi['date'], y=m1_ppi['ppi_yoy'], name='PPI同比',
                line=dict(color='red', width=2), yaxis='y2', connectgaps=False
            ))

            L = m1_ppi['m1_yoy'].dropna(); R = m1_ppi['ppi_yoy'].dropna()
            Lpad = (L.max()-L.min())*0.1 if not L.empty else 1
            Rpad = (R.max()-R.min())*0.1 if not R.empty else 1

            fig2.update_layout(
                title=f'M1同比（领先{lead_months}个月） vs PPI同比',
                xaxis=dict(title='日期'),
                yaxis=dict(title='M1同比(%)', range=[L.min()-Lpad, L.max()+Lpad] if not L.empty else None),
                yaxis2=dict(title='PPI同比(%)', overlaying='y', side='right', range=[R.min()-Rpad, R.max()+Rpad] if not R.empty else None),
                template='plotly_white', height=520,
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
            )

            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning('M1或PPI数据不足，无法绘图。')

    # =============================
    # 中国10Y-2Y国债利差 vs M1同比（最近10年）
    # =============================
    st.markdown("#### 📉 中国10年-2年国债利差 与 M1同比（最近10年）")

    def _seasonal_adjust_level_to_yoy(data: pd.DataFrame, date_col: str, level_col: str) -> pd.DataFrame:
        """对月度数量型数据做简易季调（比例-移动平均法），再计算同比。返回含 date, yoy_sa 列。"""
        df = data[[date_col, level_col]].dropna().copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)
        # 月度对齐到月初
        df[date_col] = df[date_col].dt.to_period('M').dt.start_time
        # 12期中心移动平均
        df['ma12'] = df[level_col].rolling(window=12, center=True, min_periods=10).mean()
        # 季节比率
        df['ratio'] = df[level_col] / df['ma12']
        # 按月份求平均季节因子
        df['month'] = df[date_col].dt.month
        seas = df.dropna(subset=['ratio']).groupby('month')['ratio'].mean()
        if len(seas) == 12:
            seas = seas / seas.mean()
            df['seas_factor'] = df['month'].map(seas)
            df['level_sa'] = df[level_col] / df['seas_factor']
        else:
            # 数据不足：不做季调
            df['level_sa'] = df[level_col]
        df['yoy_sa'] = df['level_sa'].pct_change(12) * 100
        return df.rename(columns={date_col: 'date'})[['date', 'yoy_sa']].dropna()

    # 获取中国国债收益率（10Y、2Y）并计算利差
    cn_spread = None
    try:
        import akshare as ak
        # 拉长起点，确保有足够样本
        bond = ak.bond_zh_us_rate(start_date="19900101")
        # 兼容列名
        # 常见列：'日期', '中国国债收益率10年', '中国国债收益率2年', 也可能包含美国列
        if '日期' in bond.columns:
            bond['date'] = pd.to_datetime(bond['日期'], errors='coerce')
        elif 'date' in bond.columns:
            bond['date'] = pd.to_datetime(bond['date'], errors='coerce')
        # 寻找10Y/2Y列
        cols = list(bond.columns)
        def _find_col(tokens):
            for c in cols:
                ok = True
                for t in tokens:
                    if t not in str(c):
                        ok = False; break
                if ok:
                    return c
            return None
        col_10y = _find_col(['中国', '10']) or _find_col(['国债', '10'])
        col_2y = _find_col(['中国', '2']) or _find_col(['国债', '2'])
        if col_10y and col_2y:
            tmp = bond[['date', col_10y, col_2y]].copy()
            tmp[col_10y] = pd.to_numeric(tmp[col_10y], errors='coerce')
            tmp[col_2y] = pd.to_numeric(tmp[col_2y], errors='coerce')
            # 转月度（取月末），并对齐到月初
            tmp = tmp.dropna(subset=['date']).sort_values('date')
            tmp = tmp.set_index('date').resample('ME').last().reset_index()
            tmp['date'] = tmp['date'].dt.to_period('M').dt.start_time
            tmp['cn_spread'] = tmp[col_10y] - tmp[col_2y]
            cn_spread = tmp[['date', 'cn_spread']].dropna()
    except Exception:
        cn_spread = None

    # 获取 M1 原始数量列（用于季调）- 数据库优先
    m1_level = None
    try:
        m1_src = db_manager.load_data('macro_china_m1m2')
        if (m1_src is None) or m1_src.empty:
            m1_src = fetcher.fetch_data_by_key("macro_china_m1m2")
        if m1_src is not None and not m1_src.empty:
            if '月份' in m1_src.columns:
                m1_src['date'] = m1_src['月份'].apply(_parse_month_str)
            elif 'date' in m1_src.columns:
                m1_src['date'] = pd.to_datetime(m1_src['date'], errors='coerce')
            # 寻找数量列
            qty_candidates = [
                '货币(M1)-数量(亿元)', '货币(狭义货币M1)', 'M1', '货币(M1)'
            ]
            qty_col = next((c for c in qty_candidates if c in m1_src.columns), None)
            if qty_col is None:
                # 模糊匹配：包含 M1 且包含 数量/亿元
                maybe = [c for c in m1_src.columns if ('M1' in c and ('数量' in c or '亿元' in c))]
                qty_col = maybe[0] if maybe else None
            if qty_col is not None:
                m1_level = m1_src[['date', qty_col]].rename(columns={qty_col: 'm1_level'})
                m1_level['m1_level'] = pd.to_numeric(m1_level['m1_level'], errors='coerce')
                m1_level = m1_level.dropna(subset=['date']).sort_values('date')
    except Exception:
        m1_level = None

    if m1_level is None or m1_level.empty:
        st.warning('M1数量级别数据缺失，季调可能不充分；将回退到未季调同比。')
        # 使用上方已算好的 m1_series 的同比（若存在）作为兜底
        if 'm1_series' in locals() and not m1_series.empty:
            m1_sa_yoy = m1_series[['date', 'm1_yoy']].rename(columns={'m1_yoy': 'm1_yoy_sa'})
        else:
            m1_sa_yoy = pd.DataFrame(columns=['date', 'm1_yoy_sa'])
    else:
        m1_sa_yoy = _seasonal_adjust_level_to_yoy(m1_level, 'date', 'm1_level').rename(columns={'yoy_sa': 'm1_yoy_sa'})

    if cn_spread is not None and not cn_spread.empty and not m1_series.empty:
        # 最近10年窗口
        end_d = min(cn_spread['date'].max(), m1_series['date'].max())
        start_d = end_d - pd.DateOffset(years=window_years)
        sp10 = cn_spread[(cn_spread['date'] >= start_d) & (cn_spread['date'] <= end_d)].copy()
        m110 = m1_series[(m1_series['date'] >= start_d) & (m1_series['date'] <= end_d)].copy()

        # 计算最近10年相关性（利差领先0..12个月）
        rows = []
        for lead in range(0, 13):
            s = sp10.copy(); s['date'] = s['date'] + pd.offsets.DateOffset(months=lead)
            M = pd.merge(s, m110, on='date', how='inner').dropna()
            n = len(M)
            if n >= 24:
                rows.append({'领先(月)': lead, '样本数': n, '相关系数': M['cn_spread'].corr(M['m1_yoy'])})

        best2 = max(rows, key=lambda r: abs(r['相关系数'])) if rows else None

        # 默认使用最佳领先
        key_state = 'cn_spread_lead_months'
        if key_state not in st.session_state:
            # 按需求默认展示 11 个月领先
            st.session_state[key_state] = 11

        c1, c2 = st.columns([2, 1])
        with c2:
            if st.button('自动最佳领先（最近10年）- 国债利差→M1'):
                if best2:
                    st.session_state[key_state] = int(best2['领先(月)'])

        if best2:
            st.caption(f"最近10年最佳领先 = {int(best2['领先(月)'])} 个月；相关系数 = {best2['相关系数']:.3f}；样本数 = {int(best2['样本数'])}")

        with st.expander('最近10年相关性表（利差领先0-12个月）', expanded=False):
            if rows:
                st.dataframe(pd.DataFrame(rows).sort_values('领先(月)'), use_container_width=True)

        lead2 = st.slider('选择利差领先M1的月份数', min_value=0, max_value=12, value=int(st.session_state.get(key_state, 0)), step=1)

        sp_lead = sp10.copy(); sp_lead['date'] = sp_lead['date'] + pd.offsets.DateOffset(months=lead2)
        merged2 = pd.merge(sp_lead, m110, on='date', how='outer').sort_values('date')

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=merged2['date'], y=merged2['cn_spread'], name=f'中国10Y-2Y利差（领先{lead2}个月）', line=dict(color='royalblue', width=3), connectgaps=False))
        fig3.add_trace(go.Scatter(x=merged2['date'], y=merged2['m1_yoy'], name='M1同比', line=dict(color='teal', width=2), yaxis='y2', connectgaps=False))

        L = merged2['cn_spread'].dropna(); R = merged2['m1_yoy'].dropna()
        Lpad = (L.max()-L.min())*0.05 if not L.empty else 1
        Rpad = (R.max()-R.min())*0.05 if not R.empty else 1

        fig3.update_layout(
            title=f'中国10年-2年国债利差 vs M1同比',
            xaxis=dict(title='日期'),
            yaxis=dict(title='利差(百分点)', range=[L.min()-Lpad, L.max()+Lpad] if not L.empty else None, zeroline=True, zerolinewidth=1, zerolinecolor='lightgray'),
            yaxis2=dict(title='M1同比(%)', overlaying='y', side='right', range=[R.min()-Rpad, R.max()+Rpad] if not R.empty else None, zeroline=True, zerolinewidth=1, zerolinecolor='lightgray'),
            template='plotly_white', height=520,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning('国债利差或M1同比数据不足，无法绘图。')

    st.markdown('---')
    st.markdown('#### 📦 中国库存同比变化（库存周期）')
    
    # 添加同步按钮
    if st.button('🔄 同步Wind库存数据'):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text('正在初始化Wind API...')
            progress_bar.progress(10)
            
            import WindPy
            w = WindPy.w
            
            # 检查Wind API是否可用
            status_text.text('正在连接Wind API...')
            progress_bar.progress(20)
            
            try:
                if not w.isconnected():
                    w.start()
                if not w.isconnected():
                    progress_bar.empty()
                    status_text.empty()
                    st.error('❌ Wind API连接失败：请确保Wind API应用已启动并已登录')
                    st.info('💡 提示：使用Wind API需要：\n1. 安装Wind API应用\n2. 启动Wind API应用并登录\n3. 确保Wind API应用保持运行状态')
                    return
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f'❌ Wind API初始化失败：{str(e)}')
                st.info('💡 提示：请确保已安装Wind API应用并启动')
                return
            
            # 获取库存数据
            status_text.text('正在获取库存同比数据 (M0000561)...')
            progress_bar.progress(60)
            inventory = _load_china_inventory_yoy()
            
            progress_bar.progress(100)
            status_text.text('数据处理完成')
            time.sleep(0.5)
            
            progress_bar.empty()
            status_text.empty()
            
            if not inventory.empty:
                st.success(f'✅ 库存同比数据: {len(inventory)}条记录，日期范围: {inventory["date"].min().strftime("%Y-%m")} 至 {inventory["date"].max().strftime("%Y-%m")}')
                st.balloons()
            else:
                st.error('❌ 库存数据获取失败：请检查Wind API连接')
        except ImportError:
            progress_bar.empty()
            status_text.empty()
            st.error('❌ WindPy模块未安装')
            st.info('💡 请先安装WindPy模块：\n1. 从Wind官网下载并安装Wind API应用\n2. 运行安装脚本：python3.12 install_windpy.py\n3. 重启Python环境')
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f'❌ 数据获取失败：{str(e)}')
            import traceback
            st.code(traceback.format_exc())
    
    fig4 = get_china_inventory_chart()
    if fig4:
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.warning('库存数据不足，无法绘图。请先点击"同步Wind库存数据"按钮获取数据。')

    st.markdown('---')
    st.markdown('#### 📊 中国朱格拉周期（5000户工业企业景气扩散指数）')
    
    # 添加同步按钮
    if st.button('🔄 同步Wind数据（M0043718 & M0043728）'):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text('正在初始化Wind API...')
            progress_bar.progress(10)
            
            import WindPy
            w = WindPy.w
            
            # 检查Wind API是否可用
            status_text.text('正在连接Wind API...')
            progress_bar.progress(20)
            
            try:
                if not w.isconnected():
                    w.start()
                if not w.isconnected():
                    progress_bar.empty()
                    status_text.empty()
                    st.error('❌ Wind API连接失败：请确保Wind API应用已启动并已登录')
                    st.info('💡 提示：使用Wind API需要：\n1. 安装Wind API应用\n2. 启动Wind API应用并登录\n3. 确保Wind API应用保持运行状态')
                    return
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f'❌ Wind API初始化失败：{str(e)}')
                st.info('💡 提示：请确保已安装Wind API应用并启动')
                return
            
            # 获取数据
            status_text.text('正在获取数据 (固定资产投资情况 & 设备能力利用水平)...')
            progress_bar.progress(60)
            data_df = _load_m0043718_m0043728()
            
            progress_bar.progress(100)
            status_text.text('数据处理完成')
            time.sleep(0.5)
            
            progress_bar.empty()
            status_text.empty()
            
            if not data_df.empty:
                st.success(f'✅ 数据获取成功: {len(data_df)}条记录，日期范围: {data_df["date"].min().strftime("%Y-%m")} 至 {data_df["date"].max().strftime("%Y-%m")}')
                st.balloons()
            else:
                st.error('❌ 数据获取失败：请检查Wind API连接')
        except ImportError:
            progress_bar.empty()
            status_text.empty()
            st.error('❌ WindPy模块未安装')
            st.info('💡 请先安装WindPy模块：\n1. 从Wind官网下载并安装Wind API应用\n2. 运行安装脚本：python3.12 install_windpy.py\n3. 重启Python环境')
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f'❌ 数据获取失败：{str(e)}')
            import traceback
            st.code(traceback.format_exc())
    
    fig5 = get_m0043718_m0043728_chart()
    if fig5:
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.warning('数据不足，无法绘图。请先点击"同步Wind数据"按钮获取数据。')


def _load_china_inventory_yoy() -> pd.DataFrame:
    """加载中国库存同比数据 - 数据库优先，Wind API兜底"""
    # DB优先
    try:
        df = db_manager.load_data('china_inventory_yoy')
        if df is not None and not df.empty:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df[['date', 'value']].rename(columns={'value': 'inventory_yoy'})
                df['inventory_yoy'] = pd.to_numeric(df['inventory_yoy'], errors='coerce')
                df = df.dropna().sort_values('date')
                df['date'] = _ensure_month_start(df['date'])
                return df
    except Exception:
        pass
    
    # Wind API兜底
    try:
        try:
            import WindPy
            w = WindPy.w
        except ImportError:
            return pd.DataFrame(columns=['date', 'inventory_yoy'])
        
        # 启动Wind API（如果未连接）
        try:
            if not w.isconnected():
                w.start()
            if not w.isconnected():
                return pd.DataFrame(columns=['date', 'inventory_yoy'])
        except Exception as e:
            return pd.DataFrame(columns=['date', 'inventory_yoy'])
        
        # 获取10年历史数据
        end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
        start_date = (pd.Timestamp.now() - pd.DateOffset(years=10)).strftime('%Y-%m-%d')
        
        # 中国库存同比: M0000561
        data = w.edb("M0000561", start_date, end_date, "Fill=Previous")
        
        # 检查返回结果
        if not hasattr(data, 'ErrorCode'):
            return pd.DataFrame(columns=['date', 'inventory_yoy'])
        
        if data.ErrorCode != 0:
            return pd.DataFrame(columns=['date', 'inventory_yoy'])
        
        if not data.Data or len(data.Data) == 0 or not data.Times:
            return pd.DataFrame(columns=['date', 'inventory_yoy'])
        
        dates = pd.to_datetime(data.Times)
        values = pd.Series(data.Data[0])
        df = pd.DataFrame({'date': dates, 'inventory_yoy': values})
        df['inventory_yoy'] = pd.to_numeric(df['inventory_yoy'], errors='coerce')
        df = df.dropna().sort_values('date')
        df['date'] = _ensure_month_start(df['date'])
        
        # 保存到数据库
        try:
            db_manager.save_data(df.rename(columns={'inventory_yoy': 'value'}), 
                                'china_inventory_yoy', if_exists='replace')
        except Exception:
            pass
        
        return df
    except Exception as e:
        return pd.DataFrame(columns=['date', 'inventory_yoy'])


def get_china_inventory_chart() -> go.Figure:
    """获取中国库存同比变化图表"""
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
        title='中国库存同比变化（库存周期）',
        xaxis=dict(title='日期'),
        yaxis=dict(title='库存同比(%)', range=[inv_range.min()-inv_pad, inv_range.max()+inv_pad] if not inv_range.empty else None, zeroline=True),
        template='plotly_white',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(x=0.02, y=0.98)
    )
    return fig


def _load_m0043718_m0043728() -> pd.DataFrame:
    """加载M0043718和M0043728数据 - 数据库优先，Wind API兜底"""
    # DB优先
    try:
        df = db_manager.load_data('m0043718_m0043728')
        if df is not None and not df.empty:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                # 检查列名
                if 'm0043718' in df.columns and 'm0043728' in df.columns:
                    df = df[['date', 'm0043718', 'm0043728']]
                elif 'value' in df.columns and 'value2' in df.columns:
                    df = df.rename(columns={'value': 'm0043718', 'value2': 'm0043728'})
                    df = df[['date', 'm0043718', 'm0043728']]
                else:
                    # 尝试从多个value列推断
                    cols = [c for c in df.columns if c != 'date']
                    if len(cols) >= 2:
                        df = df.rename(columns={cols[0]: 'm0043718', cols[1]: 'm0043728'})
                        df = df[['date', 'm0043718', 'm0043728']]
                df['m0043718'] = pd.to_numeric(df['m0043718'], errors='coerce')
                df['m0043728'] = pd.to_numeric(df['m0043728'], errors='coerce')
                df = df.dropna().sort_values('date')
                df['date'] = _ensure_month_start(df['date'])
                return df
    except Exception:
        pass
    
    # Wind API兜底
    try:
        try:
            import WindPy
            w = WindPy.w
        except ImportError:
            return pd.DataFrame(columns=['date', 'm0043718', 'm0043728'])
        
        # 启动Wind API（如果未连接）
        try:
            if not w.isconnected():
                w.start()
            if not w.isconnected():
                return pd.DataFrame(columns=['date', 'm0043718', 'm0043728'])
        except Exception as e:
            return pd.DataFrame(columns=['date', 'm0043718', 'm0043728'])
        
        # 获取10年历史数据
        end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
        start_date = (pd.Timestamp.now() - pd.DateOffset(years=10)).strftime('%Y-%m-%d')
        
        # M0043718, M0043728
        data = w.edb("M0043718,M0043728", start_date, end_date, "Fill=Previous")
        
        # 检查返回结果
        if not hasattr(data, 'ErrorCode'):
            return pd.DataFrame(columns=['date', 'm0043718', 'm0043728'])
        
        if data.ErrorCode != 0:
            return pd.DataFrame(columns=['date', 'm0043718', 'm0043728'])
        
        if not data.Data or len(data.Data) < 2 or not data.Times:
            return pd.DataFrame(columns=['date', 'm0043718', 'm0043728'])
        
        dates = pd.to_datetime(data.Times)
        values1 = pd.Series(data.Data[0])
        values2 = pd.Series(data.Data[1])
        df = pd.DataFrame({
            'date': dates, 
            'm0043718': values1,
            'm0043728': values2
        })
        df['m0043718'] = pd.to_numeric(df['m0043718'], errors='coerce')
        df['m0043728'] = pd.to_numeric(df['m0043728'], errors='coerce')
        df = df.dropna().sort_values('date')
        df['date'] = _ensure_month_start(df['date'])
        
        # 保存到数据库
        try:
            db_manager.save_data(df.rename(columns={'m0043718': 'value', 'm0043728': 'value2'}), 
                                'm0043718_m0043728', if_exists='replace')
        except Exception:
            pass
        
        return df
    except Exception as e:
        return pd.DataFrame(columns=['date', 'm0043718', 'm0043728'])


def get_m0043718_m0043728_chart() -> go.Figure:
    """获取M0043718 vs M0043728对比图表（双折线图）"""
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
        title='中国朱格拉周期（5000户工业企业景气扩散指数）',
        xaxis=dict(title='日期'),
        yaxis=dict(title='固定资产投资情况', range=[range1.min()-pad1, range1.max()+pad1] if not range1.empty else None),
        yaxis2=dict(title='设备能力利用水平', side='right', overlaying='y', range=[range2.min()-pad2, range2.max()+pad2] if not range2.empty else None),
        template='plotly_white',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(x=0.02, y=0.98)
    )
    return fig



def _load_china_gdp() -> pd.DataFrame:
    """加载中国GDP数据 - 数据库优先，Wind API兜底"""
    # DB优先
    try:
        df = db_manager.load_data('china_gdp')
        if df is not None and not df.empty:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df[['date', 'value']].rename(columns={'value': 'gdp'})
                df['gdp'] = pd.to_numeric(df['gdp'], errors='coerce')
                df = df.dropna().sort_values('date')
                df['date'] = _ensure_month_start(df['date'])
                return df
    except Exception:
        pass
    
    # Wind API兜底
    try:
        try:
            import WindPy
            w = WindPy.w
        except ImportError:
            return pd.DataFrame(columns=['date', 'gdp'])
        
        # 启动Wind API（如果未连接）
        try:
            if not w.isconnected():
                w.start()
            if not w.isconnected():
                return pd.DataFrame(columns=['date', 'gdp'])
        except Exception as e:
            return pd.DataFrame(columns=['date', 'gdp'])
        
        # 获取10年历史数据
        end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
        start_date = (pd.Timestamp.now() - pd.DateOffset(years=10)).strftime('%Y-%m-%d')
        
        # 中国GDP: M5567876
        data = w.edb("M5567876", start_date, end_date, "Fill=Previous")
        
        # 检查返回结果
        if not hasattr(data, 'ErrorCode'):
            return pd.DataFrame(columns=['date', 'gdp'])
        
        if data.ErrorCode != 0:
            return pd.DataFrame(columns=['date', 'gdp'])
        
        if not data.Data or len(data.Data) == 0 or not data.Times:
            return pd.DataFrame(columns=['date', 'gdp'])
        
        dates = pd.to_datetime(data.Times)
        values = pd.Series(data.Data[0])
        df = pd.DataFrame({'date': dates, 'gdp': values})
        df['gdp'] = pd.to_numeric(df['gdp'], errors='coerce')
        df = df.dropna().sort_values('date')
        df['date'] = _ensure_month_start(df['date'])
        
        # 保存到数据库
        try:
            db_manager.save_data(df.rename(columns={'gdp': 'value'}), 
                                'china_gdp', if_exists='replace')
        except Exception:
            pass
        
        return df
    except Exception as e:
        return pd.DataFrame(columns=['date', 'gdp'])


def get_china_gdp_chart() -> go.Figure:
    """获取中国GDP图表"""
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
        title='中国GDP',
        xaxis=dict(title='日期'),
        yaxis=dict(title='GDP', range=[gdp_range.min()-gdp_pad, gdp_range.max()+gdp_pad] if not gdp_range.empty else None),
        template='plotly_white',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(x=0.02, y=0.98)
    )
    return fig
