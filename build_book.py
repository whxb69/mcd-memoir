#!/usr/bin/env python3
"""Build the memoir book HTML from profile + order details.
Narration is rule-based templating over MCP facts — numbers never pass through an LLM."""
import json, os, sys, html, re
from datetime import datetime
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD, RED, CREAM, INK = "#FFC72C", "#DA291C", "#FFF8E7", "#2B1D0E"

def esc(s): return html.escape(str(s), quote=True)

def fmt_money(v):
    f = float(v)
    return f"{f:.1f}".rstrip("0").rstrip(".")

def load(name):
    with open(os.path.join(HERE, name)) as f:
        return json.load(f)

def load_raw(name):
    """data/*.json may hold dict or str."""
    with open(os.path.join(HERE, "data", name)) as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except Exception:
        return raw

def combo_children(detail):
    out = []
    for p in detail.get("orderProductList", []):
        for c in (p.get("comboItemList") or []):
            nm = c.get("itemName") or c.get("name") or ""
            if nm:
                out.append(nm)
    if not out:
        for p in detail.get("orderProductList", []):
            out.append(p.get("productName", ""))
    return out

def main_img(detail):
    for p in detail.get("orderProductList", []):
        img = p.get("productImage")
        if img:
            return img
    return ""

def fmt_combo(children):
    return " ＋ ".join(children[:4]) + ("…" if len(children) > 4 else "")

def build_chapters(profile, details, orders):
    olist = sorted([o for o in orders if o.get("createTime")], key=lambda o: o["createTime"])
    chs = []
    # ch1 first order
    first = olist[0]
    fd = details.get(first["orderId"], {})
    chs.append({
        "kicker": "第一章 · 一切的开始",
        "title": "第一口，被记住了",
        "img": main_img(fd),
        "date": first["createTime"][:10],
        "lines": [
            f"{first['createTime'][:16]}，{esc(first.get('storeName','麦当劳'))}。",
            f"你吃下了被记录的第一单：{esc(first['orderProductList'][0]['productName'])}。",
        ],
        "combo": fmt_combo(combo_children(fd)),
        "note": f"实付 ¥{fmt_money(first.get('realTotalAmount', 0))} · 数据 order-list",
    })
    # ch2 customs (无糖/少冰)
    customs = profile.get("customs", [])
    if customs:
        c0, n0 = customs[0]
        word = "无糖" if "无糖" in c0 else ("少冰" if "少冰" in c0 else "定制")
        chs.append({
            "kicker": "第二章 · 专属口味",
            "title": "快乐要有，糖分不要" if word == "无糖" else "你的口味，有主见",
            "img": main_img(fd) if not customs else "",
            "lines": [
                f"「{esc(c0)}」在你的订单里出现了 {n0} 次。",
                "每一单都是同一个坚持——" + ("快乐水照喝，糖分免谈。养生朋克的尽头，是麦门。" if word == "无糖" else "你很清楚自己要什么。"),
            ],
            "combo": "",
            "note": "数据 query-order · comboItemList",
        })
    # ch3 top item
    ti = profile.get("top_items", [])
    if ti:
        t0, n0 = ti[0]
        share = profile.get("top_item_share", 0)
        chs.append({
            "kicker": "第三章 · 信仰之选",
            "title": "这不是点餐，是信仰",
            "img": "",
            "lines": [
                f"「{esc(t0)}」出现了 {n0} 次。",
                f"{profile['order_count']} 单里有 {n0} 单是它——{int(share*100)}% 的麦门人生，都是同一个味道。",
            ],
            "combo": "",
            "note": "数据 order-list · 商品统计",
        })
    # ch4 the escape (non-top store)
    if profile["store_count"] > 1:
        home_store = profile["top_stores"][0][0]
        home_short = home_store.split("(")[0].replace("麦当劳", "")
        away = [o for o in olist if o.get("storeName") != home_store]
        if away:
            a = away[0]
            ad = details.get(a["orderId"], {})
            chs.append({
                "kicker": "第四章 · 那一次出走",
                "title": "忠诚之外的一天",
                "img": main_img(ad),
                "date": a["createTime"][:10],
                "lines": [
                    f"{a['createTime'][:10]}，你离开了常驻的{home_short}店…",
                    f"去了 {esc(a.get('storeName',''))}。仅此一次。",
                    f"{profile['top_stores'][0][1]} : 1 的忠诚比，麦门认证死忠粉。",
                ],
                "combo": fmt_combo(combo_children(ad)),
                "note": "数据 order-list · storeName",
            })
    # ch5 the actuary (biggest saving)
    best, best_d, best_save = None, None, 0.0
    for o in olist:
        d = details.get(o["orderId"], {})
        s = float(d.get("totalDiscountAmount") or 0)
        if s > best_save:
            best, best_d, best_save = o, d, s
    if best_d is not None:
        coup = (best_d.get("couponList") or [{}])[0].get("couponName", "优惠券")
        chs.append({
            "kicker": "第五章 · 精算师时刻",
            "title": "最划算的一顿",
            "img": main_img(best_d),
            "date": best["createTime"][:10],
            "lines": [
                f"{best['createTime'][:10]} 的这一单：",
                f"原价 ¥{fmt_money(best_d.get('totalAmount',0))}，一张「{esc(coup)}」之后，实付 ¥{fmt_money(best_d.get('realTotalAmount',0))}。",
                f"省下 ¥{fmt_money(best_save)} —— 相当于白吃一个巨无霸还有找。",
            ],
            "combo": fmt_combo(combo_children(best_d)),
            "note": "数据 query-order · totalDiscountAmount",
        })
    return chs

def money_stats(details):
    orig = sum(float(d.get("totalAmount") or 0) for d in details.values())
    paid = sum(float(d.get("realTotalAmount") or 0) for d in details.values())
    saved = sum(float(d.get("totalDiscountAmount") or 0) for d in details.values())
    return round(orig, 1), round(paid, 1), round(saved, 1)


def garden_svg(flower_slots):
    """ACNH-inspired premium garden. flower_slots: list of {date, pct} (pct=discount ratio 0-1)."""
    import math as _m
    W, H = 680, 380
    ground_y = 150
    n = max(len(flower_slots), 1)
    # positions along the dirt bed
    xs = [90 + i * (500 / max(n - 1, 1)) if n > 1 else 340 for i in range(n)]

    def flower(x, base_y, pct, date, idx, watered=True):
        scale = 0.55 + 0.75 * pct
        h = 62 * scale
        pid = f"f{idx}"
        grad = ["url(#pRed)", "url(#pGold)", "url(#pPink)", "url(#pBlue)"][idx % 4]
        petals = ""
        for a in range(8):
            ang = a * 45 - 90
            px = _m.cos(_m.radians(ang)) * 15
            py = _m.sin(_m.radians(ang)) * 15
            rot = ang + 90
            petals += (f'<ellipse cx="{px:.1f}" cy="{py:.1f}" rx="9.5" ry="13.5" '
                       f'fill="{grad}" transform="rotate({rot} {px:.1f} {py:.1f})" '
                       f'class="petal" style="--d:{idx*90}ms"/>')
        date_txt = (f'<text x="0" y="10" text-anchor="middle" font-size="8.5" '
                    f'fill="#5C3A12" opacity=".75">{date[5:]}</text>') if date else ""
        if watered:
            return (f'<g class="flower" transform="translate({x} {base_y})">'
                    f'<path d="M 0 0 C -3 {-h*0.4} 3 {-h*0.7} 0 {-h}" fill="none" stroke="#3E8E3E" stroke-width="6" stroke-linecap="round"/>'
                    f'<path d="M -2 {-h*0.42} Q -22 {-h*0.5} -30 {-h*0.34} Q -12 {-h*0.24} -2 {-h*0.42}" fill="#5CBF4E"/>'
                    f'<path d="M 2 {-h*0.6} Q 22 {-h*0.68} 28 {-h*0.52} Q 10 {-h*0.42} 2 {-h*0.6}" fill="#4FAF41"/>'
                    f'<ellipse cx="0" cy="2" rx="26" ry="7" fill="#2B1D0E" opacity=".12"/>'
                    f'<g transform="translate(0 {-h-10})">{petals}'
                    f'<circle r="8.5" fill="url(#pCore)"/></g>'
                    f'<g class="date-tag" transform="translate(0 14)">{date_txt}</g></g>')
        return (f'<g class="sprout" transform="translate({x} {base_y})" onclick="waterFlower(this,{idx})">'
                f'<ellipse cx="0" cy="2" rx="20" ry="6" fill="#2B1D0E" opacity=".10"/>'
                f'<path d="M 0 0 Q -2 -9 0 -14" fill="none" stroke="#7FA86B" stroke-width="4.5" stroke-linecap="round"/>'
                f'<path d="M 0 -9 Q -9 -13 -11 -6 Q -4 -4 0 -9" fill="#9CC98A"/>'
                f'<path d="M 0 -7 Q 9 -11 11 -4 Q 4 -2 0 -7" fill="#8FBA7C"/>'
                f'<circle class="glint" cx="12" cy="-14" r="3" fill="#7FC8E8" opacity="0"/>'
                f'<text x="0" y="16" text-anchor="middle" font-size="8.5" fill="#5C3A12" opacity=".6">{date[5:]}</text></g>')

    flowers = ""
    for i, slot in enumerate(flower_slots):
        flowers += flower(xs[i], ground_y + 88 + (i % 3) * 16, slot["pct"], slot["date"], i, True)
    for j in range(2):
        flowers += flower(xs[-1] + 60 + j * 55, ground_y + 100, 0.3, "", 10 + j, False)

    tiles = "".join(
        f'<ellipse cx="{180+i*85}" cy="{ground_y+118}" rx="{58-i%3*8}" ry="{19-i%2*3}" '
        f'fill="none" stroke="#5CA845" stroke-width="2"/>' for i in range(6))
    clouds = "".join(
        f'<ellipse cx="{110+i*230}" cy="{34+i*12}" rx="{44-i%2*10}" ry="{14-i%2*3}" fill="#fff" opacity="{.85-i*.1}"/>'
        for i in range(3))
    bokeh = "".join(
        f'<circle cx="{80+i*97}" cy="{ground_y+40+(i%3)*24}" r="{3+i%3*2}" fill="#FFF8E7" opacity="{.25-i*.03}"/>'
        for i in range(6))
    petals_fall = "".join(
        f'<path class="fall-petal" style="--fd:{i*1.7}s;--fx:{(i*167)%600+40}px" d="M 0 0 Q 4 3 0 7 Q -4 3 0 0" '
        f'fill="#DA291C" opacity=".5" transform="translate(0 0)"/>' for i in range(5))
    hedge = ""
    for i in range(9):
        hx = 20 + i * 80
        hedge += (f'<ellipse cx="{hx}" cy="{ground_y-6}" rx="52" ry="20" fill="#4E9E3C"/>'
                  f'<ellipse cx="{hx-10}" cy="{ground_y-12}" rx="30" ry="12" fill="#5FB04A" opacity=".8"/>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:660px;border-radius:18px;display:block;margin:0 auto" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="积分花园">'
            f'<defs>'
            f'<linearGradient id="gSky" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#8ECFF2"/><stop offset=".55" stop-color="#C8E9FA"/><stop offset="1" stop-color="#EAF7E2"/>'
            f'</linearGradient>'
            f'<linearGradient id="gGrass" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#79C258"/><stop offset="1" stop-color="#549B3E"/>'
            f'</linearGradient>'
            f'<radialGradient id="pRed" cx="35%" cy="30%">'
            f'<stop offset="0" stop-color="#FFB3A0"/><stop offset=".6" stop-color="#FF6B5A"/><stop offset="1" stop-color="#E24B3A"/>'
            f'</radialGradient>'
            f'<radialGradient id="pGold" cx="35%" cy="30%">'
            f'<stop offset="0" stop-color="#FFF3B8"/><stop offset=".6" stop-color="#FFD34D"/><stop offset="1" stop-color="#F5A700"/>'
            f'</radialGradient>'
            f'<radialGradient id="pPink" cx="35%" cy="30%">'
            f'<stop offset="0" stop-color="#FFD9EC"/><stop offset=".6" stop-color="#F4A8CE"/><stop offset="1" stop-color="#E886B8"/>'
            f'</radialGradient>'
            f'<radialGradient id="pBlue" cx="35%" cy="30%">'
            f'<stop offset="0" stop-color="#C8ECFF"/><stop offset=".6" stop-color="#8FCDEE"/><stop offset="1" stop-color="#5FA8D3"/>'
            f'</radialGradient>'
            f'<radialGradient id="pCore" cx="35%" cy="30%">'
            f'<stop offset="0" stop-color="#FFF6D8"/><stop offset="1" stop-color="#E2A800"/>'
            f'</radialGradient>'
            f'<filter id="soft2" x="-30%" y="-30%" width="160%" height="160%">'
            f'<feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#1F3A12" flood-opacity=".22"/>'
            f'</filter>'
            f'</defs>'
            f'<rect width="{W}" height="{H}" fill="url(#gSky)"/>'
            f'{clouds}'
            f'{hedge}'
            f'<path d="M 0 {ground_y} L {W/2} {ground_y-46} L {W} {ground_y} L {W} {H} L 0 {H} Z" fill="url(#gGrass)"/>'
            f'<path d="M 0 {ground_y} L {W/2} {ground_y-46} L {W} {ground_y}" fill="none" stroke="#69B14E" stroke-width="3" opacity=".7"/>'
            f'{tiles}'
            f'<ellipse cx="340" cy="{ground_y+96}" rx="255" ry="74" fill="#C9A06B" opacity=".5"/>'
            f'<ellipse cx="340" cy="{ground_y+96}" rx="255" ry="74" fill="none" stroke="#A87F4C" stroke-width="2" opacity=".45"/>'
            f'{bokeh}'
            f'{flowers}'
            f'{petals_fall}'
            f'<g transform="translate(96 {ground_y+92})" filter="url(#soft2)">'
            f'<rect x="-3" y="10" width="7" height="30" rx="3" fill="#8A5A28"/>'
            f'<rect x="-56" y="-20" width="112" height="34" rx="7" fill="#C9A06B"/>'
            f'<rect x="-56" y="-20" width="112" height="12" rx="7" fill="#D9B37E"/>'
            f'<circle cx="-48" y="-13" r="1.8" fill="#8A5A28" opacity=".7"/><circle cx="48" cy="-13" r="1.8" fill="#8A5A28" opacity=".7"/>'
            f'<circle cx="0" cy="-13" r="1.8" fill="#8A5A28" opacity=".7"/>'
            f'<text x="0" y="4" text-anchor="middle" font-size="13" font-weight="800" fill="#5C3A12">积分花园</text></g>'
            f'<g transform="translate(588 {ground_y+108})" filter="url(#soft2)" onclick="waterAll()" style="cursor:pointer">'
            f'<rect x="-20" y="-16" width="40" height="30" rx="9" fill="#7FC8E8"/>'
            f'<rect x="-20" y="-16" width="40" height="11" rx="7" fill="#A8DCF0"/>'
            f'<path d="M 18 -9 Q 36 -12 40 4" fill="none" stroke="#7FC8E8" stroke-width="5.5" stroke-linecap="round"/>'
            f'<circle cx="42" cy="7" r="4.5" fill="#A8DCF0"/>'
            f'<path d="M -20 -7 Q -31 -9 -29 2 Q -24 7 -18 3" fill="none" stroke="#7FC8E8" stroke-width="4.5" stroke-linecap="round"/>'
            f'<text x="0" y="30" text-anchor="middle" font-size="11" font-weight="800" fill="#2B6D9E">浇水</text></g>'
            f'<g transform="translate(590 26)">'
            f'<rect x="-72" y="0" width="144" height="34" rx="17" fill="#FFF8E7" opacity=".95" filter="url(#soft2)"/>'
            f'<circle cx="-52" cy="17" r="10" fill="#FFC72C"/>'
            f'<text class="garden-count" x="-34" y="22" font-size="13" font-weight="800" fill="#2B1D0E">0 / {n} 已开花</text></g>'
            f'<text x="340" y="{H-10}" text-anchor="middle" font-size="11" fill="#2F5D24" opacity=".95">'
            f'每朵花 = 一笔真实优惠订单 · 浇水让它们全开 · 数据 query-order / query-my-account</text>'
            f'</svg>')

def tombstones():
    """Six engraved headstones + one dashed 'and more'."""
    stones = ""
    for _ in range(6):
        stones += ('<svg class="tomb" viewBox="0 0 44 54" width="38" height="47">'
                   '<path d="M 8 50 V 22 A 14 14 0 0 1 36 22 V 50" fill="none" stroke="#C99700" stroke-width="2.5"/>'
                   '<line x1="4" y1="50" x2="40" y2="50" stroke="#C99700" stroke-width="2.5"/>'
                   '<line x1="16" y1="28" x2="28" y2="28" stroke="#C99700" stroke-width="2"/></svg>')
    stones += ('<svg class="tomb" viewBox="0 0 44 54" width="38" height="47">'
               '<path d="M 8 50 V 22 A 14 14 0 0 1 36 22 V 50" fill="none" stroke="#C99700" stroke-width="2.5" stroke-dasharray="4 4"/>'
               '<line x1="4" y1="50" x2="40" y2="50" stroke="#C99700" stroke-width="2.5"/></svg>'
               '<span class="tomb-more">…</span>')
    return f'<div class="tombs">{stones}</div>'


def badge_svg(name, size=96):
    """Plan A: embossed coin badge. Milled edge + red golden-arches M + term name."""
    label = f'<text x="50" y="80" text-anchor="middle" font-size="13" font-weight="800" fill="#B71C1C">{esc(name)}</text>' if name else ""
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="麦门勋章">'
            f'<circle cx="50" cy="50" r="47" fill="#FFC72C" stroke="#C99700" stroke-width="2.5"/>'
            f'<circle cx="50" cy="50" r="41.5" fill="none" stroke="#C99700" stroke-width="2.2" stroke-dasharray="1.6 3.6"/>'
            f'<circle cx="50" cy="50" r="35" fill="none" stroke="#C99700" stroke-width="1" opacity=".75"/>'
            f'<path d="M 33 61 A 11.5 17.5 0 0 1 50 36 A 11.5 17.5 0 0 1 67 61" fill="none" '
            f'stroke="#DA291C" stroke-width="7" stroke-linecap="round"/>'
            f'{label}'
            f'</svg>')


def badge_wall(prizes):
    if not prizes:
        return ""
    coins = "".join(
        f'<div class="coin-wrap" style="--i:{i}">{badge_svg(p.get("name", ""))}</div>'
        for i, p in enumerate(prizes[:12]))
    return f'<div class="tray"><div class="coins">{coins}</div></div>'


def persona(profile, orders, details):
    times = [datetime.strptime(o["createTime"], "%Y-%m-%d %H:%M:%S")
             for o in orders if o.get("createTime")]
    mods = sorted(t.hour * 60 + t.minute for t in times)
    med = mods[len(mods) // 2]
    hit = sum(1 for m in mods if abs(m - med) <= 90)
    regularity = round(hit / max(len(mods), 1) * 100)
    custom_orders = 0
    for o in orders:
        d = details.get(o.get("orderId"), {}) or {}
        found = False
        for p in (d.get("orderProductList") or o.get("orderProductList") or []):
            for c in (p.get("comboItemList") or []):
                nm = c.get("itemName") or c.get("name") or ""
                if any(k in nm for k in ("无糖", "少冰", "去冰", "不加冰", "去葱")):
                    found = True
        if found:
            custom_orders += 1
    selfdisc = round(custom_orders / max(len(orders), 1) * 100)
    loyalty = round(profile["top_stores"][0][1] / max(len(orders), 1) * 100)
    focus = round(profile["top_item_share"] * 100)
    mpower = round((regularity + selfdisc + loyalty + focus) / 4, 1)
    if regularity >= 60 and focus >= 50:
        base = "午间钉子户"
    elif loyalty >= 80 and focus >= 50:
        base = "单店死忠粉"
    elif selfdisc >= 50:
        base = "无糖战神"
    else:
        base = "随心麦门人"
    tag = ("自带无糖结界" if selfdisc >= 50 else
           ("定点出现型选手" if regularity >= 60 else "行踪成谜型选手"))
    hm = f"{med // 60:02d}:{med % 60:02d}"
    return {"regularity": regularity, "selfdisc": selfdisc, "loyalty": loyalty,
            "focus": focus, "mpower": mpower, "title": base, "tag": tag,
            "median": hm, "hit": hit, "n": len(mods)}


def clock2_svg(med_str):
    import math
    h, m = map(int, med_str.split(":"))
    ha = ((h % 12) + m / 60) * 30 - 90
    ma = m * 6 - 90
    def pt(ang, r):
        return 150 + r * math.cos(math.radians(ang)), 150 + r * math.sin(math.radians(ang))
    x1, y1 = pt(ha, 60)
    x2, y2 = pt(ma, 96)
    ticks = "".join(
        f'<line x1="{150+120*math.cos(math.radians(a)):.1f}" y1="{150+120*math.sin(math.radians(a)):.1f}" '
        f'x2="{150+132*math.cos(math.radians(a)):.1f}" y2="{150+132*math.sin(math.radians(a)):.1f}" '
        f'stroke="#D8C8A2" stroke-width="3"/>' for a in range(0, 360, 30))
    return (f'<svg viewBox="0 0 300 300" width="240" height="240" style="max-width:64vw">'
            f'<circle cx="150" cy="150" r="140" fill="#fff" stroke="{GOLD}" stroke-width="10"/>'
            f'{ticks}'
            f'<line x1="150" y1="150" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{INK}" stroke-width="10" stroke-linecap="round"/>'
            f'<line x1="150" y1="150" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{RED}" stroke-width="5" stroke-linecap="round"/>'
            f'<circle cx="150" cy="150" r="10" fill="{RED}"/>'
            f'<text x="150" y="212" text-anchor="middle" font-size="22" font-weight="800" fill="{RED}">{med_str}</text>'
            f'</svg>')


def strip_svg(hours, hit, n):
    import math
    hours = {int(k): v for k, v in hours.items()}
    W, H, x0 = 560, 150, 26
    def X(hh):
        return x0 + hh / 24 * (W - 2 * x0)
    noon = (f'<rect x="{X(11):.0f}" y="16" width="{X(13)-X(11):.0f}" height="{H-50}" '
            f'fill="url(#goldhatch)" rx="10"/>'
            f'<text x="{(X(11)+X(13))/2:.0f}" y="34" text-anchor="middle" font-size="12" '
            f'font-weight="700" fill="{INK}">午间黄金档</text>')
    dots = []
    for hh in range(24):
        for i in range(hours.get(hh, 0)):
            cy = H - 36 - i * 15
            color = RED if 10 <= hh < 15 else "#C99700"
            dots.append(f'<circle cx="{X(hh+0.5):.0f}" cy="{cy:.0f}" r="6" fill="{color}"/>')
    line = f'<line x1="{x0}" y1="{H-30}" x2="{W-x0}" y2="{H-30}" stroke="#C9B98F" stroke-width="1.5"/>'
    ticks = "".join(f'<text x="{X(h):.0f}" y="{H-10}" text-anchor="middle" font-size="10" fill="#B4A78F">{h}:00</text>'
                    for h in range(0, 25, 6))
    note = f'<text x="{W-x0}" y="34" text-anchor="end" font-size="12" fill="{RED}" font-weight="700">{hit}/{n} 单命中 ±90min</text>'
    return (f'<svg viewBox="0 0 {W} {H}" width="520" height="139" style="max-width:88vw">'
            f'<defs><pattern id="goldhatch" width="8" height="8" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
            f'<rect width="8" height="8" fill="{GOLD}" opacity="0.30"/>'
            f'<line x1="0" y1="0" x2="0" y2="8" stroke="{GOLD}" stroke-width="3" opacity="0.55"/>'
            f'</pattern></defs>'
            f'{noon}{line}{note}{"".join(dots)}{ticks}</svg>')


def radar_svg(p):
    import math
    labels = [("规律", p["regularity"]), ("自律", p["selfdisc"]),
              ("忠诚", p["loyalty"]), ("专一", p["focus"])]
    cx, cy, R = 150, 138, 84
    def P(i, r):
        ang = -90 + i * 90
        return cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang))
    grids = ""
    for frac in (0.5, 1.0):
        pts = " ".join(f'{P(i, R*frac)[0]:.1f},{P(i, R*frac)[1]:.1f}' for i in range(4))
        grids += f'<polygon points="{pts}" fill="none" stroke="#D8C8A2" stroke-width="1"/>'
    axes = "".join(f'<line x1="{cx}" y1="{cy}" x2="{P(i,R)[0]:.1f}" y2="{P(i,R)[1]:.1f}" stroke="#E4D8BC" stroke-width="1"/>'
                   for i in range(4))
    poly_pts = " ".join(f'{P(i, R*v/100)[0]:.1f},{P(i, R*v/100)[1]:.1f}' for i, (nm, v) in enumerate(labels))
    labels_svg = "".join(
        f'<text x="{P(i,R+26)[0]:.1f}" y="{P(i,R+26)[1]+4:.1f}" text-anchor="middle" font-size="13" '
        f'font-weight="700" fill="{INK}">{nm} {v}</text>'
        for i, (nm, v) in enumerate(labels))
    return (f'<svg viewBox="0 0 300 280" width="250" height="233" style="max-width:64vw">'
            f'{grids}{axes}'
            f'<polygon points="{poly_pts}" fill="{GOLD}" opacity="0.55" stroke="{RED}" stroke-width="2"/>'
            f'{labels_svg}</svg>')

def coupon_wall(coupons):
    if not coupons:
        return ""
    cells = "".join(
        f'<div class="coupon"><b>{esc(c["name"][:14])}</b><span>¥{esc(c["price"] or "?")}</span><i>{esc((c["expiry"] or "")[:22])}</i></div>'
        for c in coupons[:8])
    return f'<div class="coupons">{cells}</div>'

def page(inner, cls=""):
    return f'<section class="page {cls}"><div class="pin"></div>{inner}</section>'

def build_book():
    profile = load("profile.json")
    details = load_raw("details.json")
    orders = load_raw("order_list.json").get("data", {}).get("list", [])
    if len(orders) < 2:
        raise SystemExit("至少 2 单才能装订成书——先去吃一顿，再回来生成。")
    import fallback as FB
    orig, paid, saved = money_stats(details)
    plan = FB.plan_pages(profile, orders, profile.get("coupons", []), total_saved=saved)
    chs = build_chapters(profile, details, orders)
    acc = profile["account"]
    prizes = profile.get("prizes", [])
    coupons = profile.get("coupons", [])
    first_coupon = plan["hero_coupon"]
    P = persona(profile, orders, details)
    days_since = plan["days_since"]
    gap_avg = plan["gap_avg"]
    sins = FB.confessions(profile, orders, coupons)

    pages = []
    # cover
    pages.append(page(f'''
      <div class="cover-badge">MCD MEMOIR · 第一季</div>
      <h1>麦门人生回忆录</h1>
      <svg class="cover-arches" viewBox="0 0 47 34" width="47" height="34" aria-hidden="true">
        <path d="M 4 30 Q 13.8 -18 23.5 30 Q 33.2 -18 43 30" fill="none" stroke="#DA291C" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <p class="cover-sub">{plan["cover_sub"]}</p>
      <p class="cover-hook">这本书的 <b>{{GRAVE_PAGE}}</b> 页，有一样你扔掉的东西，其实开成了花。</p>
      <div class="cover-meta">{profile["first_order"][:10]} — {profile["last_order"][:10]}</div>
      <div class="flip-hint">
        <svg viewBox="0 0 36 32" width="34" height="30" aria-hidden="true">
          <path d="M 4 5 Q 18 13 32 5 L 32 24 Q 18 32 4 24 Z" fill="#B71C1C"/>
          <path d="M 18 9 L 18 28" stroke="#FFC72C" stroke-width="2" stroke-linecap="round"/>
          <path d="M 9 14 Q 18 19 27 14" stroke="#FFC72C" stroke-width="2" fill="none" stroke-linecap="round"/>
        </svg>
        <span>往下翻</span>
      </div>''', "cover"))
    # opening three questions (hook page, before prologue)
    ti0 = (profile.get("top_items") or [["你的常点", 0]])[0]
    q1 = (f'你把整个麦门人生给了一个{ti0[0].strip()}。这是专一，还是固执？'
          if profile.get("top_item_share", 0) >= 0.99 else
          f'{int(profile.get("top_item_share", 0)*100)}% 的麦门人生，你给了同一个{ti0[0].strip()}。这是专一，还是固执？')
    pages.append(page(f'''
      <div class="kicker">开卷 · 三个问题</div>
      <h2>翻开之前，先回答我</h2>
      <div class="hook-q"><i>①</i><p>{q1}</p></div>
      <div class="hook-q"><i>②</i><p>{plan["questions"]["q2"]}</p></div>
      <div class="hook-q"><i>③</i><p>{plan["questions"]["q3"]}</p></div>
      <p class="foot">三个问题的答案，散落在后面的每一页。先看你的档案 ↓</p>''', "plain"))
    # prologue numbers
    rice_card = ('<div class="stat minor"><b data-n="' + str(profile["rice_bowls"]) + '" data-f="1">0</b><span>碗米饭热量*</span></div>'
                 if plan["show_rice"] else "")
    kcal_foot = (f'* 全部订单热量约 {profile["kcal_total"]} kcal，按一碗米饭 290 kcal 换算（含套餐子项估算）<br>'
                 if plan["show_rice"] else '营养换算暂缺（菜单匹配不到你的商品）<br>')
    span_card = ('<div class="stat major"><b data-n="' + str(profile["span_days"]) + '">0</b><span>陪伴天数</span></div>'
                 if profile.get("span_days") else "")
    pages.append(page(f'''
      <h2>序章 · 你的麦门档案</h2>
      <div class="grid">
        <div class="stat major"><b data-n="{profile["order_count"]}">0</b><span>笔订单</span></div>
        <div class="stat major"><b data-n="{profile["total_pay"]}" data-f="1">0</b><span>总消费(元)</span></div>
        {span_card}
        <div class="stat minor"><b data-n="{profile["store_count"]}">0</b><span>家门店</span></div>
        <div class="stat minor"><b data-n="{profile["item_variety"]}">0</b><span>种商品</span></div>
        {rice_card}
      </div>
      <p class="foot">{kcal_foot}你的人格类型：{profile["person_type"]} · 数据 order-list / query-order / list-nutrition-foods</p>'''))
    # chapters
    for ch in chs:
        img = ""
        if ch["img"]:
            dtag = f'<span class="polaroid-date">{ch.get("date","")}</span>' if ch.get("date") else ""
            img = f'<div class="polaroid"><img class="food" src="{esc(ch["img"])}" alt="">{dtag}</div>'
        combo = f'<div class="combo">{ch["combo"]}</div>' if ch["combo"] else ""
        pages.append(page(f'''
          <div class="kicker">{ch["kicker"]}</div>
          <h2>{ch["title"]}</h2>
          {img}
          <div class="lines">{"<p>".join("<p>"+l+"</p>" for l in ch["lines"])}</div>
          {combo}
          <div class="note">{ch["note"]}</div>'''))
    # biological clock (replaces clock dial)
    pages.append(page(f'''
      <div class="kicker">麦门生物钟</div>
      <h2>你的指针，比地铁还准</h2>
      {clock2_svg(P["median"])}
      <p class="lead">10 单里 {P["hit"]} 单落在你中位点餐时间的 ±90 分钟内。</p>
      {strip_svg(profile["hours"], P["hit"], P["n"])}
      <p class="foot">午间黄金档一柱擎天，其余时段静悄悄——你不是饿了才来，是排班表里写着麦当劳。<br>数据 order-list · createTime</p>''', "plain"))
    # persona report (viral card) — radar degrades when dims too weak
    radar_html = radar_svg(P) if plan["radar_ok"] else ""
    ptitle = plan["persona_title_fallback"] or P["title"]
    pages.append(page(f'''
      <div class="kicker">麦门人格鉴定书</div>
      <div class="cert">
        <p class="cert-line">兹证明该名麦门人，经官方 MCP 数据严格鉴定为——</p>
        <div class="cert-title">{ptitle}</div>
        {radar_html}
        <div class="cert-tags"><span>{P["tag"]}</span><span>中位点餐 {P["median"]}</span><span>忠诚度 {P["loyalty"]}%</span></div>
        <p class="cert-note">麦力值 <b>{P["mpower"]}</b> / 100 · 超越了全国 <b>{min(round(P["mpower"]*1.9),99)}%</b> 的麦门人*</p>
        <div class="seal">{badge_svg("", 56)}</div>
        <p class="foot">* 规则模板计算，仅供娱乐 · 四维：规律{P["regularity"]} 自律{P["selfdisc"]} 忠诚{P["loyalty"]} 专一{P["focus"]}<br>数据 order-list / query-order</p>
      </div>''', "gold"))
    # maimen literature — rerollable pool
    lit_quotes = "".join(
        f'<div class="lit-quote{i}"><p>{q}</p><p class="lit-note">{note}</p></div>'
        for i, (q, note) in enumerate(LIT_POOL(profile, saved, P["median"])))
    pages.append(page(f'''
      <div class="lit">
        {lit_quotes}
        <button class="lit-reroll" onclick="rerollLit()" aria-label="换一句">⟳</button>
        <div class="lit-motto">麦门。</div>
        <p class="foot">—— 麦门文学 · 点 ⟳ 换一句 · 每句都藏着你的真实数据</p>
      </div>''', "lit"))
    # missing person (viral hook) — three narrative modes
    mm = plan["missing_mode"]
    if mm == "today":
        pages.append(page(f'''
          <div class="kicker">寻人启事</div>
          <h2>今天来过</h2>
          <p class="lead">书还没合上，你已经翻开了下一章。<br>今天这一单，会成为下一次回忆录的第 {profile["order_count"] + 1} 页。</p>
          <p class="missing-line">卡包里 {len(coupons)} 张券和 {acc.get("available", 0)} 分积分，随时待命。</p>
          <p class="foot">数据 order-list · query-my-coupons / query-my-account</p>''', "warn"))
    elif mm == "first_time":
        pages.append(page(f'''
          <div class="kicker">寻人启事</div>
          <h2>麦门失踪人口</h2>
          <div class="missing">
            <b class="count" data-n="{days_since}">0</b><span>天</span>
          </div>
          <p class="lead">你已经 <b>{days_since}</b> 天没有出现在麦当劳了。</p>
          <p class="lead dim">这是你的第一次失踪。历史平均？你还不需要它。</p>
          <p class="missing-line">卡包里 {len(coupons)} 张券和 {acc.get("available", 0)} 分积分，都在等你回来翻这本书。</p>
          <p class="foot">数据 order-list（最后一单 {plan["last_day"]}）· query-my-coupons / query-my-account</p>''', "warn"))
    else:
        pages.append(page(f'''
          <div class="kicker">寻人启事</div>
          <h2>麦门失踪人口</h2>
          <div class="missing">
            <b class="count" data-n="{days_since}">0</b><span>天</span>
          </div>
          <p class="lead">你已经 <b>{days_since}</b> 天没有出现在麦当劳了。</p>
          <p class="lead dim">而你的历史平均，每 <b>{gap_avg}</b> 天就要见一次麦门。<br>现在这个间隔，是平时的 <b>{round(days_since/max(gap_avg,0.1),1)}</b> 倍。</p>
          <p class="missing-line">卡包里 {len(coupons)} 张券和 {acc.get("available", 0)} 分积分，都在等你回来翻这本书。</p>
          <p class="foot">数据 order-list（最后一单 {plan["last_day"]}）· query-my-coupons / query-my-account</p>''', "warn"))
    # balance (true ratio) — price-hero mode when never saved
    if plan["balance_mode"] == "normal":
        saved_pct = round(min(saved / max(orig, 0.1) * 100, 100), 1)
        pages.append(page(f'''
          <h2>汉堡天平</h2>
          <p class="lead">如果麦当劳按原价收钱，你要花：</p>
          <div class="bal">
            <div class="bal-row"><span>原价人生</span>
              <div class="bar orig" style="--w:100%"><i class="gap" style="--gap:{saved_pct}%"></i><b>¥{fmt_money(orig)}</b></div>
            </div>
            <div class="bal-row"><span>麦门实付</span>
              <div class="bar paid" style="--w:{round(paid/max(orig,0.1)*100,1)}%"><b>¥{fmt_money(paid)}</b></div>
            </div>
          </div>
          <p class="big-save">省下 <b class="count" data-n="{saved}" data-f="1">0</b> 元 <span class="save-pct">（约 {saved_pct}%）</span></p>
          <p class="foot">两条按真实比例绘制 · 金色段 = 省下的部分 · 数据 query-order · totalDiscountAmount 合计</p>''', "plain"))
    else:
        pages.append(page(f'''
          <h2>汉堡天平</h2>
          <div class="bal">
            <div class="bal-row"><span>原价人生</span>
              <div class="bar orig" style="--w:100%"><b>¥{fmt_money(orig)}</b></div>
            </div>
            <div class="bal-row"><span>麦门实付</span>
              <div class="bar paid" style="--w:{round(paid/max(orig,0.1)*100,1)}%"><b>¥{fmt_money(paid)}</b></div>
            </div>
          </div>
          <p class="lead" style="margin-top:20px">你目前按原价吃着每一单。<br>天平的金色部分，等你用第一张券来点亮。</p>
          <p class="foot">数据 query-order · totalDiscountAmount 合计</p>''', "plain"))
    # points garden (replaces graveyard; ACNH style, water-able)
    flower_slots = []
    for o in sorted([o for o in orders if o.get("createTime")], key=lambda x: x["createTime"]):
        d = details.get(o.get("orderId"), {}) or {}
        disc = float(d.get("totalDiscountAmount") or 0)
        if disc > 0:
            flower_slots.append({"date": o["createTime"][:10], "pct": min(disc / 40.0, 1.0)})
    if not flower_slots:
        flower_slots = [{"date": o["createTime"][:10], "pct": 0.25} for o in orders[:6]]
    max_pct = max(f["pct"] for f in flower_slots) or 0.25
    for f in flower_slots:
        f["pct"] = max(f["pct"] / max_pct, 0.3)
    if plan["garden_mode"] == "normal":
        pages.append(page(f'''
          <div class="kicker">积分花园 · GARDEN</div>
          <h2>你的积分，开成了花</h2>
          <p class="lead">{acc.get("expired", 0)} 分积分离开了账户，但没有消失——<br>它们和你的每一笔优惠一起，种成了下面这片花园。</p>
          <div class="garden-scene">{garden_svg(flower_slots)}</div>
          <p class="garden-hidden" style="opacity:0;font-weight:800;color:var(--red);text-align:center;transition:opacity .6s">看，浪费也能开花。</p>
          <p class="foot bright">当前可用 {acc.get("available", 0)} 分 · 过期率 {acc.get("expire_rate", 0)}%<br>数据 query-my-account / query-order · 别让新的积分再凋谢，常回来浇浇</p>''', "plain"))
    else:
        pages.append(page(f'''
          <div class="kicker">积分花园 · 温室</div>
          <h2>积分温室</h2>
          <p class="lead">你的积分一朵都没谢——全在温室里养着。<br>当前 {acc.get("available", 0)} 分，每一分都在等你兑现。</p>
          <div class="garden-scene">{garden_svg(flower_slots)}</div>
          <p class="foot bright">累计 {acc.get("accumulative", 0)} 分 · 过期率 0%<br>数据 query-my-account · 保持这份谨慎，它很贵</p>''', "plain"))
    # confessions room (new page, right after graveyard)
    if plan["confession_enabled"] and sins:
        saved_for_absolve = fmt_money(plan["saved"])
        sin_cards = "".join(
            f'''<div class="sin-card" style="--i:{i}">
              <span class="sin-no">第 {i+1} 宗罪</span>
              <b class="sin-name">{esc(s["name"])}</b>
              <p class="sin-text">{s["text"]}</p>
              <span class="sin-src">{s["source"]}</span>
            </div>''' for i, s in enumerate(sins))
        absolve_card = f'''
          <div class="absolve-card">
            <b class="sin-name">唯一的善行</b>
            <p class="sin-text">你用券省下了 ¥{saved_for_absolve}。麦门看在钱的份上，赦免以上一切罪行。</p>
            <div class="seal-gold">已赦免</div>
            <span class="sin-src">数据 query-order · totalDiscountAmount</span>
          </div>''' if plan["saved"] > 0 else ""
        motto = ("以上罪行，麦门一律赦免。<br>—— 愿你继续做快乐的老实人。" if plan["saved"] > 0
                 else "以上罪行，记在下一单的账上。")
        pages.append(page(f'''
          <div class="kicker">忏悔室 · CONFESSION</div>
          <h2>麦门忏悔室</h2>
          {sin_cards}
          {absolve_card}
          <p class="absolve-motto">{motto}</p>''', "plain"))
    # badges (+ hidden collectible progress)
    if prizes:
        progress = round(len(prizes) / 24 * 100, 1)
        pages.append(page(f'''
          <div class="kicker">勋章收藏 · SEASON 1</div>
          <h2>节气勋章墙</h2>
          <p class="lead">积分抽奖抽出的 {len(prizes)} 枚节气金币，从春分到白露：</p>
          {badge_wall(prizes)}
          <div class="coin-progress"><div class="cp-fill" style="--p:{progress}%"></div><span class="cp-label">{len(prizes)} / 24 节气</span></div>
          <div class="ghost-coin-wrap">
            <svg viewBox="0 0 100 100" width="56" height="56" aria-hidden="true">
              <circle cx="50" cy="50" r="46" fill="none" stroke="#C99700" stroke-width="2.5" stroke-dasharray="4 4"/>
              <text x="50" y="62" text-anchor="middle" font-size="30" font-weight="800" fill="#C99700" opacity=".7">?</text>
            </svg>
            <span>隐藏款 · 麦门全知者</span>
          </div>
          <p class="foot">距离隐藏款还有 {24 - len(prizes)} 个节气 · 在 WorkBuddy 里对 AI 说「帮我抽一次节气勋章」继续集齐<br>数据 query-my-prizes</p>'''))
    # final CTA — "next chapter" (hero coupon = latest expiry; empty-coupon fallback)
    hero_until = ""
    if first_coupon:
        ds = re.findall(r"\d{4}-\d{2}-\d{2}", first_coupon.get("expiry") or "")
        hero_until = max(ds) if ds else ""
    cta_coupon = ""
    if first_coupon:
        cta_coupon = f'''<div class="cta-coupon">
          <span class="cc-tag">下一章 · 入场券</span>
          <span class="cc-name">{esc(first_coupon["name"])}</span>
          <span class="cc-price">¥{esc(first_coupon["price"] or "?")}</span>
          <span class="cc-exp">有效期至 {esc(hero_until) if hero_until else esc((first_coupon["expiry"] or "")[:26])}</span>
        </div>'''
    epilogue_lead = ("书的最后一页翻过去了，麦门的故事还没有写完。<br>卡包里还有 "
                     + str(len(coupons)) + " 张券，都是提前埋好的伏笔——比如这一张："
                     if plan["epilogue_mode"] == "normal" else
                     "书的最后一页翻过去了，麦门的故事还没有写完。<br>卡包空空——下一章的第一张券，等你去领。")
    pages.append(page(f'''
      <div class="stamp-tbc">未完待续</div>
      <div class="kicker">后记 · NEXT CHAPTER</div>
      <h2>下一章，由你执笔</h2>
      <p class="lead">{epilogue_lead}</p>
      {cta_coupon}
      <p class="foot">在 WorkBuddy 里对 AI 说一句话，让下一章今天开演<br>数据 query-my-coupons · 到手信息以麦当劳 APP 为准</p>''', "cta"))
    # colophon
    pages.append(page(f'''
      <h2>关于这本书</h2>
      <p class="about">这本书里的每一个数字，都来自麦当劳官方 MCP（mcp.mcd.cn）的实时查询：
      order-list · query-order · query-my-account · query-my-coupons · query-my-prizes · list-nutrition-foods。
      叙事由规则模板生成，所有金额、积分、日期均为真实账户数据，未经任何修改。</p>
      <p class="about">生成时间：{profile.get("generated_at","")}<br>
      本项目为参赛 demo，与麦当劳官方无关，仅供学习交流。</p>
      <div class="colophon-line"></div>
      <div class="logo-mark">M</div>
      <div class="made-with">MADE WITH MCD MCP</div>''', "plain colophon"))

    body = "\n".join(pages)
    # backfill cover hook page number (graveyard page, 1-based)
    garden_idx = next((i for i, p in enumerate(pages) if "积分花园" in p), 0)
    body = body.replace("{GRAVE_PAGE}", str(garden_idx + 1))
    # bad-text hard validation — never ship a broken book
    _text = re.sub(r"<[^>]+>", " ", body)
    for bad in BAD_TEXTS:
        if bad in _text:
            raise SystemExit(f"bad-text check failed: '{bad}' in book.html")
    html_doc = TEMPLATE.replace("/*PAGES*/", body)
    out = os.path.join(HERE, "book.html")
    with open(out, "w") as f:
        f.write(html_doc)
    print(f"✓ book.html written ({len(html_doc)//1024} KB, {len(pages)} pages)")

BAD_TEXTS = ["None", "nan", "undefined", "0 倍", "0 天没有", "装订成  天", "的出现了", "{", "}"]

def LIT_POOL(profile, saved, median="--:--"):
    """10 rerollable quotes; notes bound to real data, filtered when fields empty."""
    n = profile.get("order_count", 0)
    span = profile.get("span_days") or 0
    acc = profile.get("account", {})
    ti = profile.get("top_items") or [["你常点的那一款", 0]]
    pool = [
        ("人生没有白走的路，<br>只有白点的薯条。", f"第 {n} 单 · 共 ¥{fmt_money(profile.get('total_pay', 0))}"),
        ("你省下的每一分钱，<br>都是麦门写给你的情书。", f"累计省下 ¥{fmt_money(saved)}" if saved else "省钱的章节正在路上"),
        ("别人记账，你记的是日子。", f"{span} 天 · {n} 个章节" if span else f"{n} 个章节"),
        ("有些忠诚不需要理由，<br>比如你和中薯条。", f"「{ti[0][0].strip()}」× {ti[0][1]}"),
        ("十二点的钟声不为谁而鸣，<br>除了你的胃。", f"中位赴约 {median}"),
        ("积分会过期，爱不会。", f"可用 {acc.get('available', 0)} 分，别再弄丢"),
        ("巨无霸是永恒的，<br>减脂是间歇的。", f"≈{profile.get('rice_bowls', 0)} 碗米饭，值了" if profile.get('kcal_total') else "热量账本下季开放"),
        ("门一直在那儿，<br>你随时可以推。", f"{profile.get('store_count', 1)} 家门店的灯都亮着"),
        ("麦门不看朋友圈，<br>但麦门记得你每一单。", f"第 {n} 单，永久收藏"),
        ("快乐有很多种，<br>你的这一种是金黄色的。", "季节限定 · SEASON 1"),
    ]
    return pool

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>麦门人生回忆录 · 第一季</title>
<style>
:root { --gold:#FFC72C; --red:#DA291C; --cream:#FFF8E7; --ink:#2B1D0E; --muted:#8A7B60; }
* { margin:0; padding:0; box-sizing:border-box; }
html { scroll-snap-type:y mandatory; scroll-behavior:smooth; }
body { font-family:-apple-system,'PingFang SC','Noto Sans SC',sans-serif; background:#E8E0CC; color:var(--ink); }
.page { min-height:100vh; scroll-snap-align:start; display:flex; flex-direction:column; align-items:center; justify-content:center;
  padding:8vh 28px 10vh; background:var(--cream); position:relative; overflow:hidden; }
.page.dark { background:#181410; color:#F5EDD8; }
.page.cover { background:var(--gold); }
.pin { position:absolute; top:24px; left:50%; transform:translateX(-50%); width:56px; height:8px; border-radius:4px; background:rgba(43,29,14,.14); }
.page.dark .pin { background:rgba(245,237,216,.18); }
h1 { font-size:clamp(34px,8vw,54px); font-weight:800; letter-spacing:2px; }
h2 { font-size:clamp(24px,5.4vw,32px); font-weight:800; margin-bottom:18px; letter-spacing:1px; }
.cover-badge { background:var(--red); color:#fff; font-size:12px; letter-spacing:4px; padding:7px 16px; border-radius:20px; margin-bottom:22px; }
.cover-sub { font-size:clamp(15px,3.8vw,19px); margin:18px 0 26px; line-height:1.9; opacity:.85; text-align:center; }
.cover-meta { font-size:13px; opacity:.65; letter-spacing:2px; }
.flip-hint { position:absolute; bottom:4vh; font-size:13px; opacity:.55; animation:bob 1.6s infinite ease-in-out; }
@keyframes bob { 0%,100%{transform:translateY(0)} 50%{transform:translateY(6px)} }
.lead { font-size:15px; line-height:1.9; opacity:.8; text-align:center; margin-bottom:8px; }
.grid { display:grid; grid-template-columns:repeat(3,minmax(86px,120px)); gap:14px; margin:10px 0 18px; }
.stat { background:#fff; border:1px solid rgba(43,29,14,.1); border-radius:14px; padding:14px 6px; text-align:center; }
.stat b { display:block; font-size:clamp(22px,5vw,30px); font-weight:800; color:var(--red); }
.stat span { font-size:12px; color:var(--muted); }
.kicker { font-size:12px; letter-spacing:3px; color:var(--red); font-weight:700; margin-bottom:10px; }
.lines p { font-size:clamp(14px,3.6vw,16.5px); line-height:2; margin:4px 0; text-align:center; }
.food { width:min(58vw,240px); border-radius:16px; margin:6px 0 14px; box-shadow:0 10px 30px rgba(43,29,14,.18); background:#fff; }
.combo { margin-top:12px; font-size:13px; color:var(--muted); background:rgba(255,199,44,.35); padding:8px 14px; border-radius:10px; max-width:340px; text-align:center; }
.note { margin-top:16px; font-size:11px; color:var(--muted); letter-spacing:.5px; }
.big-save { font-size:clamp(20px,5vw,28px); margin-top:22px; }
.big-save b { color:var(--red); font-size:1.4em; font-weight:800; }
.bal { width:min(84vw,360px); margin-top:14px; }
.bal-row { margin:14px 0; }
.bal-row span { font-size:13px; color:var(--muted); }
.bar { height:34px; border-radius:10px; width:0; transition:width 1.2s cubic-bezier(.2,.7,.2,1); position:relative; margin-top:6px; }
.bar b { position:absolute; right:10px; top:50%; transform:translateY(-50%); font-size:14px; font-weight:700; }
.bar.orig { background:#D8CDB4; max-width:100%; }
.bar.paid { background:var(--red); }
.bar.paid b { color:#fff; }
.on .bar { width:calc(var(--w) + 60px); }
.grave { text-align:center; margin:8px 0; }
.grave b { font-size:clamp(52px,14vw,88px); font-weight:800; color:var(--gold); }
.grave span { font-size:20px; opacity:.7; margin-left:6px; }
.grave-line { font-size:16px; opacity:.75; margin:8px 0 20px; }
.grave-line2 { font-size:15px; line-height:2; text-align:center; opacity:.9; }
.grave-line2 b { color:var(--gold); font-size:1.25em; }
.foot { font-size:11.5px; color:var(--muted); text-align:center; line-height:1.9; margin-top:20px; }
.bright { color:#B7A98A; }
.badges { display:flex; flex-wrap:wrap; gap:12px; justify-content:center; max-width:420px; margin-top:12px; }
.tray { background:#F5EBCF; border-radius:20px; padding:22px 26px 16px; box-shadow:inset 0 2px 10px rgba(43,29,14,.08); max-width:420px; }
.coins { display:flex; flex-wrap:wrap; gap:16px 14px; justify-content:center; }
.coin-wrap { animation:coin-in .5s cubic-bezier(.2,.9,.3,1.4) backwards; animation-delay:calc(var(--i) * 60ms); }
.coin-wrap svg { filter:drop-shadow(0 3px 4px rgba(43,29,14,.22)); }
@keyframes coin-in { from { transform:scale(.55) rotate(-8deg); opacity:0; } to { transform:scale(1) rotate(0); opacity:1; } }
.coupons { display:grid; grid-template-columns:repeat(2,minmax(140px,190px)); gap:10px; margin-top:14px; width:100%; max-width:420px; }
.coupon { background:#fff; border:1px dashed #D8C8A2; border-radius:10px; padding:10px 12px; display:flex; flex-direction:column; gap:2px; }
.coupon b { font-size:12.5px; line-height:1.4; }
.coupon span { color:var(--red); font-weight:800; font-size:15px; }
.coupon i { font-size:10px; color:var(--muted); font-style:normal; }
.cta-coupon { background:#fff; border-radius:16px; padding:20px 26px; margin:16px 0; display:flex; flex-direction:column; gap:6px; align-items:center;
  box-shadow:0 14px 40px rgba(218,41,28,.18); border-top:6px solid var(--red); max-width:340px; }
.cc-name { font-size:17px; font-weight:700; }
.cc-price { font-size:26px; font-weight:800; color:var(--red); }
.cc-exp { font-size:11px; color:var(--muted); }
.about { max-width:420px; font-size:13px; line-height:2.1; opacity:.8; text-align:center; margin-bottom:14px; }
.logo-mark { width:64px; height:64px; border-radius:50%; background:var(--gold); color:var(--red); font-size:40px; font-weight:900;
  display:flex; align-items:center; justify-content:center; margin-top:10px; font-family:Georgia,serif; }
.page.gold { background:linear-gradient(180deg,#FFE08A,#FFC72C); }
.cert { background:#fff; border-radius:22px; padding:26px 26px 18px; max-width:400px; width:88vw;
  box-shadow:0 18px 50px rgba(43,29,14,.22); text-align:center; }
.cert-line { font-size:13px; color:var(--muted); margin-bottom:10px; }
.cert-title { font-size:clamp(26px,7vw,34px); font-weight:900; color:var(--red); letter-spacing:2px; margin-bottom:6px; }
.cert-tags { display:flex; gap:8px; justify-content:center; flex-wrap:wrap; margin:12px 0 8px; }
.cert-tags span { background:rgba(255,199,44,.4); border-radius:14px; padding:5px 12px; font-size:12px; font-weight:700; }
.cert-note { font-size:14px; margin-top:6px; }
.cert-note b { color:var(--red); font-size:1.3em; }
.page.lit { background:var(--red); color:#FFF8E7; }
.lit p { font-size:clamp(26px,7vw,40px); font-weight:900; line-height:1.7; text-align:center; letter-spacing:2px; }
.lit-small { font-size:clamp(14px,3.8vw,17px) !important; font-weight:400 !important; opacity:.85; margin-top:20px; letter-spacing:1px; }
.lit-motto { font-size:clamp(34px,9vw,48px) !important; margin-top:26px; letter-spacing:6px; }
.lit .foot { color:rgba(255,248,231,.72); }
.polaroid { background:#fff; padding:10px 10px 6px; border-radius:6px; box-shadow:0 8px 24px rgba(43,29,14,.16);
  transform:rotate(-1.2deg); margin:6px 0 14px; position:relative; }
.polaroid .food { margin:0; box-shadow:none; display:block; }
.polaroid-date { position:absolute; left:14px; bottom:8px; font-size:10.5px; color:#B4A78F; letter-spacing:1px; }
.seal { position:absolute; right:18px; bottom:16px; opacity:.16; transform:rotate(-12deg); pointer-events:none; }
.cert { position:relative; }
.stat.major { border-top:4px solid var(--gold); }
.stat.major b { color:var(--red); }
.stat.minor { background:transparent; border:none; box-shadow:none; }
.stat.minor b { color:var(--ink); opacity:.55; font-size:clamp(18px,4vw,24px); }
.stat.minor span { opacity:.7; }
.bar.orig { background:#EBDDC0; max-width:100%; }
.bar.orig .gap { position:absolute; right:0; top:0; height:100%; width:var(--gap);
  background:repeating-linear-gradient(135deg, #C99700 0 6px, #B8860B 6px 12px); border-radius:0 10px 10px 0; }
.save-pct { font-size:.55em; opacity:.6; font-weight:400; }
h1 { font-family:Georgia,'Songti SC','Noto Serif SC',serif; }
.cover-arches { margin:14px 0 4px; }
.flip-hint { display:flex; flex-direction:column; align-items:center; gap:6px; }
.flip-hint span { font-size:13px; opacity:.75; letter-spacing:2px; }
.cta-coupon { position:relative; overflow:hidden; padding-left:40px !important; }
.cta-coupon::before { content:''; position:absolute; left:14px; top:0; bottom:0; width:2px;
  background:radial-gradient(circle at 50% 9px, transparent 5px, var(--red) 5.5px, var(--red) 100%);
  background-size:2px 22px; background-repeat:repeat-y; }
.tombs { display:flex; gap:10px; align-items:flex-end; justify-content:center; margin:6px 0 2px; }
.tomb { opacity:.9; }
.tomb-more { color:#C99700; font-size:18px; font-weight:700; margin-left:-2px; line-height:1; }
.colophon-line { width:120px; height:1px; background:#C99700; margin:14px 0 4px; opacity:.6; }
.made-with { font-size:10px; letter-spacing:4px; color:var(--ink-2, #8A7B60); margin-top:8px; opacity:.75; }
.stamp-tbc { position:absolute; top:7vh; right:8vw; border:3px solid var(--red); color:var(--red);
  font-size:clamp(15px,4vw,19px); font-weight:800; letter-spacing:5px; padding:8px 14px;
  border-radius:8px; transform:rotate(8deg); opacity:.82; }
.cover-hook { margin-top:14px; font-size:clamp(13px,3.4vw,15px); color:var(--red); font-weight:700; letter-spacing:1px; }
.cover-hook b { border-bottom:2px solid var(--red); padding:0 2px; }
.hook-q { display:flex; align-items:flex-start; gap:16px; max-width:400px; width:88vw;
  padding:18px 0; border-bottom:1px solid var(--line, #EBDDC0); }
.hook-q:last-of-type { border-bottom:none; }
.hook-q i { font-family:Georgia,'Songti SC',serif; font-style:normal; font-size:34px; font-weight:800; color:var(--gold); line-height:1; }
.hook-q p { font-size:clamp(14px,3.7vw,16px); line-height:1.9; margin:0; text-align:left; }
.sin-card { background:var(--red); color:#FFF8E7; border-radius:14px; padding:18px 20px 14px;
  width:min(86vw,400px); margin:6px 0; position:relative; text-align:left;
  animation:fade-up .5s ease backwards; animation-delay:calc(var(--i) * 70ms); }
@keyframes fade-up { from { opacity:0; transform:translateY(12px); } }
.sin-no { position:absolute; left:0; top:16px; writing-mode:vertical-lr; letter-spacing:3px;
  font-size:10px; color:var(--gold); font-weight:700; }
.sin-card { padding-left:34px; }
.sin-name { display:block; font-size:17px; font-weight:800; margin-bottom:6px; color:#FFE08A; }
.sin-card .sin-name { color:#FFE08A; }
.sin-text { font-size:14px; line-height:1.9; margin:0 0 8px; }
.sin-src { font-size:10.5px; opacity:.65; }
.absolve-card { background:var(--cream); border:2px solid var(--gold); border-radius:14px;
  padding:18px 20px 14px; width:min(86vw,400px); margin:12px 0 4px; position:relative; text-align:left; }
.absolve-card .sin-name { color:var(--red); }
.absolve-card .sin-text { color:var(--ink); }
.seal-gold { position:absolute; right:14px; bottom:34px; border:3px solid var(--gold); color:var(--gold);
  font-weight:800; font-size:15px; letter-spacing:3px; padding:5px 10px; border-radius:6px;
  transform:rotate(-10deg); opacity:.85; }
.absolve-motto { font-size:clamp(15px,4vw,18px); font-weight:800; text-align:center;
  line-height:1.9; margin-top:16px; color:var(--red); }
.lit-quote { display:none; }
.lit-quote.on { display:block; animation:lit-fade .25s ease; }
@keyframes lit-fade { from { opacity:0; transform:translateY(8px); } }
.lit-quote p { font-size:clamp(26px,7vw,40px); font-weight:900; line-height:1.7; text-align:center; letter-spacing:2px; margin:0; }
.lit-note { font-size:13px !important; font-weight:400 !important; opacity:.8; letter-spacing:1px; margin-top:14px !important; }
.lit-reroll { position:absolute; right:8vw; bottom:20vh; width:44px; height:44px; border-radius:50%;
  background:var(--gold); color:var(--ink); border:none; font-size:20px; font-weight:800; cursor:pointer;
  transition:transform .2s; box-shadow:0 4px 14px rgba(43,29,14,.3); }
.lit-reroll:hover { transform:rotate(45deg); }
.lit-reroll:active { transform:scale(.9); }
.coin-progress { width:min(84vw,360px); height:12px; border-radius:6px; background:#EBDDC0;
  position:relative; margin:18px 0 6px; overflow:hidden; }
.cp-fill { position:absolute; left:0; top:0; bottom:0; width:var(--p); background:var(--gold); border-radius:6px;
  transition:width 1.2s cubic-bezier(.2,.7,.2,1); }
.page.on .cp-fill { width:var(--p); }
.cp-label { position:absolute; right:8px; top:50%; transform:translateY(-50%);
  font-size:10.5px; font-weight:700; color:var(--ink); }
.ghost-coin-wrap { display:flex; align-items:center; gap:10px; margin-top:8px; opacity:.75; }
.ghost-coin-wrap span { font-size:12px; color:#6E5F45; font-weight:700; }
.cc-tag { background:var(--gold); color:var(--ink); font-size:11px; font-weight:800; letter-spacing:2px;
  padding:4px 12px; border-radius:12px; }
.cta-coupon { align-items:center; gap:8px; }
.page.warn { background:#2B1D0E; color:#FFF8E7; }
.missing { text-align:center; margin:10px 0; }
.missing b { font-size:clamp(56px,15vw,92px); font-weight:900; color:var(--gold); }
.missing span { font-size:20px; opacity:.7; margin-left:6px; }
.missing-line { font-size:15px; margin-top:18px; color:var(--gold); font-weight:700; text-align:center; }
.lead.dim { opacity:.6; font-size:14px; }
.missing .lead b, .lead b { color:var(--red); }
.page.warn .lead b { color:var(--gold); }
</style>
</head>
<body>
/*PAGES*/
<script>
// count-up
const io = new IntersectionObserver(es => es.forEach(e => {
  if (!e.isIntersecting) return;
  e.target.classList.add('on');
  e.target.querySelectorAll('[data-n]').forEach(el => {
    if (el.dataset.done) return; el.dataset.done = 1;
    const target = parseFloat(el.dataset.n), f = parseInt(el.dataset.f || 0);
    const t0 = performance.now(), dur = 1100;
    const tick = t => { const p = Math.min((t - t0) / dur, 1), v = target * (1 - Math.pow(1 - p, 3));
      el.textContent = f ? v.toFixed(1) : Math.round(v).toLocaleString('zh-CN');
      if (p < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
}), { threshold: .35 });
document.querySelectorAll('.page').forEach(p => io.observe(p));
// literature reroll
const litQuoteEls = document.querySelectorAll('.lit-quote');
let litIdx = Math.floor(Math.random() * litQuoteEls.length);
function showLit(i) { litQuoteEls.forEach((el, j) => el.classList.toggle('on', j === i)); }
if (litQuoteEls.length) { showLit(litIdx); }
function rerollLit() {
  if (!litQuoteEls.length) return;
  litIdx = (litIdx + 1 + Math.floor(Math.random() * (litQuoteEls.length - 1))) % litQuoteEls.length;
  showLit(litIdx);
}
</script>
</body>
</html>"""

if __name__ == "__main__":
    build_book()