# 宏观数据跟踪

宏观经济数据收集、存储与可视化系统：本地使用 Streamlit 仪表盘，线上通过
GitHub Actions 每日自动抓取数据并发布静态站点到 Cloudflare Pages。

## 架构

```
GitHub Actions（每天北京时间 09:30 自动运行）
  ├─ scripts/update_data.py   抓取最新数据（AkShare / yfinance / CPB），写入 SQLite
  ├─ scripts/build_site.py    将 15 张核心图表渲染为静态 HTML（site/index.html）
  ├─ 提交更新后的数据库回仓库
  └─ wrangler pages deploy    发布到 Cloudflare Pages
```

## 项目结构

```
宏观数据跟踪/
├── config/                  # 指标与数据源配置
├── src/
│   ├── data_fetcher/        # 数据获取（akshare / yfinance / 复合指标）
│   ├── database/            # SQLite 操作
│   └── dashboard/           # 本地 Streamlit 应用 + 图表生成器
├── scripts/
│   ├── update_data.py       # 每日数据更新（无界面）
│   └── build_site.py        # 静态站点生成
├── data/                    # SQLite 数据库（随仓库提交，作为线上数据源）
└── .github/workflows/       # 自动更新 + 部署工作流
```

## 本地使用

```bash
pip install -r requirements.txt
python scripts/update_data.py        # 更新数据
python scripts/build_site.py         # 生成静态站点（site/index.html）
python run.py                        # 或运行本地 Streamlit 仪表盘
```

## 线上部署（一次性配置）

1. 推送代码到 GitHub 仓库（main 分支）。
2. 在 Cloudflare Dashboard 创建 API Token：
   - My Profile → API Tokens → Create Token → 使用 "Edit Cloudflare Workers" 模板，
     或自定义授予 `Cloudflare Pages: Edit` 权限。
3. 在 Cloudflare Dashboard 首页右侧复制 Account ID。
4. 在 GitHub 仓库 Settings → Secrets and variables → Actions 添加两个 Secret：
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
5. 手动触发一次工作流（Actions → 更新数据并部署到 Cloudflare Pages → Run workflow），
   首次运行会自动创建名为 `macro-dashboard` 的 Pages 项目。
6. 访问 `https://macro-dashboard.pages.dev`（也可在 Pages 项目中绑定自定义域名）。

## 数据来源说明

| 类别 | 来源 | 更新方式 |
|---|---|---|
| 中国宏观（M2、PPI、社融、国债收益率等） | AkShare | 每日自动 |
| 行情（BTC、美元指数、纳指、FedEx） | Yahoo Finance（yfinance） | 每日自动 |
| CPB 世界贸易量 | cpb.nl | 每日自动（月度数据） |

线上站点仅包含可自动更新的图表；依赖 Wind 终端或手动导入的图表
（产能利用率、库存周期、朱格拉周期、工业企业利润）仅保留在本地 Streamlit 仪表盘中。
