# WorkBuddy 开发记录 · workbuddy.md

> 本项目全程使用 WorkBuddy AI 辅助开发。本文件按时间线记录关键开发会话，用于 WorkBuddy 联动活动奖励核验。

## 项目：麦门人生回忆录（mcd-memoir）

### 阶段一 · 选题分析（WorkBuddy 会话）

- 拉取麦当劳 MCP 挑战赛官方仓库全部 200 个报名 Issue 并聚类分析：识别出省钱/营养/点餐/报表等 8 大红海与无障碍、履约链路、AIGC 等蓝海方向
- 对比「语音车载点单」vs「晒单 AIGC 生成器」：提炼三条胜负手（输出物即演示 / 参与式传播飞轮 / 真数据窄切口），收敛出「麦门人生回忆录」方向

### 阶段二 · MCP 数据可行性验证（WorkBuddy 会话）

- 使用用户 Token 实测 `mcp.mcd.cn`：发现 35 个工具，逐个验证 order-list、query-order、query-my-account、query-my-coupons、query-my-prizes、list-nutrition-foods、campaign-calendar
- 关键发现：order-list 无分页参数（定位为"最近一季回忆录"）；query-order 含官方商品图与券名（回忆录插图零版权风险）
- 解决响应格式问题：MCP 返回"Markdown 包裹 JSON"，实现 JSON 游标解码器（`mcd_client.py`）

### 阶段三 · 产品方案与数据组装（WorkBuddy 会话）

- 盘点 13 项可用数据 → 设计三条内容主线（金钱逆转剧/习惯发现剧/时光追忆剧）与 4 个情绪爆点页
- 制定"数值不进 LLM"原则：数字全部来自 MCP 原始数据，LLM 只做叙事

### 阶段四 · Demo 开发（WorkBuddy 会话）

- 实现 gather → profile → build_book 三层管线，生成 13 页翻页书 v1
- 迭代 v2：干饭时钟改为「麦门生物钟」；新增人格鉴定书/麦门文学/失踪人口三个传播页
- 精致化三批：色彩收敛 22→18、金币勋章墙（方案 A）、钢印、拍立得相框、天平真实比例、封面拱门三连修

### 阶段五 · 增长与泛化（WorkBuddy 会话）

- 逆向 172 星冠军 README + 两个 0 星项目，产出增长方案（README 基建/分发飞轮/站外钩子）
- 用户多形态分析：1 单边缘数据压力测试，设计 20+ 页面级兜底矩阵与 bad-text 硬校验（`fallback.py`）
- 实施四个传播钩子：开卷三问、麦门忏悔室（5 宗罪+已赦免）、文学重掷池（10 句）、勋章隐藏款进度

### 工程产出

| 文件 | 说明 |
|---|---|
| mcd_client.py | MCP 客户端（握手/重试/游标解码） |
| gather.py / fetch_details.py | 数据采集与详情 |
| stats.py | 确定性画像计算 |
| fallback.py | 用户分型 + 每页兜底决策 |
| build_book.py | 章节编排 + 金句库 + 翻页书渲染 |
| book.html | 最终产物：18 页翻页书 |
