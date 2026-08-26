# -*- coding: utf-8 -*-
"""重放结果 A/B 汇总"""
import json, io, collections

d = json.load(io.open(r"_replay_adj_out.json", encoding="utf-8"))

def leg_stats(matches, mode, ev_min=None, only_mkt=None):
    n = 0; win = lose = push = half = 0; pnl = 0.0
    for m in matches:
        r = m.get(mode) or {}
        if r.get("error"):
            continue
        for b in r.get("bets") or []:
            if ev_min is not None and (b.get("ev") is None or b["ev"] < ev_min):
                continue
            if only_mkt and not b["name"].startswith(only_mkt):
                continue
            if b.get("result") == "unknown":
                continue
            n += 1
            pnl += b.get("pnl") or 0.0
            res = b.get("result")
            if res == "win": win += 1
            elif res == "lose": lose += 1
            elif res == "push": push += 1
            elif res == "half": half += 1
    hit = (win + 0.5 * half) / (win + lose + half) if (win + lose + half) else None
    roi = pnl / n if n else None
    return {"n": n, "win": win, "lose": lose, "push": push, "half": half,
            "hit": round(hit * 100, 1) if hit is not None else None,
            "roi": round(roi * 100, 1) if roi is not None else None}

def dir_stats(matches, mode):
    n = 0; win = lose = push = half = 0; pnl = 0.0
    for m in matches:
        r = m.get(mode) or {}
        if r.get("error"):
            continue
        dn = r.get("direction")
        if not dn:
            continue
        leg = next((b for b in r.get("bets") or [] if b["name"] == dn), None)
        if not leg or leg.get("result") == "unknown":
            continue
        n += 1
        pnl += leg.get("pnl") or 0.0
        res = leg.get("result")
        if res == "win": win += 1
        elif res == "lose": lose += 1
        elif res == "push": push += 1
        elif res == "half": half += 1
    hit = (win + 0.5 * half) / (win + lose + half) if (win + lose + half) else None
    roi = pnl / n if n else None
    return {"n": n, "win": win, "lose": lose, "push": push, "half": half,
            "hit": round(hit * 100, 1) if hit is not None else None,
            "roi": round(roi * 100, 1) if roi is not None else None}

def ou_pick(matches, mode):
    """每场模型对2.5大小球的倾向与命中"""
    over_n = over_w = under_n = under_w = 0
    for m in matches:
        r = m.get(mode) or {}
        if r.get("error"):
            continue
        ob = next((b for b in r.get("bets") or [] if b["name"].startswith("大2.5")), None)
        ub = next((b for b in r.get("bets") or [] if b["name"].startswith("小2.5")), None)
        tot = m["hg"] + m["ag"]
        if ob and ub:
            if ob["prob"] >= ub["prob"]:
                over_n += 1
                if tot > 2.5: over_w += 1
            else:
                under_n += 1
                if tot < 2.5: under_w += 1
    return {"over_pick": over_n, "over_hit": over_w, "under_pick": under_n, "under_hit": under_w}

def flips(matches):
    f = 0; total = 0; det = []
    for m in matches:
        od = (m.get("old") or {}).get("direction")
        nd = (m.get("new") or {}).get("direction")
        if od and nd:
            total += 1
            if od != nd:
                f += 1
                det.append((m["league"], m["home"], m["away"], od, nd, "%d-%d" % (m["hg"], m["ag"])))
    return f, total, det

leagues = ["中超", "葡超", "英冠", "意甲", "美职", "阿甲", "法甲", "法乙", "瑞超", "巴甲", "英乙", "J1", "荷甲", "比甲", "西乙", "英超", "西甲", "土超"]
print("== 总览: 方向命中率 / ROI ==")
print("%-4s | %-6s | %-6s | %-6s | %-6s" % ("联赛", "旧n", "旧命中", "新n", "新命中"))
for lg in leagues:
    ms = [m for m in d if m["league"] == lg]
    if not ms: continue
    o = dir_stats(ms, "old"); n = dir_stats(ms, "new")
    if o["n"] or n["n"]:
        print("%-4s | %-6d | %-6s | %-6d | %-6s" % (lg, o["n"], str(o["hit"]), n["n"], str(n["hit"])))

print()
print("== EV>=5% 腿 ROI (批次门槛) ==")
print("%-4s | %-5s | %-8s | %-5s | %-8s" % ("联赛", "旧n", "旧ROI", "新n", "新ROI"))
for lg in leagues:
    ms = [m for m in d if m["league"] == lg]
    if not ms: continue
    o = leg_stats(ms, "old", ev_min=0.05); n = leg_stats(ms, "new", ev_min=0.05)
    if o["n"] or n["n"]:
        print("%-4s | %-5d | %-8s | %-5d | %-8s" % (lg, o["n"], str(o["roi"]), n["n"], str(n["roi"])))

print()
print("== EV>=20% 腿 ROI ==")
print("%-4s | %-5s | %-8s | %-5s | %-8s" % ("联赛", "旧n", "旧ROI", "新n", "新ROI"))
for lg in leagues:
    ms = [m for m in d if m["league"] == lg]
    if not ms: continue
    o = leg_stats(ms, "old", ev_min=0.20); n = leg_stats(ms, "new", ev_min=0.20)
    if o["n"] or n["n"]:
        print("%-4s | %-5d | %-8s | %-5d | %-8s" % (lg, o["n"], str(o["roi"]), n["n"], str(n["roi"])))

print()
print("== 全部腿(不计EV门槛) 汇总 ==")
for mode in ("old", "new"):
    s = leg_stats(d, mode)
    ds = dir_stats(d, mode)
    ou = ou_pick(d, mode)
    print(mode, "| legs:", s, "| dir:", ds, "| OU:", ou)

f, total, det = flips(d)
print()
print("方向翻转: %d/%d" % (f, total))
for x in det[:40]:
    print("  ", x)
