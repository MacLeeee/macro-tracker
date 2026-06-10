#!/usr/bin/env python3
"""
每日数据更新脚本（无界面，供 GitHub Actions / 本地命令行调用）

更新所有可自动抓取的数据表；Wind 终端类数据（美国产能利用率、中国库存、
朱格拉指数等）与手动导入数据（工业企业利润）保留数据库中的既有值。
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from loguru import logger

from src.database.db_manager import db_manager
from src.data_fetcher.data_manager import data_manager

RESULTS = {}


def step(name):
    """装饰器：每个更新步骤独立容错，单步失败不影响整体"""
    def wrapper(func):
        def inner():
            try:
                func()
                RESULTS[name] = True
                logger.info(f"[OK] {name}")
            except Exception as e:
                RESULTS[name] = False
                logger.error(f"[FAIL] {name}: {e}")
        return inner
    return wrapper


@step("配置指标（M2/工业增加值/沪深300/中证2000/BTC/DXY/纳指）")
def update_config_indicators():
    results = data_manager.update_all_indicators(force_update=True)
    failed = [k for k, ok in results.items() if not ok]
    if failed:
        logger.warning(f"以下指标更新失败: {failed}")


@step("全球流动性指标（BTC/DXY）")
def update_global_liquidity():
    from src.data_fetcher.composite_indicator import liquidity_indicator
    liquidity_indicator.update_and_calculate(force_update=True)


@step("中国超额流动性（M2-工业增加值）")
def update_china_liquidity():
    from src.data_fetcher.china_liquidity_indicator import china_liquidity_indicator
    china_liquidity_indicator.update_and_calculate(force_update=True)


@step("社融同比指标")
def update_social_financing():
    from src.data_fetcher.social_financing_indicator import init_social_financing_indicator
    sf = init_social_financing_indicator(db_manager)
    sf.update_and_calculate(force_update=True)


@step("M1/M2剪刀差源数据（M1M2/中证500）")
def update_m1m2():
    from src.data_fetcher.m1m2_scissors_indicator import M1M2ScissorsIndicator
    M1M2ScissorsIndicator(db_manager).ensure_source_data()


@step("中国PPI")
def update_china_ppi():
    import akshare as ak
    from src.data_fetcher.akshare_fetcher import AkShareFetcher
    fetcher = AkShareFetcher()
    data = fetcher.fetch_data_by_key("macro_china_ppi")
    if data is None or data.empty:
        raise RuntimeError("PPI 返回空数据")
    db_manager.save_data(data, "macro_china_ppi", if_exists="replace")


@step("美国PMI")
def update_us_pmi():
    import akshare as ak
    raw = None
    try:
        raw = ak.macro_usa_pmi()
    except Exception:
        pass
    if raw is None or raw.empty:
        raw = ak.macro_usa_ism_pmi()
    if raw is None or raw.empty:
        raise RuntimeError("PMI 返回空数据")

    # 标准化为 date + pmi 两列，按月对齐（每月取最后一次公布值）
    date_col = next((c for c in ['日期', '月份', 'date'] if c in raw.columns), None)
    value_col = next((c for c in ['今值', 'value'] if c in raw.columns), None)
    if not date_col or not value_col:
        raise RuntimeError(f"PMI 列名无法识别: {list(raw.columns)}")
    out = raw[[date_col, value_col]].rename(columns={date_col: 'date', value_col: 'pmi'})
    out['date'] = pd.to_datetime(out['date'], errors='coerce')
    out['pmi'] = pd.to_numeric(out['pmi'], errors='coerce')
    out = out.dropna().sort_values('date')
    out['date'] = out['date'].dt.to_period('M').dt.start_time
    out = out.groupby('date', as_index=False)['pmi'].last()
    db_manager.save_data(out, "macro_usa_pmi", if_exists="replace")


@step("中美国债收益率（10Y/2Y）")
def update_bond_rates():
    import akshare as ak
    bond = ak.bond_zh_us_rate(start_date="19900101")
    if bond is None or bond.empty:
        raise RuntimeError("国债收益率返回空数据")
    if '日期' in bond.columns:
        bond['date'] = pd.to_datetime(bond['日期'], errors='coerce')
    db_manager.save_data(bond, "bond_zh_us_rate", if_exists="replace")

    cols = list(bond.columns)

    def find_col(tokens):
        for c in cols:
            if all(t in str(c) for t in tokens):
                return c
        return None

    col10 = find_col(['美国', '10'])
    col2 = find_col(['美国', '2'])
    if col10:
        t = bond[['date', col10]].rename(columns={col10: 'value'})
        t['value'] = pd.to_numeric(t['value'], errors='coerce')
        db_manager.save_data(t.dropna(), 'us_yield_10y', if_exists='replace')
    if col2:
        t = bond[['date', col2]].rename(columns={col2: 'value'})
        t['value'] = pd.to_numeric(t['value'], errors='coerce')
        db_manager.save_data(t.dropna(), 'us_yield_2y', if_exists='replace')


@step("COMEX铜价")
def update_comex_copper():
    import akshare as ak
    copper = ak.futures_global_hist_em(symbol="HG00Y")
    if copper is None or copper.empty:
        raise RuntimeError("COMEX铜返回空数据")
    copper['date'] = pd.to_datetime(copper['日期'], errors='coerce')
    copper = copper[['date', '最新价']].rename(columns={'最新价': 'close'})
    copper['close'] = pd.to_numeric(copper['close'], errors='coerce')
    copper = copper.dropna().sort_values('date')
    db_manager.save_data(copper, 'comex_copper', if_exists='replace')


@step("中国出口近12月累计增速")
def update_china_export():
    import akshare as ak
    from src.dashboard.trade_export_page import _ensure_date_column, _rolling12_yoy
    exp = ak.macro_china_hgjck()
    exp = _ensure_date_column(exp)
    candidates = [c for c in exp.columns
                  if ('出口' in str(c) and ('当月' in str(c) or '金额' in str(c)))]
    if not candidates:
        candidates = [c for c in exp.columns if '出口' in str(c)]
    if not candidates:
        raise RuntimeError("未找到出口金额列")
    out = _rolling12_yoy(exp, 'date', candidates[0]).rename(columns={'roll12_yoy': 'export_12m_yoy'})
    out = out.dropna().sort_values('date')
    if out.empty:
        raise RuntimeError("出口增速计算结果为空")
    db_manager.save_data(out, 'china_export_12m_yoy', if_exists='replace')


@step("CPB世界贸易量（WTM）")
def update_wtm():
    from src.dashboard.trade_export_page import _sync_cpb_wtm
    wtm = _sync_cpb_wtm()
    if wtm is None or wtm.empty:
        raise RuntimeError("WTM 同步失败（保留数据库既有数据）")


@step("FedEx股价（yfinance）")
def update_fedex():
    import yfinance as yf
    start_date = (pd.Timestamp.today() - pd.DateOffset(years=15)).strftime('%Y-%m-%d')
    df = yf.Ticker("FDX").history(start=start_date, interval='1d', auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError("FDX 返回空数据")
    df = df.reset_index()
    df = df.rename(columns={'Date': 'date', 'Close': 'close'})
    df['date'] = pd.to_datetime(df['date'])
    if getattr(df['date'].dt, 'tz', None) is not None:
        df['date'] = df['date'].dt.tz_localize(None)
    out = df[['date', 'close']].dropna().sort_values('date')
    db_manager.save_data(out, 'openbb_fdx_price', if_exists='replace')


def main():
    logger.info("=" * 50)
    logger.info("开始每日数据更新")
    logger.info("=" * 50)

    steps = [
        update_config_indicators,
        update_global_liquidity,
        update_china_liquidity,
        update_social_financing,
        update_m1m2,
        update_china_ppi,
        update_us_pmi,
        update_bond_rates,
        update_comex_copper,
        update_china_export,
        update_wtm,
        update_fedex,
    ]
    for s in steps:
        s()

    ok = sum(1 for v in RESULTS.values() if v)
    logger.info("=" * 50)
    logger.info(f"数据更新完成: {ok}/{len(RESULTS)} 成功")
    for name, success in RESULTS.items():
        logger.info(f"  {'✓' if success else '✗'} {name}")
    logger.info("=" * 50)

    # 部分失败不阻断建站：图表会回退到数据库中的既有数据
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
