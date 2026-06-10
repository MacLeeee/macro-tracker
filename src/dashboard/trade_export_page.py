import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os, json, re, io, ssl, urllib.request, urllib.parse, time

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.database.db_manager import db_manager

def _parse_month_str(x: str):
    x = str(x)
    if '年' in x and '月' in x:
        y = int(x.split('年')[0]); m = int(x.split('年')[1].split('月')[0])
        return pd.Timestamp(year=y, month=m, day=1)
    return pd.to_datetime(x, errors='coerce')

def _ensure_date_column(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df.columns = [str(c).strip() for c in df.columns]
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    elif '月份' in df.columns:
        df['date'] = df['月份'].apply(_parse_month_str)
    elif '统计时间' in df.columns:
        df['date'] = df['统计时间'].apply(_parse_month_str)
    else:
        if isinstance(df.index, pd.DatetimeIndex):
            df['date'] = pd.to_datetime(df.index, errors='coerce')
        else:
            df['date'] = pd.to_datetime(df.iloc[:,0], errors='coerce')
    return df

def _rolling12_yoy(df: pd.DataFrame, date_col: str, value_col: str) -> pd.DataFrame:
    x = df[[date_col, value_col]].dropna().copy()
    x[date_col] = pd.to_datetime(x[date_col])
    x = x.sort_values(date_col)
    x[date_col] = x[date_col].dt.to_period('M').dt.start_time
    x['roll12'] = pd.to_numeric(x[value_col], errors='coerce').rolling(12, min_periods=12).sum()
    x['roll12_yoy'] = (x['roll12'] / x['roll12'].shift(12) - 1.0) * 100
    return x[[date_col, 'roll12_yoy']].rename(columns={date_col: 'date'})

# =============================
# CPB WTM（世界贸易量）获取与解析
# =============================

def _load_wtm_from_db() -> pd.DataFrame:
    try:
        prev = db_manager.load_data('cpb_wtm_world_trade')
        if prev is not None and not prev.empty and 'date' in prev.columns:
            return prev[['date','wtv_index']].dropna().sort_values('date')
    except Exception:
        pass
    return pd.DataFrame(columns=['date','wtv_index'])

def _discover_wtm_xlsx_url() -> str:
    candidates_pages = [
        # 用户提供的示例页（优先）
        'https://www.cpb.nl/en/wtm/cpb-world-trade-monitor-may-2025',
        # 聚合入口页（可能含最新月报链接）
        'https://www.cpb.nl/en/world-trade-monitor',
        'https://www.cpb.nl/en/wtm',
        'https://www.cpb.nl/en/wtm/cpb-world-trade-monitor',
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}
    ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    for page in candidates_pages:
        try:
            req = urllib.request.Request(page, headers=headers)
            with urllib.request.urlopen(req, timeout=15, context=ctx if page.startswith('https') else None) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            # 抓取页面内所有 .xlsx 链接
            hrefs = re.findall(r'href=["\']([^"\']+\.xlsx)["\']', html, flags=re.I)
            if not hrefs:
                continue
            # 评分：包含 wtm/world/trade/database 关键词优先
            def score(u: str) -> int:
                s = u.lower()
                return sum(kw in s for kw in ['wtm', 'world', 'trade', 'database'])
            hrefs = sorted(hrefs, key=lambda u: score(u), reverse=True)
            url = hrefs[0]
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                base = re.match(r'^(https?://[^/]+)', page)
                if base:
                    url = base.group(1) + url
            return url
        except Exception:
            continue
    return ''

def _download_wtm_xlsx(xlsx_url: str) -> bytes:
    if not xlsx_url:
        return b''
    headers = {'User-Agent': 'Mozilla/5.0'}
    ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    for _ in range(2):
        try:
            req = urllib.request.Request(xlsx_url, headers=headers)
            with urllib.request.urlopen(req, timeout=25, context=ctx if xlsx_url.startswith('https') else None) as resp:
                return resp.read()
        except Exception:
            time.sleep(1)
            continue
    return b''

def _parse_wtm_excel(file_bytes: bytes) -> pd.DataFrame:
    if not file_bytes:
        return pd.DataFrame(columns=['date','wtv_index'])
    try:
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
    except Exception:
        return pd.DataFrame(columns=['date','wtv_index'])

    def _parse_pivot(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=['date','wtv_index'])
        # 查找月份列头所在行（形如 2000m01）
        header_row_idx = None
        month_pat = re.compile(r'^\d{4}m\d{2}$', re.I)
        for ridx in range(min(40, len(df))):
            row_vals = [str(x).strip() for x in list(df.iloc[ridx].values)]
            if any(month_pat.match(v) for v in row_vals):
                header_row_idx = ridx
                break
        if header_row_idx is None:
            return pd.DataFrame(columns=['date','wtv_index'])
        headers = [str(x).strip() for x in list(df.iloc[header_row_idx].values)]
        month_cols = [(ci, h) for ci, h in enumerate(headers) if month_pat.match(h)]
        if not month_cols:
            return pd.DataFrame(columns=['date','wtv_index'])
        # 查找“World trade”所在行
        world_row_idx = None
        for ridx in range(header_row_idx+1, min(header_row_idx+200, len(df))):
            row_vals = [str(x).lower() for x in list(df.iloc[ridx].values)[:10]]
            if any(('world trade' in v) for v in row_vals) or any(('tgz_w1' in v) for v in row_vals):
                world_row_idx = ridx
                break
        if world_row_idx is None:
            return pd.DataFrame(columns=['date','wtv_index'])
        # 提取该行各月份数值
        records = []
        for ci, label in month_cols:
            val = df.iat[world_row_idx, ci]
            try:
                y = int(label[:4]); m = int(label[-2:])
                dt = pd.Timestamp(year=y, month=m, day=1)
            except Exception:
                continue
            records.append((dt, pd.to_numeric(val, errors='coerce')))
        out = pd.DataFrame(records, columns=['date','wtv_index']).dropna().sort_values('date')
        return out

    best = pd.DataFrame()
    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet, header=None)
            if df is None or df.empty:
                continue
            # 先尝试透视表结构解析
            out = _parse_pivot(df)
            if out.empty:
                # 再尝试“date+value”直列结构
                df2 = xl.parse(sheet)
                df2 = _ensure_date_column(df2)
                if 'date' not in df2.columns:
                    continue
                num_cols = [c for c in df2.columns if c != 'date']
                ranked = []
                for c in num_cols:
                    s = str(c).lower(); score = sum(kw in s for kw in ['world','trade','volume','wtm','index'])
                    ranked.append((score, c))
                ranked.sort(reverse=True)
                target_col = ranked[0][1] if ranked else (num_cols[0] if num_cols else None)
                if target_col is None:
                    continue
                out = df2[['date', target_col]].rename(columns={target_col:'wtv_index'})
                out['wtv_index'] = pd.to_numeric(out['wtv_index'], errors='coerce')
                out = out.dropna().sort_values('date')
            if len(out) > len(best):
                best = out
        except Exception:
            continue
    if best.empty:
        return best
    # 统一到月初
    best['date'] = pd.to_datetime(best['date'], errors='coerce')
    best['date'] = best['date'].dt.to_period('M').dt.start_time
    best = best.dropna().drop_duplicates(subset=['date']).sort_values('date')
    return best[['date','wtv_index']]

def _sync_cpb_wtm() -> pd.DataFrame:
    url = _discover_wtm_xlsx_url()
    data = _download_wtm_xlsx(url)
    wtm = _parse_wtm_excel(data)
    if not wtm.empty:
        # 增量合并
        try:
            prev = db_manager.load_data('cpb_wtm_world_trade')
            if prev is not None and not prev.empty:
                prev = prev[['date','wtv_index']]
                wtm = pd.concat([prev, wtm], ignore_index=True)
                wtm = wtm.drop_duplicates(subset=['date'], keep='last').sort_values('date')
        except Exception:
            pass
        db_manager.save_data(wtm, 'cpb_wtm_world_trade', if_exists='replace')
    return wtm

def _load_export_12m_yoy() -> pd.DataFrame:
    # DB优先
    try:
        prev = db_manager.load_data('china_export_12m_yoy')
        if prev is not None and not prev.empty:
            return prev[['date','export_12m_yoy']].dropna().sort_values('date')
    except Exception:
        pass
    # 接口兜底
    try:
        import akshare as ak
        exp = ak.macro_china_hgjck()
        exp = _ensure_date_column(exp)
        candidates = [c for c in exp.columns if ('出口' in str(c) and ('当月' in str(c) or '当月值' in str(c) or '当月-金额' in str(c) or '金额' in str(c)))]
        value_col = candidates[0] if candidates else None
        if value_col is None:
            maybe = [c for c in exp.columns if ('出口' in str(c))]
            value_col = maybe[0] if maybe else None
        if value_col is None:
            return pd.DataFrame(columns=['date','export_12m_yoy'])
        out = _rolling12_yoy(exp, 'date', value_col).rename(columns={'roll12_yoy':'export_12m_yoy'})
        out = out.dropna().sort_values('date')
        try:
            db_manager.save_data(out, 'china_export_12m_yoy', if_exists='replace')
        except Exception:
            pass
        return out
    except Exception:
        return pd.DataFrame(columns=['date','export_12m_yoy'])

def _load_profit_12m_cuml_yoy() -> pd.DataFrame:
    """仅从数据库读取利润近12月累计增速，若没有则返回空，供手动导入。"""
    try:
        prev = db_manager.load_data('china_industrial_profit_cuml_yoy')
        if prev is not None and not prev.empty:
            return prev[['date','profit_12m_cuml_yoy']].dropna().sort_values('date')
    except Exception:
        pass
    return pd.DataFrame(columns=['date','profit_12m_cuml_yoy'])

def _ytd_to_month_value(df: pd.DataFrame, date_col: str, ytd_col: str) -> pd.DataFrame:
    x = df[[date_col, ytd_col]].dropna().copy()
    x[date_col] = pd.to_datetime(x[date_col])
    x = x.sort_values(date_col)
    x[date_col] = x[date_col].dt.to_period('M').dt.start_time
    x['year'] = x[date_col].dt.year
    x['ytd'] = pd.to_numeric(x[ytd_col], errors='coerce')
    # 年内差分，年首当月值=当月累计
    x['month_value'] = x.groupby('year')['ytd'].diff().fillna(x['ytd'])
    return x[[date_col,'month_value']].rename(columns={date_col:'date'})

def show_trade_export():
    st.markdown("### 🚢 贸易出口数据")
    st.markdown("#### 🏭 工业企业利润近12月累计增速（领先6个月） vs 出口近12月累计增速")

    window_years = 10
    export_12m = _load_export_12m_yoy()
    profit_12m = _load_profit_12m_cuml_yoy()

    # （此处不展示WTM；改为放在下方利润图后）

    # 文件上传：导入“工业企业利润总额_累计值”并转换为近12月累计增速
    with st.expander('手动导入工业企业利润数据（CSV/Excel）', expanded=profit_12m.empty):
        up = st.file_uploader('选择文件（包含日期列与“工业企业利润总额_累计值”等累计列）', type=['csv','xlsx','xls'])
        if up is not None:
            try:
                if up.name.lower().endswith('.csv'):
                    raw = pd.read_csv(up)
                else:
                    raw = pd.read_excel(up)
                raw = _ensure_date_column(raw)
                # 选择累计值列
                candidates = [c for c in raw.columns if ('工业' in str(c) and '利润' in str(c) and ('累计' in str(c) or '累计值' in str(c)))]
                value_col = candidates[0] if candidates else None
                if value_col is None:
                    # 退而求其次：第二列或数值列
                    num_cols = [c for c in raw.columns if c != 'date']
                    value_col = num_cols[1] if len(num_cols) > 1 else (num_cols[0] if num_cols else None)
                if value_col is None:
                    st.error('未识别到累计值列，请检查文件列名。')
                else:
                    mv = _ytd_to_month_value(raw, 'date', value_col)
                    prof = _rolling12_yoy(mv, 'date', 'month_value').rename(columns={'roll12_yoy':'profit_12m_cuml_yoy'})
                    prof = prof.dropna().sort_values('date')
                    # 与DB增量合并并写库
                    try:
                        prev = db_manager.load_data('china_industrial_profit_cuml_yoy')
                        if prev is not None and not prev.empty:
                            prof = pd.concat([prev[['date','profit_12m_cuml_yoy']], prof], ignore_index=True)
                            prof = prof.drop_duplicates(subset=['date'], keep='last').sort_values('date')
                    except Exception:
                        pass
                    db_manager.save_data(prof, 'china_industrial_profit_cuml_yoy', if_exists='replace')
                    profit_12m = prof
                    st.success(f'已导入并缓存：{len(profit_12m)} 行，最近日期 {profit_12m["date"].max().date()}')
            except Exception as e:
                st.error(f'导入失败: {e}')

    if export_12m.empty and profit_12m.empty:
        st.warning('出口与工业企业利润数据均不足，无法绘图。')
        return

    # 提供一键重试抓取利润数据
    col_retry, _ = st.columns([1,3])
    with col_retry:
        st.caption('提示：利润数据支持手动导入 CSV/Excel，系统不再自动爬取统计局。')

    if profit_12m.empty and not export_12m.empty:
        # 仅展示出口12月累计增速
        end_d = export_12m['date'].max()
        start_d = end_d - pd.DateOffset(years=10)
        e10 = export_12m[(export_12m['date'] >= start_d) & (export_12m['date'] <= end_d)].copy()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=e10['date'], y=e10['export_12m_yoy'], name='出口近12月累计增速(%)', line=dict(color='orange', width=3), connectgaps=False))
        L = e10['export_12m_yoy'].dropna(); Lpad = (L.max()-L.min())*0.1 if not L.empty else 1
        fig.update_layout(title='出口近12月累计增速', xaxis=dict(title='日期'), yaxis=dict(title='出口近12月累计增速(%)', range=[L.min()-Lpad, L.max()+Lpad] if not L.empty else None), template='plotly_white', height=480)
        st.info('工业企业利润数据暂缺，已先展示出口序列。')
        st.plotly_chart(fig, use_container_width=True)
        return

    end_d = min(export_12m['date'].max(), profit_12m['date'].max())
    start_d = end_d - pd.DateOffset(years=window_years)
    e10 = export_12m[(export_12m['date'] >= start_d) & (export_12m['date'] <= end_d)].copy()
    p10 = profit_12m[(profit_12m['date'] >= start_d) & (profit_12m['date'] <= end_d)].copy()
    p10_lead = p10.copy(); p10_lead['date'] = p10_lead['date'] + pd.offsets.DateOffset(months=6)
    merged = pd.merge(e10, p10_lead, on='date', how='outer').sort_values('date')

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=merged['date'], y=merged['export_12m_yoy'], name='出口近12月累计增速(%)', line=dict(color='orange', width=3), connectgaps=False))
    fig.add_trace(go.Scatter(x=merged['date'], y=merged['profit_12m_cuml_yoy'], name='工业企业利润近12月累计增速(领先6个月)(%)', line=dict(color='purple', width=2), yaxis='y2', connectgaps=False))

    L = merged['export_12m_yoy'].dropna(); R = merged['profit_12m_cuml_yoy'].dropna()
    Lpad = (L.max()-L.min())*0.1 if not L.empty else 1
    Rpad = (R.max()-R.min())*0.1 if not R.empty else 1

    fig.update_layout(
        title='工业企业利润近12月累计增速（领先6个月） vs 出口近12月累计增速',
        xaxis=dict(title='日期'),
        yaxis=dict(title='出口近12月累计增速(%)', range=[L.min()-Lpad, L.max()+Lpad] if not L.empty else None),
        yaxis2=dict(title='工业企业利润近12月累计增速(%)', overlaying='y', side='right', range=[R.min()-Rpad, R.max()+Rpad] if not R.empty else None),
        template='plotly_white', height=520,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # ============== WTM：紧随利润图下方 ==============
    st.markdown('---')
    st.markdown('#### 🌍 CPB 世界贸易量（WTM）')
    wtm = _load_wtm_from_db()
    c3, c4 = st.columns([2,1])
    with c4:
        if st.button('同步 CPB WTM（世界贸易量）', key='sync_wtm'):
            wtm_new = _sync_cpb_wtm()
            if not wtm_new.empty:
                wtm = wtm_new
                st.success(f'WTM 已更新：{len(wtm)} 行；最近 {wtm["date"].max().date()}')
            else:
                st.error('WTM 同步失败（可能无法解析或无下载链接）')

    # 提供“最新月报页”直达链接（自动发现）
    latest_url = _discover_wtm_xlsx_url()
    if latest_url:
        # 从下载链接回推月报页域名展示
        base = re.match(r'^(https?://[^/]+)', latest_url)
        host = base.group(1) if base else 'https://www.cpb.nl'
        # 使用用户提供的格式生成说明链接（尽量模拟最新）
        st.markdown(f'最新 WTM 下载链接候选：[{latest_url}]({latest_url})  |  月报页参考：[{host}/en/wtm/](http://cpb.nl/en/wtm/cpb-world-trade-monitor-may-2025)')
    else:
        st.info('未能自动发现下载链接，请打开参考页：<http://cpb.nl/en/wtm/cpb-world-trade-monitor-may-2025>')

    # 手动上传 WTM Excel（兜底）
    with st.expander('手动导入 WTM Excel（两列：日期、世界贸易量指数/WTM）', expanded=wtm.empty):
        up2 = st.file_uploader('选择 WTM Excel', type=['xlsx','xls','csv'], key='wtm_uploader')
        if up2 is not None:
            try:
                if up2.name.lower().endswith('.csv'):
                    raw = pd.read_csv(up2)
                else:
                    raw = pd.read_excel(up2)
                raw = _ensure_date_column(raw)
                # 自动识别指数列
                num_cols = [c for c in raw.columns if c != 'date']
                ranked = []
                for c in num_cols:
                    s=str(c).lower(); sc=sum(k in s for k in ['world','trade','volume','wtm','index'])
                    ranked.append((sc, c))
                ranked.sort(reverse=True)
                col = ranked[0][1] if ranked else (num_cols[0] if num_cols else None)
                if col is None:
                    st.error('未识别到指数列，请检查文件列名。')
                else:
                    out = raw[['date', col]].rename(columns={col:'wtv_index'})
                    out['wtv_index'] = pd.to_numeric(out['wtv_index'], errors='coerce')
                    out['date'] = pd.to_datetime(out['date'], errors='coerce').dt.to_period('M').dt.start_time
                    out = out.dropna().drop_duplicates(subset=['date']).sort_values('date')
                    if not out.empty:
                        # 合并入库
                        try:
                            prev = db_manager.load_data('cpb_wtm_world_trade')
                            if prev is not None and not prev.empty:
                                out = pd.concat([prev[['date','wtv_index']], out], ignore_index=True)
                                out = out.drop_duplicates(subset=['date'], keep='last').sort_values('date')
                        except Exception:
                            pass
                        db_manager.save_data(out, 'cpb_wtm_world_trade', if_exists='replace')
                        wtm = out
                        st.success(f'WTM 已导入：{len(wtm)} 行，最新 {wtm["date"].max().date()}')
            except Exception as e:
                st.error(f'导入失败: {e}')

    if not wtm.empty:
        wtm10 = wtm.copy()
        end_d = wtm10['date'].max(); start_d = end_d - pd.DateOffset(years=10)
        wtm10 = wtm10[(wtm10['date'] >= start_d) & (wtm10['date'] <= end_d)]
        figw = go.Figure()
        figw.add_trace(go.Scatter(x=wtm10['date'], y=wtm10['wtv_index'], name='WTM 世界贸易量指数', line=dict(color='#2a9d8f', width=3)))
        Y = wtm10['wtv_index'].dropna(); pad = (Y.max()-Y.min())*0.08 if not Y.empty else 1
        figw.update_layout(title='CPB 世界贸易量（最近10年）', xaxis=dict(title='日期'), yaxis=dict(title='指数', range=[Y.min()-pad, Y.max()+pad] if not Y.empty else None), template='plotly_white', height=420)
        st.plotly_chart(figw, use_container_width=True)

    # ============== FedEx vs WTM YoY ==============
    st.markdown('#### ✈️ FedEx 对数涨跌幅（领先3个月） vs 世界贸易量同比')

    def _load_fdx_close_db_first() -> pd.DataFrame:
        # DB 优先
        try:
            prev = db_manager.load_data('openbb_fdx_price')
            if prev is not None and not prev.empty and 'date' in prev.columns and 'close' in prev.columns:
                prev['date'] = pd.to_datetime(prev['date'], errors='coerce')
                out = prev[['date','close']].dropna().sort_values('date')
                return out
        except Exception:
            pass
        # OpenBB 兜底
        try:
            from openbb import obb
            # 拉长区间：至少覆盖10年
            import pandas as _pd
            start_date = (_pd.Timestamp.today() - _pd.DateOffset(years=15)).strftime('%Y-%m-%d')
            data = obb.equity.price.historical(symbol="FDX", provider="yfinance", start_date=start_date)
            try:
                data = data.to_df()
            except Exception:
                pass
            # 兼容不同返回结构
            if isinstance(data, dict) and 'FDX' in data:
                df = data['FDX']
            else:
                df = data
            df = df.reset_index().rename(columns={'index':'date'}) if 'date' not in df.columns else df
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            if 'close' not in df.columns:
                # 可能叫 adj_close 或 Close
                for c in ['adj_close','Adj Close','Close']:
                    if c in df.columns:
                        df = df.rename(columns={c:'close'})
                        break
            out = df[['date','close']].dropna().sort_values('date')
            if not out.empty:
                try:
                    db_manager.save_data(out, 'openbb_fdx_price', if_exists='replace')
                except Exception:
                    pass
            return out
        except Exception:
            return pd.DataFrame(columns=['date','close'])

    # 手动同步按钮（避免首次加载无表导致的困惑）
    cfx1, cfx2 = st.columns([2,1])
    with cfx2:
        if st.button('同步 FedEx 价格（OpenBB·yfinance）', key='sync_fdx'):  # 手动触发一次拉取并写库
            try:
                from openbb import obb
                import pandas as _pd
                start_date = (_pd.Timestamp.today() - _pd.DateOffset(years=15)).strftime('%Y-%m-%d')
                data = obb.equity.price.historical(symbol="FDX", provider="yfinance", start_date=start_date)
                try:
                    df = data.to_df()
                except Exception:
                    df = data
                df = df.reset_index().rename(columns={'index':'date'}) if 'date' not in df.columns else df
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                if 'close' not in df.columns:
                    for c in ['adj_close','Adj Close','Close']:
                        if c in df.columns:
                            df = df.rename(columns={c:'close'})
                            break
                out = df[['date','close']].dropna().sort_values('date')
                if not out.empty:
                    db_manager.save_data(out, 'openbb_fdx_price', if_exists='replace')
                    st.success(f'FedEx 已同步：{len(out)} 行；最近 {out["date"].max().date()}')
                else:
                    st.error('FedEx 返回为空，请稍后再试')
            except Exception as e:
                st.error(f'FedEx 同步失败: {e}')

    fdx = _load_fdx_close_db_first()
    if not fdx.empty and not wtm.empty:
        # 月度对齐
        fdx_m = fdx.copy(); fdx_m['date'] = fdx_m['date'].dt.to_period('M').dt.start_time
        fdx_m = fdx_m.groupby('date', as_index=False)['close'].last().sort_values('date')
        # 对数12个月变动：ln(C_t) - ln(C_{t-12})
        fdx_m['log_12m'] = np.log(pd.to_numeric(fdx_m['close'], errors='coerce')) - np.log(pd.to_numeric(fdx_m['close'], errors='coerce').shift(12))
        fdx_m['log_12m_pct'] = fdx_m['log_12m'] * 100.0

        # WTM 同比
        wtm_m = wtm.copy()
        wtm_m['yoy'] = wtm_m['wtv_index'].pct_change(12) * 100.0

        # 领先期调节器（默认3个月，可选0..6）
        lead_sel = st.slider('选择FedEx领先WTM的月份数', min_value=0, max_value=6, value=3, step=1, key='fdx_wtm_lead')
        # 评估0..6的相关性（最近10年）
        end_d2_all = min(fdx_m['date'].max(), wtm_m['date'].max())
        start_d2_all = end_d2_all - pd.DateOffset(years=10)
        fdx10 = fdx_m[(fdx_m['date'] >= start_d2_all) & (fdx_m['date'] <= end_d2_all)].copy()
        wtm10 = wtm_m[(wtm_m['date'] >= start_d2_all) & (wtm_m['date'] <= end_d2_all)].copy()
        corr_rows = []
        for L in range(0, 7):
            tmp = fdx10[['date','log_12m_pct']].copy(); tmp['date'] = tmp['date'] + pd.offsets.DateOffset(months=L)
            M = pd.merge(tmp, wtm10[['date','yoy']].dropna(), on='date', how='inner').dropna()
            if len(M) >= 24:
                corr_rows.append((L, len(M), float(M['log_12m_pct'].corr(M['yoy']))))
        if corr_rows:
            bestL, nL, rL = sorted(corr_rows, key=lambda x: abs(x[2]), reverse=True)[0]
            st.caption(f'最近10年最佳领先 ≈ {bestL} 个月；相关系数={rL:.3f}（样本数={nL}）')

        # FedEx 领先 lead_sel 个月
        fdx_lead = fdx_m[['date','log_12m_pct']].copy()
        fdx_lead['date'] = fdx_lead['date'] + pd.offsets.DateOffset(months=lead_sel)

        merged_fx = pd.merge(wtm_m[['date','yoy']], fdx_lead, on='date', how='outer').sort_values('date')
        # 最近10年
        end_d2 = merged_fx['date'].max(); start_d2 = end_d2 - pd.DateOffset(years=10)
        merged_fx = merged_fx[(merged_fx['date'] >= start_d2) & (merged_fx['date'] <= end_d2)]

        figfx = go.Figure()
        figfx.add_trace(go.Scatter(x=merged_fx['date'], y=merged_fx['yoy'], name='WTM 同比(%)', line=dict(color='#e76f51', width=3), connectgaps=False))
        figfx.add_trace(go.Scatter(x=merged_fx['date'], y=merged_fx['log_12m_pct'], name='FedEx 对数12月变动(领先3个月, %)', line=dict(color='#264653', width=2), yaxis='y2', connectgaps=False))

        L = merged_fx['yoy'].dropna(); R = merged_fx['log_12m_pct'].dropna()
        Lpad = (L.max()-L.min())*0.1 if not L.empty else 1
        Rpad = (R.max()-R.min())*0.1 if not R.empty else 1

        figfx.update_layout(
            title=f'FedEx 对数12月变动（领先{lead_sel}个月） vs 世界贸易量同比',
            xaxis=dict(title='日期'),
            yaxis=dict(title='WTM 同比(%)', range=[L.min()-Lpad, L.max()+Lpad] if not L.empty else None),
            yaxis2=dict(title=f'FedEx 对数12月变动(%, 领先{lead_sel}个月)', overlaying='y', side='right', range=[R.min()-Rpad, R.max()+Rpad] if not R.empty else None),
            template='plotly_white', height=480,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(figfx, use_container_width=True)
    else:
        st.info('FedEx 或 WTM 数据不足，无法绘制对比图。请先同步WTM并确保OpenBB可用。')


