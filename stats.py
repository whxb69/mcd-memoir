#!/usr/bin/env python3
"""Compute the memoir profile from raw MCP data. Numbers never pass through LLM."""
import re
from datetime import datetime
from collections import Counter

def parse_nutrition(data) -> dict:
    """Parse the compact table: '  name,null,1288,308,16,16,24,781,213'."""
    table = {}
    if isinstance(data, str):
        for line in data.splitlines():
            m = re.match(r"\s+(.+?),null,([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+)\s*$", line)
            if m:
                table[m.group(1).strip()] = {
                    "kj": float(m.group(2)), "kcal": float(m.group(3)),
                    "protein": float(m.group(4)), "fat": float(m.group(5)),
                    "carb": float(m.group(6)), "sodium": float(m.group(7)),
                    "calcium": float(m.group(8))}
    return table

def norm(s: str) -> str:
    return re.sub(r"[\s（）()\-—·]", "", s or "").lower()

def match_nutrition(product_name: str, table: dict):
    """Substring match, longest key first. Returns nutrition dict or None."""
    p = norm(product_name)
    for name in sorted(table, key=lambda k: -len(norm(k))):
        n = norm(name)
        if n and (n in p or p in n):
            return {"matched": name, **table[name]}
    return None

def build_profile(orders: list, account: dict, nutrition_table: dict) -> dict:
    orders = [o for o in orders if o.get("createTime")]
    orders.sort(key=lambda o: o["createTime"])
    total_pay = sum(float(o.get("realTotalAmount") or 0) for o in orders)
    hours = Counter(datetime.strptime(o["createTime"], "%Y-%m-%d %H:%M:%S").hour for o in orders)
    stores = Counter(o.get("storeName", "未知门店") for o in orders)
    items, item_count = Counter(), Counter()
    total_saved, detail_cache = 0.0, {}
    customs = Counter()
    kcal_total = 0.0
    kcal_known = 0
    for o in orders:
        for p in o.get("orderProductList", []):
            qty = p.get("quantity", 1)
            items[p["productName"]] += qty
            item_count[p["productName"]] += 1
            # kcal: prefer combo children (套餐子项才有营养表条目), fallback to product itself
            matched_any = False
            children = [c.get("name") or c.get("itemName") or "" for c in (p.get("comboItemList") or [])]
            for cand in (children if children else [p["productName"]]):
                if not cand:
                    continue
                nm = match_nutrition(cand, nutrition_table)
                if nm:
                    kcal_total += nm["kcal"] * qty
                    matched_any = True
            if matched_any:
                kcal_known += 1
            for c in p.get("comboItemList", []) or []:
                cn = c.get("name") or c.get("itemName") or ""
                if cn and ("冰" in cn or "糖" in cn or "热" in cn or "去" in cn):
                    customs[cn] += 1
        detail_cache[o["orderId"]] = None  # filled by fetch detail
    span_days = ""
    if len(orders) >= 2:
        d1 = datetime.strptime(orders[0]["createTime"], "%Y-%m-%d %H:%M:%S")
        d2 = datetime.strptime(orders[-1]["createTime"], "%Y-%m-%d %H:%M:%S")
        span_days = (d2 - d1).days
    # dominant hour bucket
    lunch = sum(v for h, v in hours.items() if 10 <= h < 15)
    dinner = sum(v for h, v in hours.items() if 17 <= h < 23)
    night = sum(v for h, v in hours.items() if h >= 23 or h < 5)
    morning = sum(v for h, v in hours.items() if 5 <= h < 10)
    if night:
        person = "深夜麦门人"
    elif morning and morning >= lunch:
        person = "早餐先行者"
    elif dinner > lunch:
        person = "晚餐档信徒"
    else:
        person = "午餐精准干饭人"
    top_item = items.most_common(1)[0] if items else ("-", 0)
    acc = account.get("data", {}) if isinstance(account, dict) else {}
    return {
        "order_count": len(orders),
        "total_pay": round(total_pay, 1),
        "first_order": orders[0]["createTime"] if orders else "",
        "last_order": orders[-1]["createTime"] if orders else "",
        "span_days": span_days,
        "hours": dict(hours),
        "person_type": person,
        "top_stores": stores.most_common(3),
        "store_count": len(stores),
        "top_items": items.most_common(5),
        "item_variety": len(items),
        "customs": customs.most_common(5),
        "top_item_share": round(top_item[1] / len(orders), 2) if orders else 0,
        "kcal_total": round(kcal_total),
        "kcal_known_orders": kcal_known,
        "rice_bowls": round(kcal_total / 290, 1),   # 1 bowl rice ≈ 290kcal
        "account": {
            "accumulative": acc.get("accumulativePoint", "0"),
            "available": acc.get("availablePoint", "0"),
            "expired": acc.get("expiredPoint", "0"),
            "expire_rate": (round(float(acc.get("expiredPoint", 0)) /
                                  max(float(acc.get("accumulativePoint", 1)), 0.1) * 100, 1)
                            if acc else 0),
            "bigmac_equiv": round(float(acc.get("expiredPoint", 0)) / 22.5, 1),  # 巨无霸≈22.5分/元
        },
        "detail_cache": detail_cache,
    }

def chapter_rules(orders: list, profile: dict) -> list:
    """Deterministic chapter selection. Each chapter = facts only; narration is applied later."""
    chs = []
    if orders:
        chs.append({"id": "first", "orders": [orders[0]], "title": "一切的开始", "kind": "first"})
    big = max(orders, key=lambda o: float(o.get("realTotalAmount") or 0), default=None)
    if big:
        chs.append({"id": "biggest", "orders": [big], "title": "最阔绰的一单", "kind": "money"})
    return chs
