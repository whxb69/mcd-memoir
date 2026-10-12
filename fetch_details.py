#!/usr/bin/env python3
"""Fetch query-order detail for every order (images, discounts, coupons)."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mcd_client import McdClient

DATA = os.path.join(HERE, "data")
token = os.environ.get("MCD_MCP_TOKEN")
if not token:
    print("no token; keep cached details")
    sys.exit(0)

orders = json.load(open(f"{DATA}/order_list.json")).get("data", {}).get("list", [])
cli = McdClient(token)
details = {}
out_path = f"{DATA}/details.json"
if os.path.exists(out_path):
    details = json.load(open(out_path))
for i, o in enumerate(orders):
    oid = o["orderId"]
    if oid in details:
        continue
    print(f"· detail {i+1}/{len(orders)} {oid[:16]}...")
    d = cli.call("query-order", {"orderId": oid})
    details[oid] = d.get("data", d) if isinstance(d, dict) else {"_raw": str(d)[:200]}
    time.sleep(0.5)
json.dump(details, open(out_path, "w"), ensure_ascii=False, indent=1)
print(f"✓ {len(details)} order details saved")
