# -*- coding: utf-8 -*-
"""全方向明细对账: 对已完赛每场, 结算 1X2/让球/大小球 每个方向
输入: scan24h_settle_<ts>.json(已完赛+比分) + scan24h_analysis_<ts>.json(bets)
输出: analysis_records/scan24h_settle_full_<ts>.json/.md
"""
import sys, os, json, io, glob, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
import settle_batch as sb

def latest(prefix, suffix=".json"):
    xs = [x for x in os.listdir(os.path.join(ROOT, "analysis_records"))
          if x.startswith(prefix) and x.endswith(suffix) and "full" not in x]
    return sorted(xs)[-1] if xs else None

def main():
    sf = latest("scan24h_settle_")
    af = latest("scan24h_analysis_")
    settle = json.load(io.open(os.path.join(ROOT, "analysis_records", sf), encoding="utf-8"))
    ana = json.load(io.open(os.path.join(ROOT, "analysis_records", af), encoding="utf-8"))
    # analysis 索引: (ct, home, away)
    idx = {}
    for m in ana["matches"]:
        idx[(m["ct"], m["home"], m["away"])] = m
    rows = []
    for s in settle["settled"]:
        m = idx.get((s["ct"], s["home"], s["away"]))
        bets = (m or {}).get("bets") or []
        legs = []
        for b in bets:
            name = b.get("name")
            if not name:
                continue
            try:
                res, _ = sb.settle_leg(name, b.get("odds") or 1.0, s["hg"], s["ag"])
            except Exception:
                res = None
            legs.append({
                "name": name, "prob": b.get("prob"), "odds": b.get("odds"),
                "ev": b.get("ev"), "star": b.get("star"), "ev_tier": b.get("ev_tier"),
                "is_1x2": bool(b.get("is_1x2")), "result": res,
            })
        rows.append({**s, "legs": legs})
    # 汇总
    def grp(tag):
        return [l for r in rows for l in r["legs"] if l["name"].startswith(tag)]
    def stat(legs):
        n = len(legs)
        w = sum(1 for l in legs if l["result"] == "win")
        l = sum(1 for l in legs if l["result"] == "lose")
        p = sum(1 for l in legs if l["result"] == "push")
        h = sum(1 for l in legs if l["result"] == "half")
        r = 100.0 * (w + 0.5 * h) / (n - p) if (n - p) else None
        return {"n": n, "win": w, "lose": l, "push": p, "half": h, "rate": r}
    s1x2, ssp, stot = stat(grp("1X2")), stat(grp("让球")), stat(grp("大") or grp("小"))
    # 正EV方向
    pos = [l for r in rows for l in r["legs"] if (l.get("ev") or 0) > 0]
    neg = [l for r in rows for l in r["legs"] if (l.get("ev") or 0) <= 0]
    sp_neg = stat(neg)
    sp_pos = stat(pos)
    # 主方向
    md = stat([{"result": r["dir_result"]} for r in rows if r["direction_name"]])
    now = datetime.now().strftime("%Y%m%d_%H%M")
    outp = os.path.join(ROOT, "analysis_records", "scan24h_settle_full_%s.json" % now)
    json.dump({"ts": settle["ts"], "n_settled": len(rows), "rows": rows,
               "summary": {"1x2": s1x2, "spread": ssp, "totals": stot,
                           "pos_ev": sp_pos, "neg_ev": sp_neg, "main_dir": md}},
              open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # MD
    M = {"win": "✅ 命中", "lose": "❌ 未中", "push": "➖ 走水", "half": "◐ 半赢"}
    L = []
    L.append("# ⚽ 全方向明细对账（已完赛 %d 场）" % len(rows))
    L.append("")
    L.append("> 生成时间：%s｜比分源：BSD finished｜结算：settle_batch 全市场" % settle["ts"][:16])
    L.append("")
    L.append("## 📊 按市场命中率")
    L.append("")
    L.append("| 市场 | 注数 | 命中 | 未中 | 走水 | 半赢 | 命中率 |")
    L.append("|---|---|---|---|---|---|---|")
    for nm, st in [("1X2 胜平负", s1x2), ("让球(亚盘/欧盘)", ssp), ("大小球", stot)]:
        L.append("| %s | %d | %d | %d | %d | %d | %s |" % (nm, st["n"], st["win"], st["lose"], st["push"], st["half"],
                ("%.1f%%" % st["rate"]) if st["rate"] is not None else "—"))
    L.append("")
    L.append("### 按 EV 分层（模型方向, 非对冲侧）")
    L.append("")
    for nm, st in [("正 EV 方向(模型建议)", sp_pos), ("负 EV 方向(对手侧)", sp_neg)]:
        L.append("- %s：%d 注｜命中 %d / 未中 %d｜命中率 %s" % (nm, st["n"], st["win"], st["lose"],
                ("%.1f%%" % st["rate"]) if st["rate"] is not None else "—"))
    L.append("- 主方向(direction)：%d 注｜命中 %d / 未中 %d｜命中率 %s" % (md["n"], md["win"], md["lose"],
            ("%.1f%%" % md["rate"]) if md["rate"] is not None else "—"))
    L.append("")
    for r in rows:
        L.append("## %s %s %s vs %s　**%s**" % (r["ct"], r["league"], r["home"], r["away"], r["score"]))
        L.append("")
        L.append("| 市场 | 方向 | 概率 | 赔率 | EV | 星级 | 结果 |")
        L.append("|---|---|---|---|---|---|---|")
        for l in r["legs"]:
            mk = "1X2" if l["is_1x2"] else ("让球" if l["name"].startswith("让") else "大小")
            st = l.get("star")
            sts = ("★%d" % st) if st else ("[%s]" % l.get("ev_tier", "")) if (l.get("ev") or 0) > 0 else "—"
            evs = ("%+.1f%%" % (l["ev"] * 100)) if l.get("ev") is not None else "—"
            ps = ("%.0f%%" % (l["prob"] * 100)) if l.get("prob") is not None else "—"
            L.append("| %s | %s | %s | %.2f | %s | %s | %s |" % (mk, l["name"], ps, l["odds"] or 0, evs, sts,
                    M.get(l["result"], l["result"] or "—")))
        L.append("")
    outf = outp.replace(".json", ".md")
    open(outf, "w", encoding="utf-8").write("\n".join(L))
    print("saved:", outp)
    print("1X2: %s | 让球: %s | 大小球: %s" % (s1x2, ssp, stot))
    print("正EV方向: %s | 主方向: %s" % (sp_pos, md))

if __name__ == "__main__":
    from datetime import datetime
    main()
