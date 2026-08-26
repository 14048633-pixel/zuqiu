# -*- coding: utf-8 -*-
"""37场完整方向报告 v2: 1X2(EV) / 大小球2.5(扫描校准)+1.5/3.5(模型参考) / 让球 / 比分TOP / 双胜"""
import json, io, os, glob, csv, math, re, sys
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
from prob_calibration import dc_score_grid

def handicap_cover_prob(grid, hdp):
    def _p(cond):
        return sum(grid[i][j] for i in range(9) for j in range(9) if cond(i, j))
    if abs(abs(hdp) - round(abs(hdp))) < 0.01:
        push = _p(lambda i, j: abs((i - j) + hdp) < 0.01)
        return _p(lambda i, j: (i - j) + hdp > 0) + push * 0.5
    return _p(lambda i, j: (i - j) + hdp > 0)

def norm(s):
    s = (s or "").lower().replace("é","e").replace("è","e").replace("ö","o").replace("ø","o").replace("ü","u").replace("ł","l").replace("ą","a").replace("ć","c").replace("ę","e").replace("ś","s").replace("ż","z").replace("ź","z").replace("ń","n").replace("æ","ae").replace("&"," ").replace("."," ").replace("'"," ")
    return " ".join(s.split())

scan_files = sorted(glob.glob(os.path.join(ROOT, "analysis_records", "scans", "scan_window_*.json")))
d = json.load(io.open(scan_files[-1], encoding="utf-8"))
ms = [m for m in d["matches"] if m["league"] in ("欧联","欧协联") or (m["league"]=="西甲" and m["ct"].startswith("08-21"))]
merged = {}
for m in ms:
    key = ("Rayo","Alaves") if m["league"]=="西甲" and "Rayo" in m["home"] else (m["home"], m["away"])
    def score(mm):
        s = 0
        r = mm.get("risk") or []
        if not any("缺亚盘" in x for x in r): s += 100
        if not any("队名/数据缺失" in x for x in r): s += 50
        return s
    if key not in merged or score(m) > score(merged[key]):
        merged[key] = m
ms = list(merged.values())

snap = {}
with io.open(os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv"), encoding="utf-8", newline="") as fh:
    for row in csv.DictReader(fh):
        k = (norm(row["home_team"]), norm(row["away_team"]))
        mk = row["market"]; oc = row["outcome"]; ts = row["last_update"] or row["snapshot_ts"]
        e = snap.setdefault(k, {}).setdefault(mk, {}).setdefault(oc, {"ts": "", "point": None, "price": None})
        if ts > e["ts"]:
            e.update(ts=ts, point=row["point"], price=row["price"])

def find_snap(h, a):
    nh, na = norm(h), norm(a)
    best, best_score = None, -1
    for (sh, sa), v in snap.items():
        sc = 3 if (sh==nh and sa==na) else (2 if (sh in nh or nh in sh) and (sa in na or na in sa) else 1 if (sh==nh or sa==na) else 0)
        if sc > best_score or (sc == best_score and best and v.get("spreads") and not snap[best].get("spreads")):
            best_score, best = sc, (sh, sa)
    return snap.get(best)

def parse_rho(m):
    for n in (m.get("notes") or []):
        mm = re.search(r"rho=(-?\d+\.?\d*)", n)
        if mm: return float(mm.group(1))
    return 0.0

def ev_of(prob, price, overround):
    if not price or prob is None: return None
    return (prob / overround) * price - 1.0

def h2h_odds(sp, home, away):
    h2h = (sp or {}).get("h2h") or {}
    nh, na = norm(home), norm(away)
    h = d = a = None
    for oc, v in h2h.items():
        if not v.get("price"): continue
        n = norm(oc)
        if n == "draw": d = float(v["price"])
        elif n == nh: h = float(v["price"])
        elif n == na: a = float(v["price"])
    return h, d, a

def spread_odds(sp, home, away):
    spr = (sp or {}).get("spreads") or {}
    nh, na = norm(home), norm(away)
    hdp = home_price = away_price = None
    for oc, v in spr.items():
        if not v.get("price"): continue
        n = norm(oc)
        pt = v.get("point")
        try: ptf = float(pt) if pt not in (None, "") else None
        except: ptf = None
        if n == nh:
            home_price = float(v["price"])
            if ptf is not None: hdp = ptf
        elif n == na:
            away_price = float(v["price"])
    return hdp, home_price, away_price

def totals_by_line(sp):
    tot = (sp or {}).get("totals") or {}
    by_line = {}
    for oc, v in tot.items():
        if not v.get("price"): continue
        pt = v.get("point")
        try: line = float(pt) if pt not in (None, "") else None
        except: line = None
        if not line or line <= 0: continue
        side = "大" if oc.lower().startswith("over") else "小"
        by_line.setdefault(line, {})[side] = float(v["price"])
    return by_line

lines = []
lines.append("# 今晚 37 场完整方向报告 v2（1X2/大小球/让球/比分/双胜）")
lines.append("")

for m in sorted(ms, key=lambda x: x["ct"]):
    lam = m.get("lam") or {}
    lh, la = lam.get("home"), lam.get("away")
    wdl = m.get("wdl") or {}
    dir_ = m.get("dir") or {}
    sp = find_snap(m["home"], m["away"])
    rho = parse_rho(m)
    grid = dc_score_grid(lh, la, rho=rho, max_goals=8) if (lh and la) else None
    def P(cond):
        return sum(grid[i][j] for i in range(9) for j in range(9) if cond(i, j)) if grid else 0.0

    h_odd, dd_odd, a_odd = h2h_odds(sp, m["home"], m["away"])
    o1 = (1/h_odd + 1/dd_odd + 1/a_odd) if (h_odd and dd_odd and a_odd) else None
    w_h, w_d, w_a = wdl.get("home"), wdl.get("draw"), wdl.get("away")
    ev_h = ev_of(w_h/100, h_odd, o1) if (w_h is not None and o1) else None
    ev_d = ev_of(w_d/100, dd_odd, o1) if (w_d is not None and o1) else None
    ev_a = ev_of(w_a/100, a_odd, o1) if (w_a is not None and o1) else None
    best1 = max([("主胜",w_h,ev_h),("平局",w_d,ev_d),("客胜",w_a,ev_a)], key=lambda x: (x[1] or 0))
    def f1(ev): return "EV%+.1f%%" % (ev*100) if ev is not None else "EV-"

    # 大小球: 2.5用扫描校准值; 1.5/3.5模型参考
    ou_main = ""
    if dir_.get("name"):
        ou_main = "%s %.0f%%@%.2f EV%+.1f%%" % (dir_["name"], (dir_.get("prob") or 0)*100, dir_.get("odds"), (dir_.get("ev") or 0)*100)
    refs = []
    for line in (1.5, 2.5, 3.5):
        over = P(lambda i,j,l=line: i+j > l + 1e-9)
        refs.append("大%.1f %.0f%%/小 %.0f%%" % (line, over*100, (1-over)*100))

    # 让球
    hdp, hp, ap = spread_odds(sp, m["home"], m["away"])
    if hdp is not None and hp and ap and grid:
        cov = handicap_cover_prob(grid, hdp)
        orr = 1/hp + 1/ap
        ev_hp = ev_of(cov, hp, orr); ev_ap = ev_of(1-cov, ap, orr)
        sp_s = "市场盘 主%+.1f 覆盖%.0f%%@%.2f %s | 客 覆盖%.0f%%@%.2f %s" % (
            hdp, cov*100, hp, f1(ev_hp), (1-cov)*100, ap, f1(ev_ap))
    else:
        bits = []
        if grid:
            for h in (-2.0,-1.5,-1.0,-0.5,0.0,+0.5,+1.0,+1.5):
                c = handicap_cover_prob(grid, h)
                if 0.40 <= c <= 0.62:
                    bits.append("主%+.1f覆盖%.0f%%" % (h, c*100))
        sp_s = "无市场亚盘→模型推演: " + (" | ".join(bits[:5]) if bits else "方向不显著")

    # 比分TOP + 双胜
    if grid:
        top3 = sorted([(i,j,grid[i][j]) for i in range(9) for j in range(9)], key=lambda x:-x[2])[:3]
        score_s = " ".join("%d-%d(%.0f%%)" % (i,j,p*100) for i,j,p in top3)
        ph = w_h/100 if w_h else P(lambda i,j: i>j)
        pd = w_d/100 if w_d else P(lambda i,j: i==j)
        pa = w_a/100 if w_a else P(lambda i,j: i<j)
        dbl = "1X%.0f%% 12%.0f%% X2%.0f%%" % ((ph+pd)*100,(ph+pa)*100,(pd+pa)*100)
    else:
        score_s = dbl = "-"

    b = m.get("best")
    best_tag = (" | BEST:%s" % (b["name"])) if b else ""

    lines.append("▶ %s %s %s vs %s [λ %.2f/%.2f]%s" % (m["ct"], m["league"], m["home"], m["away"], lh, la, best_tag))
    lines.append("  1X2 主胜%.0f%%@%s %s | 平%.0f%%@%s %s | 客胜%.0f%%@%s %s → %s" % (
        w_h or 0, ("%.2f"%h_odd) if h_odd else "-", f1(ev_h),
        w_d or 0, ("%.2f"%dd_odd) if dd_odd else "-", f1(ev_d),
        w_a or 0, ("%.2f"%a_odd) if a_odd else "-", f1(ev_a), best1[0]))
    lines.append("  大小球 %s | 模型参考 %s" % (ou_main or "-", " | ".join(refs)))
    lines.append("  让球 %s" % sp_s)
    lines.append("  比分TOP %s | 双胜 %s" % (score_s, dbl))
    lines.append("  风险 %s" % (",".join(m.get("risk") or []) or "无"))
    lines.append("")

outp = os.path.join(ROOT, "analysis_records", "tonight_37_full_directions.txt")
io.open(outp, "w", encoding="utf-8").write("\n".join(lines))
print("saved:", outp, "| 场次:", len(ms))
