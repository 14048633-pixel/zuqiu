# -*- coding: utf-8 -*-
"""BSD历史概率校准检测 (1b): 模型概率 vs 实际命中率系统性偏差
============================================================
输入: analysis_records/bsd_pred_history.json  (BSD全量历史预测+赛果)
输出: analysis_records/bsd_prob_calib_YYYYMMDD.json + .md

用途:
  1) 验证BSD概率是否校准(概率桶 vs 实际命中率)
  2) 量化模型概率虚高/偏低的方向与幅度 -> 供Platt/保序回归定基线
  3) 对比BSD概率 vs 市场赔率隐含概率, 判断谁更准
"""
import collections, io, json, os, sys
from datetime import datetime

ROOT = os.getcwd()
OUT = os.path.join(ROOT, "analysis_records")
SRC = os.path.join(OUT, "bsd_pred_history.json")


def _norm(v):
    return v if isinstance(v, (int, float)) and v == v else None


def load_preds(path=SRC):
    d = json.load(io.open(path, encoding="utf-8"))
    vals = list(d.values()) if isinstance(d, dict) else d
    out = []
    for p in vals:
        e = p.get("event") or {}
        if e.get("status") != "finished":
            continue
        hg, ag = e.get("home_score"), e.get("away_score")
        if hg is None or ag is None:
            continue
        out.append({"p": p, "e": e, "hg": hg, "ag": ag,
                    "actual": "H" if hg > ag else ("A" if ag > hg else "D"),
                    "lg": (e.get("league") or {}).get("name") if isinstance(e.get("league"), dict) else e.get("league_name")})
    return out


def bin_stats(pairs):
    """[(pred_prob, actual_hit)] -> [(lo, hi, n, hit_rate)] 每10%一桶."""
    buckets = collections.defaultdict(lambda: [0, 0])
    for prob, hit in pairs:
        if prob is None:
            continue
        b = int(prob * 10) / 10.0
        buckets[b][0] += 1
        buckets[b][1] += 1 if hit else 0
    rows = []
    for b in sorted(buckets):
        n, h = buckets[b]
        rows.append((b, round(b + 0.1, 1), n, round(100.0 * h / n, 1)))
    return rows


def _implied(price):
    return 1.0 / price if _norm(price) else None


def run():
    preds = load_preds()
    if not preds:
        print("无历史数据: %s" % SRC)
        return
    res = {"n": len(preds), "ts": datetime.now().isoformat(timespec="seconds")}

    # 1) 1X2: BSD概率桶 vs 实际命中率
    pairs = []
    for x in preds:
        p = x["p"]
        h = _norm(p.get("prob_home_win"))
        if h is None:
            continue
        pairs.append((h / 100.0, x["actual"] == "H"))
    res["calib_1x2_home"] = bin_stats(pairs)

    # 2) 大球2.5: BSD概率桶 vs 实际大球率
    pairs_ou = []
    for x in preds:
        p = x["p"]
        ov = _norm(p.get("prob_over_25"))
        if ov is None:
            continue
        pairs_ou.append((ov / 100.0, (x["hg"] + x["ag"]) > 2.5))
    res["calib_over25"] = bin_stats(pairs_ou)

    # 3) 我们模型方向的概率虚高检测: 用"BSD最热方向概率"作为代理
    pairs_fav = []
    for x in preds:
        p = x["p"]
        f = p.get("favorite")
        fp = _norm(p.get("favorite_prob"))
        if f in ("H", "A") and fp is not None:
            pairs_fav.append((fp / 100.0, x["actual"] == ("H" if f == "H" else "A")))
    res["calib_favorite"] = bin_stats(pairs_fav)

    # 4) 市场赔率隐含概率 vs 实际 (市场是否更准)
    pairs_mkt = []
    for x in preds:
        e = x["e"]
        oh = _implied(e.get("odds_home"))
        if oh is None:
            continue
        pairs_mkt.append((oh, x["actual"] == "H"))
    res["calib_market_home"] = bin_stats(pairs_mkt)

    # 5) 系统性偏差汇总: 平均概率 vs 实际命中率
    def _summ(key):
        rows = res[key]
        if not rows:
            return None
        w_avg = sum(((r[0] + r[1]) / 2.0) * r[2] for r in rows) / sum(r[2] for r in rows) * 100.0
        hit_avg = sum(r[3] * r[2] for r in rows) / sum(r[2] for r in rows)
        return {"prob_avg": round(w_avg, 1), "hit_avg": round(hit_avg, 1),
                "bias_pp": round(w_avg - hit_avg, 1)}
    res["summary"] = {k: _summ(k) for k in ("calib_1x2_home", "calib_over25", "calib_favorite", "calib_market_home")}

    # 6) 按联赛: 热门方向概率 vs 命中 (找出虚高重灾区联赛)
    lg_stat = collections.defaultdict(lambda: [0.0, 0, 0])
    for x in preds:
        p = x["p"]
        f = p.get("favorite")
        fp = _norm(p.get("favorite_prob"))
        if f in ("H", "A") and fp is not None and x["lg"]:
            hit = 1 if (x["actual"] == ("H" if f == "H" else "A")) else 0
            s = lg_stat[x["lg"]]
            s[0] += fp
            s[1] += 1
            s[2] += hit
    res["league_favorite"] = {lg: {"n": s[1], "prob_avg": round(s[0] / s[1], 1),
                                    "hit_avg": round(100.0 * s[2] / s[1], 1),
                                    "bias_pp": round(s[0] / s[1] - 100.0 * s[2] / s[1], 1)}
                              for lg, s in sorted(lg_stat.items(), key=lambda kv: -kv[1][1])
                              if s[1] >= 5}
    return res


def render(res):
    L = []
    L.append("# BSD 历史概率校准检测 (1b)")
    L.append("- 样本: %d 场已完赛" % res["n"])
    L.append("")
    L.append("## 1. 1X2主胜概率桶 vs 实际命中率")
    L.append("| 概率桶 | 场数 | 实际命中率 |")
    L.append("|---|---|---|")
    for lo, hi, n, hit in res["calib_1x2_home"]:
        L.append("| %.0f%%-%.0f%% | %d | %.1f%% |" % (lo * 100, hi * 100, n, hit))
    L.append("")
    L.append("## 2. 大2.5概率桶 vs 实际大球率")
    L.append("| 概率桶 | 场数 | 实际大球率 |")
    L.append("|---|---|---|")
    for lo, hi, n, hit in res["calib_over25"]:
        L.append("| %.0f%%-%.0f%% | %d | %.1f%% |" % (lo * 100, hi * 100, n, hit))
    L.append("")
    L.append("## 3. 热门方向概率 vs 实际命中率 (我们模型最接近的代理)")
    L.append("| 概率桶 | 场数 | 实际命中率 |")
    L.append("|---|---|---|")
    for lo, hi, n, hit in res["calib_favorite"]:
        L.append("| %.0f%%-%.0f%% | %d | %.1f%% |" % (lo * 100, hi * 100, n, hit))
    L.append("")
    L.append("## 4. 市场主胜隐含概率 vs 实际命中率 (对比基准)")
    L.append("| 概率桶 | 场数 | 实际命中率 |")
    L.append("|---|---|---|")
    for lo, hi, n, hit in res["calib_market_home"]:
        L.append("| %.0f%%-%.0f%% | %d | %.1f%% |" % (lo * 100, hi * 100, n, hit))
    L.append("")
    L.append("## 5. 系统性偏差汇总 (概率均值 - 实际命中均值)")
    for k, v in res["summary"].items():
        if v:
            L.append("- %s: 概率均值%.1f%% vs 实际%.1f%% -> 偏差%+.1fpp" % (
                k, v["prob_avg"], v["hit_avg"], v["bias_pp"]))
    L.append("")
    L.append("## 6. 联赛热门方向偏差 (样本>=5, 按偏差降序)")
    L.append("| 联赛 | 场数 | 概率均值 | 实际命中 | 偏差 |")
    L.append("|---|---|---|---|---|")
    for lg, s in sorted(res["league_favorite"].items(), key=lambda kv: -(kv[1]["bias_pp"])):
        L.append("| %s | %d | %.1f%% | %.1f%% | %+.1fpp |" % (lg, s["n"], s["prob_avg"], s["hit_avg"], s["bias_pp"]))
    L.append("")
    L.append("> 偏差为正=模型概率虚高(实际达不到); 负=概率偏低(隐藏价值).")
    return "\n".join(L)


if __name__ == "__main__":
    res = run()
    if not res:
        sys.exit(1)
    out_json = os.path.join(OUT, "bsd_prob_calib_%s.json" % datetime.now().strftime("%Y%m%d"))
    io.open(out_json, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    out_md = os.path.join(OUT, "bsd_prob_calib_%s.md" % datetime.now().strftime("%Y%m%d"))
    io.open(out_md, "w", encoding="utf-8").write(render(res))
    print("已写: %s" % out_json)
    print(render(res))
