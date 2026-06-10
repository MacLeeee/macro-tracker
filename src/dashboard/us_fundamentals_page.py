import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os, ssl, urllib.request
import time

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.database.db_manager import db_manager


def _ensure_month_start(s: pd.Series) -> pd.Series:
    s = pd.to_datetime(s, errors='coerce')
    return s.dt.to_period('M').dt.start_time


def _fetch_fred_csv(series_id: str, date_col: str = 'DATE') -> pd.DataFrame:
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        with urllib.request.urlopen(url, timeout=15, context=ctx) as resp:
            df = pd.read_csv(resp)
        df = df.rename(columns={date_col: 'date', series_id: 'value'})
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna().sort_values('date')
        return df[['date', 'value']]
    except Exception:
        return pd.DataFrame(columns=['date','value'])


def _load_us_yields() -> pd.DataFrame:
    # 尝试读取DB缓存
    ten, two = None, None
    try:
        t = db_manager.load_data('us_yield_10y')
        if t is not None and not t.empty:
            ten = t[['date','value']].rename(columns={'value':'y10'})
    except Exception:
        pass
    try:
        t = db_manager.load_data('us_yield_2y')
        if t is not None and not t.empty:
            two = t[['date','value']].rename(columns={'value':'y2'})
    except Exception:
        pass

    # 兜底：AkShare 美国国债收益率
    if (ten is None or ten.empty) or (two is None or two.empty):
        try:
            import akshare as ak
            raw = ak.bond_zh_us_rate(start_date="19900101")
            # 日期
            if '日期' in raw.columns:
                raw['date'] = pd.to_datetime(raw['日期'], errors='coerce')
            elif 'date' in raw.columns:
                raw['date'] = pd.to_datetime(raw['date'], errors='coerce')
            # 寻找美国10Y/2Y列
            cols = list(raw.columns)
            def find_col(tokens):
                for c in cols:
                    s = str(c)
                    if all(t in s for t in tokens):
                        return c
                return None
            col10 = find_col(['美国', '10']) or find_col(['美国国债收益率', '10'])
            col2 = find_col(['美国', '2']) or find_col(['美国国债收益率', '2'])
            if col10 and (ten is None or ten.empty):
                t10 = raw[['date', col10]].rename(columns={col10:'y10'})
                t10['y10'] = pd.to_numeric(t10['y10'], errors='coerce')
                ten = t10.dropna()
                try:
                    db_manager.save_data(ten.rename(columns={'y10':'value'}), 'us_yield_10y', if_exists='replace')
                except Exception:
                    pass
            if col2 and (two is None or two.empty):
                t2 = raw[['date', col2]].rename(columns={col2:'y2'})
                t2['y2'] = pd.to_numeric(t2['y2'], errors='coerce')
                two = t2.dropna()
                try:
                    db_manager.save_data(two.rename(columns={'y2':'value'}), 'us_yield_2y', if_exists='replace')
                except Exception:
                    pass
        except Exception:
            pass

    if ten is None or two is None or ten.empty or two.empty:
        return pd.DataFrame(columns=['date','spread'])

    # 月频末值并对齐月初
    ten_m = ten.copy(); ten_m['date'] = _ensure_month_start(ten_m['date'])
    ten_m = ten_m.groupby('date', as_index=False)['y10'].last()
    two_m = two.copy(); two_m['date'] = _ensure_month_start(two_m['date'])
    two_m = two_m.groupby('date', as_index=False)['y2'].last()
    merged = pd.merge(ten_m, two_m, on='date', how='inner').dropna().sort_values('date')
    merged['spread'] = merged['y10'] - merged['y2']
    # 12期滚动Z分数
    merged['spread_z'] = (merged['spread'] - merged['spread'].rolling(12, min_periods=6).mean()) / merged['spread'].rolling(12, min_periods=6).std()
    return merged[['date','spread','spread_z']].dropna()


def _load_us_pmi() -> pd.DataFrame:
    # DB优先（若你已缓存）
    try:
        df = db_manager.load_data('macro_usa_pmi')
        if df is not None and not df.empty:
            # 常见列处理
            if 'date' not in df.columns:
                for c in ['日期','时间','月份']:
                    if c in df.columns:
                        df['date'] = pd.to_datetime(df[c], errors='coerce')
                        break
            pmi_col = None
            for c in df.columns:
                if 'PMI' in str(c).upper() or '制造' in str(c):
                    pmi_col = c; break
            if pmi_col is None and 'pmi' in df.columns:
                pmi_col = 'pmi'
            if 'date' in df.columns and pmi_col is not None:
                out = df[['date', pmi_col]].rename(columns={pmi_col:'pmi'})
                out['date'] = _ensure_month_start(out['date'])
                out['pmi'] = pd.to_numeric(out['pmi'], errors='coerce')
                return out.dropna().sort_values('date')
    except Exception:
        pass

    # AkShare 兜底：优先 macro_usa_pmi，其次 macro_usa_ism_pmi
    try:
        import akshare as ak
        raw = None
        try:
            raw = ak.macro_usa_pmi()
        except Exception:
            raw = None
        if raw is None or raw.empty:
            raw = ak.macro_usa_ism_pmi()
        # 解析列
        if '月份' in raw.columns:
            raw['date'] = pd.to_datetime(raw['月份'], errors='coerce')
        elif '日期' in raw.columns:
            raw['date'] = pd.to_datetime(raw['日期'], errors='coerce')
        pmi_col = None
        # 常见列：'PMI', '今值' 等
        for c in raw.columns:
            if 'PMI' in str(c).upper() or '今值' in str(c) or '制造' in str(c):
                pmi_col = c; break
        if pmi_col is not None:
            out = raw[['date', pmi_col]].rename(columns={pmi_col:'pmi'})
            out['date'] = _ensure_month_start(out['date'])
            out['pmi'] = pd.to_numeric(out['pmi'], errors='coerce')
            out = out.dropna().sort_values('date')
            try:
                db_manager.save_data(out.rename(columns={'pmi':'value'}), 'macro_usa_pmi', if_exists='replace')
            except Exception:
                pass
            return out
    except Exception:
        pass
    return pd.DataFrame(columns=['date','pmi'])


def get_us_spread_pmi_chart(lead_months: int = 12) -> go.Figure:
    """获取美国10Y-2Y vs PMI图表（供首页调用）"""
    ydf = _load_us_yields()
    pmi = _load_us_pmi()

    if ydf.empty or pmi.empty:
        return None

    # 10Y-2Y 为领先项：将10Y-2Y向前平移
    spread_plot = ydf[['date','spread_z']].copy()
    spread_plot['date'] = spread_plot['date'] + pd.offsets.DateOffset(months=lead_months)

    merged = pd.merge(spread_plot, pmi[['date','pmi']], on='date', how='outer').sort_values('date')
    # 最近15年窗口
    end_d = merged['date'].max()
    start_d = end_d - pd.DateOffset(years=15)
    merged = merged[(merged['date'] >= start_d) & (merged['date'] <= end_d)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged['date'], y=merged['spread_z'], 
        name=f'10Y-2Y(领先{lead_months}月, Z分数)', 
        line=dict(color='#1f77b4', width=2), 
        connectgaps=False
    ))
    fig.add_trace(go.Scatter(
        x=merged['date'], y=merged['pmi'], 
        name='ISM PMI', 
        line=dict(color='#d62728', width=2), 
        yaxis='y2', 
        connectgaps=False
    ))

    R = merged['pmi'].dropna()
    Rpad = (R.max()-R.min())*0.05 if not R.empty else 1

    fig.update_layout(
        title='美国10Y-2Y vs PMI',
        xaxis=dict(title='日期'),
        yaxis=dict(title='Z分数', range=[-5, 5], zeroline=True),
        yaxis2=dict(title='PMI', overlaying='y', side='right', range=[R.min()-Rpad, R.max()+Rpad] if not R.empty else None),
        template='plotly_white', 
        height=400,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    return fig


def _load_us_capacity_utilization() -> pd.DataFrame:
    """加载美国工业产能利用率 - 数据库优先，Wind API兜底"""
    # DB优先
    try:
        df = db_manager.load_data('us_capacity_utilization')
        if df is not None and not df.empty:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df[['date', 'value']].rename(columns={'value': 'capacity_util'})
                df['capacity_util'] = pd.to_numeric(df['capacity_util'], errors='coerce')
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
            return pd.DataFrame(columns=['date', 'capacity_util'])
        
        # 启动Wind API（如果未连接）
        try:
            if not w.isconnected():
                w.start()
            # 再次检查连接状态
            if not w.isconnected():
                return pd.DataFrame(columns=['date', 'capacity_util'])
        except Exception as e:
            # Wind终端可能未运行或未登录
            return pd.DataFrame(columns=['date', 'capacity_util'])
        
        # 获取10年历史数据
        end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
        start_date = (pd.Timestamp.now() - pd.DateOffset(years=10)).strftime('%Y-%m-%d')
        
        # 产能利用率: G1110630
        data = w.edb("G1110630", start_date, end_date, "Fill=Previous")
        
        # 检查返回结果
        if not hasattr(data, 'ErrorCode'):
            return pd.DataFrame(columns=['date', 'capacity_util'])
        
        if data.ErrorCode != 0:
            # 错误代码不为0表示获取失败
            return pd.DataFrame(columns=['date', 'capacity_util'])
        
        if not data.Data or len(data.Data) == 0 or not data.Times:
            return pd.DataFrame(columns=['date', 'capacity_util'])
        
        dates = pd.to_datetime(data.Times)
        values = pd.Series(data.Data[0])
        df = pd.DataFrame({'date': dates, 'capacity_util': values})
        df['capacity_util'] = pd.to_numeric(df['capacity_util'], errors='coerce')
        df = df.dropna().sort_values('date')
        df['date'] = _ensure_month_start(df['date'])
        
        # 保存到数据库
        try:
            db_manager.save_data(df.rename(columns={'capacity_util': 'value'}), 
                                'us_capacity_utilization', if_exists='replace')
        except Exception:
            pass
        
        return df
    except Exception as e:
        # 返回空DataFrame，错误信息会在按钮点击时显示
        return pd.DataFrame(columns=['date', 'capacity_util'])


def _load_us_ppi() -> pd.DataFrame:
    """加载美国PPI - 数据库优先，Wind API兜底"""
    # DB优先
    try:
        df = db_manager.load_data('us_ppi')
        if df is not None and not df.empty:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df[['date', 'value']].rename(columns={'value': 'ppi'})
                df['ppi'] = pd.to_numeric(df['ppi'], errors='coerce')
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
            return pd.DataFrame(columns=['date', 'ppi'])
        
        # 启动Wind API（如果未连接）
        try:
            if not w.isconnected():
                w.start()
            # 再次检查连接状态
            if not w.isconnected():
                return pd.DataFrame(columns=['date', 'ppi'])
        except Exception as e:
            # Wind终端可能未运行或未登录
            return pd.DataFrame(columns=['date', 'ppi'])
        
        # 获取10年历史数据
        end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
        start_date = (pd.Timestamp.now() - pd.DateOffset(years=10)).strftime('%Y-%m-%d')
        
        # 美国PPI: G1131825
        data = w.edb("G1131825", start_date, end_date, "Fill=Previous")
        
        # 检查返回结果
        if not hasattr(data, 'ErrorCode'):
            return pd.DataFrame(columns=['date', 'ppi'])
        
        if data.ErrorCode != 0:
            # 错误代码不为0表示获取失败
            return pd.DataFrame(columns=['date', 'ppi'])
        
        if not data.Data or len(data.Data) == 0 or not data.Times:
            return pd.DataFrame(columns=['date', 'ppi'])
        
        dates = pd.to_datetime(data.Times)
        values = pd.Series(data.Data[0])
        df = pd.DataFrame({'date': dates, 'ppi': values})
        df['ppi'] = pd.to_numeric(df['ppi'], errors='coerce')
        df = df.dropna().sort_values('date')
        df['date'] = _ensure_month_start(df['date'])
        
        # 保存到数据库
        try:
            db_manager.save_data(df.rename(columns={'ppi': 'value'}), 
                                'us_ppi', if_exists='replace')
        except Exception:
            pass
        
        return df
    except Exception as e:
        # 返回空DataFrame，错误信息会在按钮点击时显示
        return pd.DataFrame(columns=['date', 'ppi'])


def get_us_capacity_ppi_ratio_chart() -> go.Figure:
    """获取美国产能利用率 vs PPI对比图表（双折线图）"""
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
        title='美国工业产能利用率 vs PPI',
        xaxis=dict(title='日期'),
        yaxis=dict(title='产能利用率(%)', range=[cap_range.min()-cap_pad, cap_range.max()+cap_pad] if not cap_range.empty else None),
        yaxis2=dict(title='PPI(%)', side='right', overlaying='y', range=[ppi_range.min()-ppi_pad, ppi_range.max()+ppi_pad] if not ppi_range.empty else None),
        template='plotly_white',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(x=0.02, y=0.98)
    )
    return fig


def show_us_fundamentals():
    st.markdown('### 🇺🇸 美国基本面数据')
    st.markdown('#### 国债收益率曲线（10Y-2Y）Z分数（领先） vs ISM制造业PMI')

    ydf = _load_us_yields()
    pmi = _load_us_pmi()

    if ydf.empty or pmi.empty:
        st.warning('美国收益率或PMI数据不足，无法绘图。')
        return

    # 10Y-2Y 为领先项：将10Y-2Y向前平移（正值表示领先X个月）
    lead = st.slider('10Y-2Y 领先（月）', min_value=0, max_value=18, value=12, step=1)
    
    fig = get_us_spread_pmi_chart(lead_months=lead)
    if fig:
        # 更新标题以显示当前滑块值
        fig.update_layout(
            title=f'10Y-2Y(领先{lead}个月, 滚动Z分数) vs ISM制造业PMI',
            height=520
        )
        # 更新trace名称
        fig.data[0].name = f'10Y-2Y(领先{lead}个月, 滚动Z分数)'
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning('数据不足')
    
    st.markdown('---')
    st.markdown('#### 美国工业产能利用率 vs PPI')
    
    # 添加同步按钮
    if st.button('🔄 同步Wind数据（产能利用率 & PPI）'):
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
            
            # 获取产能利用率数据
            status_text.text('正在获取产能利用率数据 (G1110630)...')
            progress_bar.progress(40)
            capacity = _load_us_capacity_utilization()
            
            # 获取PPI数据
            status_text.text('正在获取PPI数据 (G1131825)...')
            progress_bar.progress(70)
            ppi = _load_us_ppi()
            
            progress_bar.progress(100)
            status_text.text('数据处理完成')
            time.sleep(0.5)  # 短暂延迟让用户看到完成状态
            
            progress_bar.empty()
            status_text.empty()
            
            if not capacity.empty and not ppi.empty:
                st.success(f'✅ 产能利用率数据: {len(capacity)}条记录，日期范围: {capacity["date"].min().strftime("%Y-%m")} 至 {capacity["date"].max().strftime("%Y-%m")}')
                st.success(f'✅ PPI数据: {len(ppi)}条记录，日期范围: {ppi["date"].min().strftime("%Y-%m")} 至 {ppi["date"].max().strftime("%Y-%m")}')
                st.balloons()  # 成功时显示庆祝动画
            elif capacity.empty and ppi.empty:
                st.error('❌ 数据获取失败：请检查Wind API连接和Wind终端状态')
                st.info('💡 可能的原因：\n1. Wind终端未启动或未登录\n2. Wind API连接失败\n3. 数据代码错误或权限不足')
            elif capacity.empty:
                st.warning(f'⚠️ 产能利用率数据获取失败，但PPI数据成功: {len(ppi)}条记录')
            else:
                st.warning(f'⚠️ PPI数据获取失败，但产能利用率数据成功: {len(capacity)}条记录')
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
            st.info('💡 请检查：\n1. Wind终端是否已启动并登录\n2. 网络连接是否正常\n3. Wind API权限是否充足')
    
    fig2 = get_us_capacity_ppi_ratio_chart()
    if fig2:
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning('产能利用率或PPI数据不足，无法绘图。请先点击"同步Wind数据"按钮获取数据。')


