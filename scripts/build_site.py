#!/usr/bin/env python3
"""
静态站点生成器 - 将核心宏观图表渲染为单页静态 HTML（输出至 site/）

图表数据全部读取本地 SQLite 数据库，运行前请先执行 scripts/update_data.py
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import plotly.io as pio

from src.dashboard.chart_generators import (
    get_global_liquidity_chart,
    get_china_excess_liquidity_chart,
    get_m1m2_scissors_chart,
    get_social_financing_chart,
    get_dxy_ppi_chart,
    get_m1_ppi_chart,
    get_cn_spread_m1_chart,
    get_wtm_chart,
    get_fedex_wtm_chart,
    get_us_spread_pmi_chart,
    get_lme_copper_pmi_chart,
)

# 防中文乱码：统一指定中文字体族（浏览器端渲染）
FONT_FAMILY = '-apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'

SECTIONS = [
    {
        "id": "liquidity",
        "title": "流动性",
        "charts": [
            ("全球流动性（BTC/DXY） vs 纳斯达克", get_global_liquidity_chart),
            ("中国超额流动性（M2 - 工业增加值）", get_china_excess_liquidity_chart),
        ],
    },
    {
        "id": "money",
        "title": "货币与信贷",
        "charts": [
            ("M1/M2 剪刀差 vs 中证500", get_m1m2_scissors_chart),
            ("社融同比增长 vs 沪深300", get_social_financing_chart),
        ],
    },
    {
        "id": "china",
        "title": "中国基本面",
        "charts": [
            ("美元指数同比（逆序，领先6月） vs 中国PPI", get_dxy_ppi_chart),
            ("M1同比（领先6月） vs PPI", get_m1_ppi_chart),
            ("中国10Y-2Y利差（领先11月） vs M1同比", get_cn_spread_m1_chart),
        ],
    },
    {
        "id": "trade",
        "title": "贸易与出口",
        "charts": [
            ("CPB 世界贸易量", get_wtm_chart),
            ("FedEx 对数12月变动（领先3月） vs 世界贸易量同比", get_fedex_wtm_chart),
        ],
    },
    {
        "id": "us",
        "title": "美国基本面",
        "charts": [
            ("美国10Y-2Y利差（领先12月，Z分数） vs ISM PMI", get_us_spread_pmi_chart),
            ("COMEX铜价 vs 美国PMI", get_lme_copper_pmi_chart),
        ],
    },
]

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>宏观数据跟踪</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  :root {{
    --bg: #f5f6f8;
    --card-bg: #ffffff;
    --text: #1a1d24;
    --muted: #6b7280;
    --accent: #1f5fbf;
    --border: #e5e7eb;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: {font_family};
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }}
  header {{
    background: var(--card-bg);
    border-bottom: 1px solid var(--border);
    padding: 18px 28px;
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }}
  header h1 {{ font-size: 20px; font-weight: 700; }}
  header .updated {{ font-size: 13px; color: var(--muted); }}
  nav {{
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--card-bg);
    border-bottom: 1px solid var(--border);
    padding: 0 28px;
    display: flex;
    gap: 4px;
    overflow-x: auto;
  }}
  nav a {{
    padding: 11px 14px;
    font-size: 14px;
    color: var(--muted);
    text-decoration: none;
    white-space: nowrap;
    border-bottom: 2px solid transparent;
  }}
  nav a:hover {{ color: var(--accent); border-bottom-color: var(--accent); }}
  main {{ max-width: 1480px; margin: 0 auto; padding: 24px 24px 48px; }}
  section {{ margin-bottom: 8px; }}
  section h2 {{
    font-size: 16px;
    font-weight: 700;
    margin: 22px 4px 14px;
    padding-left: 10px;
    border-left: 4px solid var(--accent);
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(560px, 1fr));
    gap: 18px;
  }}
  @media (max-width: 640px) {{
    .grid {{ grid-template-columns: 1fr; }}
    main {{ padding: 16px 10px 40px; }}
  }}
  .card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px 6px;
    overflow: hidden;
  }}
  .card h3 {{ font-size: 14.5px; font-weight: 600; margin-bottom: 4px; }}
  .card .empty {{
    color: var(--muted);
    font-size: 13px;
    padding: 60px 0 70px;
    text-align: center;
  }}
  footer {{
    text-align: center;
    color: var(--muted);
    font-size: 12.5px;
    padding: 18px;
    border-top: 1px solid var(--border);
  }}
</style>
</head>
<body>
<header>
  <h1>宏观数据跟踪</h1>
  <span class="updated">数据更新：{updated} （北京时间，每日自动更新）</span>
</header>
<nav>
{nav}
</nav>
<main>
{sections}
</main>
<footer>
  数据来源：AkShare / Yahoo Finance / CPB，每日自动更新。
</footer>
</body>
</html>
"""


def render_chart(title: str, fig) -> str:
    if fig is None:
        return f'<div class="card"><h3>{title}</h3><div class="empty">数据暂缺</div></div>'
    fig.update_layout(
        title=None,
        font=dict(family=FONT_FAMILY, size=12),
        margin=dict(l=40, r=40, t=20, b=40),
        height=400,
        legend=dict(orientation='h', yanchor='bottom', y=1.0, xanchor='left', x=0),
    )
    html = pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs=False,
        config={"responsive": True, "displaylogo": False,
                "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
    )
    return f'<div class="card"><h3>{title}</h3>{html}</div>'


def main():
    nav_html = "\n".join(
        f'  <a href="#{s["id"]}">{s["title"]}</a>' for s in SECTIONS
    )

    sections_html = []
    total, ok = 0, 0
    for sec in SECTIONS:
        cards = []
        for title, func in sec["charts"]:
            total += 1
            try:
                fig = func()
            except Exception as e:
                print(f"  [WARN] {title} 生成失败: {e}")
                fig = None
            if fig is not None:
                ok += 1
            cards.append(render_chart(title, fig))
            print(f"  {'✓' if fig is not None else '✗'} {title}")
        sections_html.append(
            f'<section id="{sec["id"]}">\n<h2>{sec["title"]}</h2>\n'
            f'<div class="grid">\n' + "\n".join(cards) + "\n</div>\n</section>"
        )

    beijing_now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    page = PAGE_TEMPLATE.format(
        font_family=FONT_FAMILY,
        updated=beijing_now,
        nav=nav_html,
        sections="\n".join(sections_html),
    )

    out_dir = PROJECT_ROOT / "site"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "index.html"
    out_file.write_text(page, encoding="utf-8")
    print(f"\n站点已生成: {out_file} （{ok}/{total} 张图表成功）")

    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
