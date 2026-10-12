#!/usr/bin/env python3
"""Gather all raw data needed for the memoir via MCP (or --demo uses cached data)."""
import json, os, sys, time, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mcd_client import McdClient
from stats import parse_nutrition, build_profile

DATA = os.path.join(HERE, "data")

def load_local(name):
    p = os.path.join(DATA, name)
    if os.path.exists(p):
        with open(p) as f:
            raw = f.read()
        try:
            return json.loads(raw)
        except Exception:
            try:
                return json.loads(json.loads(raw))
            except Exception:
                return None
    return None

def gather(token: str | None):
    if token:
        from mcd_client import McdClient as C
        cli = C(token)
        print("· order-list ..."); orders = cli.call("order-list")
        time.sleep(0.4)
        print("· query-my-account ..."); account = cli.call("query-my-account")
        time.sleep(0.4)
        print("· query-my-coupons ..."); coupons = cli.call("query-my-coupons", {"page": "1", "pageSize": "50"})
        time.sleep(0.4)
        print("· query-my-prizes ..."); prizes = cli.call("query-my-prizes", {"pageNum": "1", "pageSize": "20"})
        time.sleep(0.4)
        print("· list-nutrition-foods ..."); nutrition = cli.call("list-nutrition-foods")
        json.dump(orders, open(f"{DATA}/order_list.json", "w"), ensure_ascii=False, indent=1)
        json.dump(account, open(f"{DATA}/account.json", "w"), ensure_ascii=False, indent=1)
        json.dump(coupons, open(f"{DATA}/coupons.json", "w"), ensure_ascii=False, indent=1)
        json.dump(prizes, open(f"{DATA}/prizes.json", "w"), ensure_ascii=False, indent=1)
        json.dump(nutrition, open(f"{DATA}/nutrition.json", "w"), ensure_ascii=False, indent=1)
    else:
        print("· demo mode: using cached data/")
        orders = load_local("order_list.json")
        account = load_local("account.json")
        coupons = load_local("coupons.json")
        prizes = load_local("prizes.json")
        nutrition = load_local("nutrition.json")
    return orders, account, coupons, prizes, nutrition

def parse_coupons(coupons):
    """Coupons arrive as markdown; extract name/price/expiry/tag lines."""
    out = []
    if isinstance(coupons, str):
        blocks = coupons.split("## ")[1:]
        for b in blocks:
            name = b.splitlines()[0].strip() if b.splitlines() else ""
            price = re_search(r"\*\*优惠\*\*: ¥([\d.]+)", b)
            expiry = re_search(r"\*\*有效期\*\*: ([^\\n]+)", b)
            tag = re_search(r"\*\*标签\*\*: (.+)", b)
            if name:
                out.append({"name": name, "price": price, "expiry": (expiry or "")[:60], "tag": tag})
    return out

def parse_prizes(prizes):
    if isinstance(prizes, dict):
        data = prizes.get("data", {})
        if isinstance(data, dict):
            return data.get("prizes", []) or []
    return []

import re
def re_search(pat, s):
    m = re.search(pat, s or "")
    return m.group(1) if m else ""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=os.environ.get("MCD_MCP_TOKEN"))
    ap.add_argument("--out", default=os.path.join(HERE, "profile.json"))
    args = ap.parse_args()
    orders, account, coupons, prizes, nutrition = gather(args.token)
    olist = (orders or {}).get("data", {}).get("list", []) if isinstance(orders, dict) else []
    ntable = parse_nutrition(nutrition.get("data") if isinstance(nutrition, dict) else nutrition)
    profile = build_profile(olist, account if isinstance(account, dict) else {}, ntable)
    profile["coupons"] = parse_coupons(coupons)
    profile["prizes"] = parse_prizes(prizes)
    profile["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(profile, open(args.out, "w"), ensure_ascii=False, indent=1)
    print(f"✓ profile.json written: {profile['order_count']} orders, ¥{profile['total_pay']}, {len(ntable)} nutrition items")
