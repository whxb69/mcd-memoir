# MCP_INTEGRATION · 麦当劳 MCP 集成说明

> 本项目基于麦当劳中国官方 MCP Server（`https://mcp.mcd.cn`，streamable HTTP + Bearer Token）。
> 共调用 8 个只读工具，全链路不执行任何写操作（不下单、不领券、不抽奖、不取消）。

## 一、调用链路总览

```
┌─ gather.py ────────────────────────────────────────────┐
│ order-list          历史订单列表（时间线骨架）           │
│ query-my-account    积分账户（花园/忏悔室素材）          │
│ query-my-coupons    卡包券（后记入场券/见死不救）        │
│ query-my-prizes     抽奖奖品（勋章墙）                   │
│ list-nutrition-foods 营养库160品（米饭换算/朋克养生）     │
└────────────────────────────────────────────────────────┘
┌─ fetch_details.py ─────────────────────────────────────┐
│ query-order         逐单详情：官方商品图/原价/实付/      │
│                     优惠金额/券名/套餐子项/定制项         │
└────────────────────────────────────────────────────────┘
┌─ build_book.py（纯本地，无 MCP 调用）───────────────────┐
│ stats.py 确定性画像 → fallback.py 兜底决策 → HTML        │
└────────────────────────────────────────────────────────┘
```

## 二、逐工具用途与业务价值

| # | Tool | 关键返回字段 | 在书中的位置 | 业务价值 |
|---|---|---|---|---|
| 1 | `order-list` | createTime / storeName / orderProductList / realTotalAmount | 序章、章节时间线 | 回忆录的骨架：每一单都是一章的候选 |
| 2 | `query-order` | productImage / totalAmount / totalDiscountAmount / couponList / comboItemList | 章节主视觉、汉堡天平、忏悔室 | "原价¥57.5→实付¥27.9，省¥29.6"——省钱故事的真实依据 |
| 3 | `query-my-account` | availablePoint / expiredPoint / accumulativePoint | 积分花园、忏悔室、后记 | 把"过期积分"变成可感知的损失（沉默成本可视化） |
| 4 | `query-my-coupons` | 券名/用券价/有效期 | 后记入场券、见死不救 | 消费闭环：书翻完 → 下一章今天开演 |
| 5 | `query-my-prizes` | 节气徽章列表+状态 | 节气勋章墙 | 收藏感 + 隐藏款进度（37.5%） |
| 6 | `list-nutrition-foods` | 160 品 kcal/蛋白质/钠等 | 序章米饭换算、朋克养生罪 | "≈19.9 碗米饭"的具象化 |
| 7 | `campaign-calendar` | 当月活动 | （预留：后记活动钩子） | 场景延伸 |
| 8 | `now-time-info` | 服务器时间 | 兜底时间源 | 生成时间戳、券过期判定基准 |

## 三、工程细节

### 1. 响应格式解包

MCP 文本返回有两种形态：纯 JSON，或「Markdown 字段说明 + `## Original Response` + JSON」混合体，且 JSON 前可能夹自然语言行。`mcd_client.py` 使用 **JSON 游标解码**（`JSONDecoder().raw_decode` 从首个 `{` 起逐位置尝试），两种形态统一处理。

### 2. "数值不进 LLM" 原则

- 所有金额/积分/日期/券名直接取自 MCP 原始 JSON，渲染层仅做格式化（`fmt_money`）与 HTML 转义
- 叙事文案由 `build_book.py` 内的**规则模板**生成（金句池 10 条为写死常量），模板中出现的每个数字都绑定 profile 字段
- `fallback.py` 的全部判定为确定性规则（阈值+正则），无 LLM 参与

### 3. 只读约束

代码中不存在 create-order / cancel-order / auto-bind-coupons / draw-lottery / mall-create-order 等写操作的调用。勋章墙的"去抽奖"引导是给用户的自然语言提示，不由程序代执行。

### 4. 兜底与用户分型

见 `fallback.py`：novice（2-4 单）/ regular（5-19）/ veteran（≥20）三档；每个页面有对应降级分支；`build_book()` 末尾 BAD_TEXTS 硬校验，命中即拒绝发布。

### 5. 配置方式

WorkBuddy 自定义连接器：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_MCP_TOKEN" }
    }
  }
}
```

本项目通过同一 Token 以 HTTP 直连（等价配置），Token 仅从环境变量 `MCD_MCP_TOKEN` 读取，不落盘、不入库。
