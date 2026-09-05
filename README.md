# 公众号创作工作台 - 云端信源自动采集

## 这是什么？

配合「公众号创作工作台.html」使用的云端自动采集方案。通过 GitHub Actions 定时抓取官方公开列表页，输出 `data/sources.json`，工作台通过 jsDelivr CDN 自动拉取，实现信源准实时更新。

## 快速开始（5分钟）

### 1. 创建 GitHub 仓库

1. 登录 [GitHub](https://github.com)，点击右上角 `+` → `New repository`
2. 仓库名建议：`wechat-workbench-sources`（可自定义）
3. 选择 `Public`（公开仓库才能用 jsDelivr 免费 CDN）
4. 勾选 `Add a README file`
5. 点击 `Create repository`

### 2. 上传模板文件

将本目录下的所有文件上传到你的 GitHub 仓库：

```
你的仓库/
├── .github/
│   └── workflows/
│       └── fetch_sources.yml    # Actions 定时任务配置
├── scripts/
│   └── fetch_sources.py          # 采集脚本
├── data/
│   └── sources.json              # 输出数据（Actions自动生成）
└── README.md                      # 本文件
```

**上传方式**：在仓库页面点击 `Add file` → `Upload files`，拖拽文件上传。

### 3. 配置采集源

编辑 `scripts/fetch_sources.py` 中的 `SOURCES` 列表，添加你需要监控的官方网站：

```python
SOURCES = [
    {
        "name": "国资委",           # 显示名称
        "url": "http://...",        # 列表页URL
        "type": "list",             # 解析类型
        "item_selector": "ul li",   # 列表项选择器
        "title_selector": "a",      # 标题选择器
        "date_selector": "span",    # 日期选择器
    },
    # 继续添加...
]
```

> **注意**：不同网站的 HTML 结构不同，可能需要调整选择器。建议先在本地运行脚本测试。

### 4. 启用 Actions

1. 在仓库页面点击顶部 `Actions` 标签
2. 如果看到提示，点击 `I understand my workflows, go ahead and enable them`
3. 点击左侧 `信源自动采集`
4. 点击 `Run workflow` → `Run workflow` 手动触发一次测试

### 5. 获取 CDN 地址

数据提交后，通过 jsDelivr CDN 访问：

```
https://cdn.jsdelivr.net/gh/你的用户名/你的仓库名@main/data/sources.json
```

例如：
```
https://cdn.jsdelivr.net/gh/yanglaoshi/wechat-workbench-sources@main/data/sources.json
```

### 6. 配置工作台

1. 打开「公众号创作工作台.html」
2. 点击侧边栏底部的 `☁ 云端` 按钮
3. 粘贴上面的 CDN 地址
4. 点击 `✓ 保存并立即拉取`

完成！工作台会在每次打开时及每小时自动拉取最新信源数据。

## 工作原理

```
GitHub Actions（每6小时）
    ↓
运行 fetch_sources.py
    ↓
抓取官方公开列表页 → 解析标题/日期/链接
    ↓
输出 data/sources.json → 提交到仓库
    ↓
jsDelivr CDN（免费，带CORS）
    ↓
工作台 fetch 拉取 → 增量合并（按标题去重）
    ↓
展示最新信源动态 + 潜力评分
```

## 成本说明

| 项目 | 费用 | 说明 |
|---|---|---|
| GitHub 仓库 | 免费 | 公开仓库无限存储 |
| GitHub Actions | 免费 | 公开仓库每月无限分钟数；本任务约240分钟/月 |
| jsDelivr CDN | 免费 | 全球加速，带 CORS 头 |
| 总计 | **0元** | 永久免费使用 |

## 常见问题

### Q: 数据更新延迟多久？
A: GitHub Actions 每6小时运行一次，jsDelivr CDN 缓存约12小时。因此数据最迟18小时内更新。如需更即时，可配置 `JSDELIVR_API_TOKEN` 强制刷新 CDN。

### Q: 如何配置 JSDELIVR_API_TOKEN？
A:
1. 访问 [jsDelivr 官网](https://www.jsdelivr.com/) 注册账号
2. 在个人设置中生成 API Token
3. 在 GitHub 仓库 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`
4. Name 填 `JSDELIVR_API_TOKEN`，Value 填你的 Token
5. 下次运行 Actions 时会自动刷新 CDN

### Q: 抓取失败怎么办？
A:
1. 在 Actions 运行日志中查看具体错误
2. 检查目标网站是否能正常访问、是否有反爬
3. 调整 `scripts/fetch_sources.py` 中的选择器
4. 对于反爬严格的网站，建议改用 RSSHub 或手动导入

### Q: 可以添加多少个信源？
A: 理论上无限制，但建议不超过20个，避免单次运行超时。每个信源最多取10条最新动态。

### Q: 工作台断网了还能用吗？
A: 可以。云端拉取失败时，工作台自动降级为本地快照，并显示"本地快照"状态。之前拉取的数据不会丢失。

### Q: 如何手动更新数据？
A: 两种方式：
1. 在工作台点击信源区的 `⟳ 立即拉取` 按钮
2. 在 GitHub Actions 页面手动触发运行

## 合规说明

- 本脚本只采集**公开网页的标题/摘要/链接/发布时间**
- 不搬运正文、不商用转售数据
- 合理 UA、间隔与重试，失败自动降级
- 工作台渲染时展示原文链接并标注"以官方发布为准"
- 对反爬站点不做绕过验证码等破解动作

## 文件说明

| 文件 | 说明 |
|---|---|
| `.github/workflows/fetch_sources.yml` | Actions 定时任务配置 |
| `scripts/fetch_sources.py` | 采集脚本（Python，仅用标准库） |
| `data/sources.json` | 输出数据（Actions 自动生成） |
| `README.md` | 本说明文件 |

## 技术支持

如遇到问题，请检查：
1. Actions 运行日志是否有报错
2. `data/sources.json` 是否正常生成
3. CDN 地址是否能在浏览器中直接打开
4. 工作台「☁ 云端」配置中的地址是否正确
