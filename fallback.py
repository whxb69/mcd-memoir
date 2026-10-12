#!/usr/bin/env python3
"""User typing + per-page fallback decisions. Pure functions, no side effects.
Every page of the book must resolve to a render decision BEFORE build_book touches HTML."""
import re
from datetime import datetime

def user_type(n_orders: int) -> str:
    """novice 2-4 / regular 5-19 / veteran 20+. 0-1 => rejected by caller."""
    if n_orders <= 4:
        return "novice"
    if n_orders <= 19:
        return "regular"
    return "veteran"

def safe_int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default

def gap_stats(orders):
    times = sorted(datetime.strptime(o["createTime"], "%Y-%m-%d %H:%M:%S")
                   for o in orders if o.get("createTime"))
    if not times:
        return 0, 0.0, ""
    days_since = (datetime.now() - times[-1]).days
    gaps = [(times[i+1] - times[i]).days for i in range(len(times) - 1)]
    gap_avg = round(sum(gaps) / len(gaps), 1) if gaps else 0.0
    return days_since, gap_avg, times[-1].strftime("%Y-%m-%d")

def coupon_dates(coupons, generated_at: str):
    """Count expired / soon-to-expire coupons (within 3 days of generated_at)."""
    try:
        now = datetime.strptime(generated_at, "%Y-%m-%d %H:%M:%S")
    except Exception:
        now = datetime.now()
    expired, soon, value = 0, 0, 0.0
    for c in coupons:
        ds = re.findall(r"\d{4}-\d{2}-\d{2}", c.get("expiry") or "")
        if not ds:
            continue
        try:
            d = datetime.strptime(max(ds), "%Y-%m-%d")
        except Exception:
            continue
        diff = (d - now).days
        if diff < 0:
            expired += 1
            value += safe_int(c.get("price"), 0)
        elif diff <= 3:
            soon += 1
    return expired, soon, round(value, 1)

def plan_pages(profile, orders, coupons, total_saved=0.0) -> dict:
    """One decision dict per page. build_book consumes this; never improvises."""
    n = profile.get("order_count", 0)
    utype = user_type(n)
    acc = profile.get("account", {})
    days_since, gap_avg, last_day = gap_stats(orders)
    expired_coupons, soon_coupons, coupon_loss = coupon_dates(
        coupons, profile.get("generated_at") or "")
    span_days = profile.get("span_days") or 0
    customs = profile.get("customs") or []
    saved_raw = float(total_saved or 0)

    plan = {"user_type": utype, "days_since": days_since, "gap_avg": gap_avg,
            "last_day": last_day, "expired_coupons": expired_coupons,
            "soon_coupons": soon_coupons, "coupon_loss": coupon_loss}

    # cover
    plan["cover_sub"] = (f'用 {n} 张真实订单<br>装订成 {span_days} 天的麦门时光'
                         if span_days else
                         f'用 {n} 张真实订单<br>装订成一本麦门时光')
    # opening questions
    q2 = (f'你已经 {days_since} 天没有推开那扇门了——麦门想你了。' if days_since > 0
          else '书还没合上，你已经翻开了下一章——今天来过。')
    q3 = (f'{acc.get("expired", 0)} 个积分被你随手弄丢了——后来，它们在花园里开成了花。'
          if safe_int(acc.get("expired")) > 0 else
          '你的积分一个都没丢过。这份谨慎，很少见。')
    plan["questions"] = {"q2": q2, "q3": q3}
    # profile grid: hide rice card when kcal missing
    plan["show_rice"] = profile.get("kcal_total", 0) > 0
    # chapter 2 customs fallback
    plan["customs_mode"] = "normal" if customs else "plain_believer"
    # chapter 4 escape / never-left
    plan["escape_mode"] = "normal" if profile.get("store_count", 0) > 1 else "never_left"
    # chapter 5 actuary
    plan["saved"] = saved_raw
    plan["actuary_mode"] = "normal" if saved_raw > 0 else "price_hero"
    # clock
    hours = profile.get("hours") or {}
    plan["clock_uniform"] = len(hours) <= 1
    # persona radar degradation: count dims below 20
    dims = [profile.get("top_item_share", 0) * 100,
            100,  # loyalty-ish, recomputed by caller if needed
            profile.get("top_stores", [[0, 0]])[0][1] / max(n, 1) * 100,
            profile.get("top_item_share", 0) * 100]
    plan["radar_ok"] = sum(1 for d in dims if d < 20) < 2
    plan["persona_title_fallback"] = "见习麦门人" if utype == "novice" else None
    # literature: notes availability handled by template; keep flag
    plan["lit_mode"] = "pool"
    # missing person
    if days_since == 0:
        plan["missing_mode"] = "today"
    elif gap_avg == 0:
        plan["missing_mode"] = "first_time"
    else:
        plan["missing_mode"] = "normal"
    # balance
    plan["balance_mode"] = "normal" if saved_raw > 0 else "no_coupon"
    # graveyard
    plan["garden_mode"] = ("normal" if safe_int(acc.get("expired")) > 0
                              else "fortress")
    # badges
    plan["show_badges"] = len(profile.get("prizes", [])) > 0
    # confessions
    plan["confession_enabled"] = True
    # epilogue
    plan["hero_coupon"] = hero_coupon(coupons)
    plan["epilogue_mode"] = "normal" if coupons else "empty"
    return plan


def hero_coupon(coupons):
    """Coupon with the latest expiry; None when empty."""
    if not coupons:
        return None
    def key(c):
        ds = re.findall(r"\d{4}-\d{2}-\d{2}", c.get("expiry") or "")
        return max(ds) if ds else "0000-00-00"
    return max(coupons, key=key)


def confessions(profile, orders, coupons) -> list:
    """Deterministic 'sins'. Returns list of dicts: {name, text, source}."""
    sins = []
    acc = profile.get("account", {})
    n = profile.get("order_count", 0)
    span = profile.get("span_days") or 0
    expired = safe_int(acc.get("expired"))
    if expired > 0:
        sins.append({"name": "花期误了",
                     "text": f"你的 {expired} 分积分没能撑到兑现那天。不过别难过——它们已经在花园里开成了 {acc.get('bigmac_equiv', 0)} 朵小花。",
                     "source": "数据 query-my-account"})
    ti = profile.get("top_items") or []
    if ti and profile.get("top_item_share", 0) >= 0.5:
        t0, n0 = ti[0]
        sins.append({"name": "从一而终",
                     "text": f"你把 {int(profile['top_item_share']*100)}% 的麦门人生给了「{t0.strip()}」。菜单上有 160 种可能，你选了命中注定的那一种。",
                     "source": "数据 order-list · 商品统计"})
    customs = profile.get("customs") or []
    kcal = profile.get("kcal_total", 0)
    if customs and "无糖" in customs[0][0] and kcal > 2000:
        sins.append({"name": "朋克养生",
                     "text": f"你点了 {customs[0][1]} 次「{customs[0][0]}」——配着炸鸡和薯条。快乐水戒了糖，没戒快乐，这叫战略性养生。",
                     "source": "数据 query-order · comboItemList"})
    stores = profile.get("top_stores") or []
    if stores and n and stores[0][1] / n >= 0.7 and profile.get("store_count", 1) > 1:
        sins.append({"name": "深宅不出",
                     "text": f"全城 {profile['store_count']} 家麦门，{int(stores[0][1]/n*100)}% 的饭你都进了同一家。你不是食客，你是编外员工。",
                     "source": "数据 order-list · storeName"})
    expired_c, soon_c, loss = coupon_dates(coupons, profile.get("generated_at") or "")
    if expired_c + soon_c > 0:
        state = "已经" if expired_c else "正在"
        sins.append({"name": "见死不救",
                     "text": f"{expired_c + soon_c} 张券{state}离开你，面值约 ¥{loss}。你上次想起它们，还是领它们的时候。",
                     "source": "数据 query-my-coupons"})
    # universal fallback sin
    if span:
        sins.append({"name": "日子过得太快",
                     "text": f"你与麦门相识 {span} 天，第一单像上周的事。时间都去哪了？都变成订单了。",
                     "source": "数据 order-list"})
    return sins[:5]
