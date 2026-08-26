# -*- coding: utf-8 -*-
"""快照自检工具 — 每场/每批分析后一键检查数据完整性
================================================================
用途:
  1. 逐场检查 1X2/亚盘/大小球 三市场覆盖是否齐全(哪场缺什么一目了然)
  2. 侧边判定一致性: 用 classify_side 重判 outcome 名, 与快照存储 side 对比,
     揪出 "队名不一致导致 1X2/亚盘错配或丢失" 的历史污染(SJK/Cracovia/Al-Hazem/Aldosivi 类)
  3. 同侧多价检测: 同一 book+line 下同一 side 出现不同 price = 数据被污染
  4. 可选: 传入 rerun JSON 审计风险标签分布(伤停覆盖占比等), 提示数据源缺口

纯标准库; 用法:
  python selfcheck_scan.py [--snap <csv>] [--rerun <json>] [--json]
  # 默认读 prediction_v2/output/odds_snapshots/snapshots.csv

输出: 每场一行覆盖矩阵 + 问题清单 + 汇总统计; 发现可修复污染返回非0。
"""
import argparse
import collections
import csv
import io
import json
import os
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from src.live_odds import classify_side  # noqa: E402


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def load_rows(path):
    if not os.path.exists(path):
        print("❌ 快照不存在: %s" % path)
        sys.exit(2)
    with io.open(path, "r", encoding="utf-8") as f:
        r = csv.reader(f)
        try:
            hdr = next(r)
        except StopIteration:
            return [], []
        return hdr, list(r)


def audit_snapshot(path):
    hdr, rows = load_rows(path)
    if not rows:
        print("❌ 快照为空: %s" % path)
        return 2
    # 列: 0 snapshot_ts 1 event_id 2 league 3 ct 4 home 5 away
    #     6 book 7 market 8 outcome 9 side 10 side_key 11 point 12 price 13 last_update
    events = collections.OrderedDict()
    for x in rows:
        if len(x) < 13:
            continue
        key = (x[1], x[4], x[5])
        ev = events.setdefault(key, {
            "league": x[2], "ct": x[3], "home": x[4], "away": x[5],
            "markets": collections.defaultdict(list),
        })
        try:
            price = float(x[12])
        except (TypeError, ValueError):
            price = None
        ev["markets"][x[7]].append({
            "ts": x[0], "book": x[6], "outcome": x[8], "side": x[9], "line": x[11], "price": price,
        })

    problems = []
    matrix = []
    n_full = 0
    for (eid, h, a), ev in events.items():
        m = ev["markets"]
        has_h = _check_market(m.get("h2h", []), "h2h", eid, h, a, problems)
        # 亚盘含欧盘 spreads(主客异号, 按abs归组) 与 API-Football asian_handicap(同号同盘, 按带符号线归组)
        has_s = (_check_market(m.get("spreads", []), "spreads", eid, h, a, problems)
                 or _check_market(m.get("asian_handicap", []), "asian_handicap", eid, h, a, problems))
        has_t = _check_market(m.get("totals", []), "totals", eid, h, a, problems)
        flag = ""
        if has_h and has_s and has_t:
            n_full += 1
        else:
            flag = "  <<< 缺盘"
        matrix.append("%s %-12s %-22s vs %-22s | 1X2=%s 亚盘=%s 大小球=%s%s" % (
            eid, (ev["league"] or "?")[:12], h, a,
            "✔" if has_h else "-", "✔" if has_s else "-", "✔" if has_t else "-", flag))

    print("=" * 78)
    print("自检: %s  (%d 事件, %d 行)" % (path, len(events), len(rows)))
    print("=" * 78)
    for line in matrix:
        print(line)
    print()
    print("三市场齐全: %d/%d" % (n_full, len(events)))
    print()
    if problems:
        print("⚠️  发现 %d 个数据问题:" % len(problems))
        for p in problems:
            print("  - %s" % p)
    else:
        print("✅ 未发现侧边错配/同侧多价问题")
    return 0 if not problems else 1


def _check_market(rows, market, eid, h, a, problems):
    """返回该市场是否可用(主客/三侧齐全), 并登记错配问题。"""
    if not rows:
        return False
    if market == "h2h":
        # 按 (ts, book, line) 分组: 同侧多价检测 + 三侧齐全覆盖(任意一次快照齐全即算有盘)
        groups = collections.defaultdict(dict)
        for r in rows:
            g = groups[(r["ts"], r["book"], r["line"])]
            if r["side"] in g and g[r["side"]] != r["price"]:
                problems.append("%s %s vs %s | h2h %s/%s 同侧多价: %.2f vs %.2f" %
                                (eid, h, a, r["book"], r["side"], g[r["side"]], r["price"]))
            g[r["side"]] = r["price"]
            want = classify_side(r["outcome"], h, a)
            if want is not None and want != r["side"]:
                problems.append("%s %s vs %s | h2h %s 侧边错配: 存=%s 重判=%s (outcome=%r)" %
                                (eid, h, a, r["book"], r["side"], want, r["outcome"]))
        return any({"home", "draw", "away"} <= set(g) for g in groups.values())
    if market in ("spreads", "asian_handicap"):
        groups = collections.defaultdict(dict)
        for r in rows:
            try:
                line_f = float(r["line"]) if market == "asian_handicap" else (float(r["line"]) if r["side"] == "home" else -float(r["line"]))
            except (TypeError, ValueError):
                line_f = None
            g = groups[(r["ts"], r["book"], line_f)]
            if r["side"] in g and g[r["side"]] != r["price"]:
                problems.append("%s %s vs %s | %s %s/%s 同侧多价" % (eid, h, a, market, r["book"], r["side"]))
            g[r["side"]] = r["price"]
            if r["side"] in ("home", "away"):
                want = classify_side(r["outcome"], h, a)
                if want is not None and want != r["side"]:
                    problems.append("%s %s vs %s | %s %s 侧边错配: 存=%s 重判=%s (outcome=%r)" %
                                    (eid, h, a, market, r["book"], r["side"], want, r["outcome"]))
        return any({"home", "away"} <= set(g) for g in groups.values())
    if market == "totals":
        groups = collections.defaultdict(dict)
        for r in rows:
            g = groups[(r["ts"], r["book"], r["line"])]
            if r["side"] in g and g[r["side"]] != r["price"]:
                problems.append("%s %s vs %s | totals %s/%s 同侧多价" % (eid, h, a, r["book"], r["side"]))
            g[r["side"]] = r["price"]
        return any({"over", "under"} <= set(g) for g in groups.values())
    return True


def repair_snapshot(path):
    """定向修复侧边错配行: classify_side 与存储 side 不一致且可置信时, 改写 side/side_key。
    仅修复 h2h/spreads 的 home/away 错配, 不做其它改动; 先备份原文件。
    返回修复行数。"""
    hdr, rows = load_rows(path)
    fixed = 0
    out = [hdr]
    for x in rows:
        if len(x) < 13:
            out.append(x)
            continue
        mk = x[7]
        if mk not in ("h2h", "spreads"):
            out.append(x)
            continue
        want = classify_side(x[8], x[4], x[5])
        if want in ("home", "away") and want != x[9]:
            x[9] = want
            if mk == "spreads":
                x[10] = "%s@%s" % (want, x[11]) if x[11] else want
            else:
                x[10] = want
            fixed += 1
        out.append(x)
    if fixed:
        bak = path + ".bak"
        if not os.path.exists(bak):
            try:
                io.open(bak, "w", encoding="utf-8", newline="").write(
                    "".join(",".join(r) + "\n" for r in rows))
            except Exception:
                pass
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerows(out)
    print("✅ 修复 %d 行侧边错配 (备份: %s.bak)" % (fixed, path))
    return fixed


def audit_rerun(path):
    d = json.load(io.open(path, encoding="utf-8"))
    ms = d.get("matches") or []
    print("=" * 78)
    print("风险标签审计: %s (%d 场)" % (path, len(ms)))
    print("=" * 78)
    cnt = collections.Counter()
    for m in ms:
        for t in (m.get("result", {}).get("risk_tags") or []):
            cnt[t] += 1
    for t, n in cnt.most_common(20):
        print("  %-46s %d" % (t, n))
    n_inj = sum(1 for m in ms for t in (m.get("result", {}).get("risk_tags") or []) if "伤停覆盖不全" in t)
    if ms:
        print()
        print("伤停覆盖不全占比: %d/%d (%.0f%%)" % (n_inj, len(ms), 100.0 * n_inj / len(ms)))
    return 0


def main():
    ap = argparse.ArgumentParser(description="快照自检")
    ap.add_argument("--snap", default=os.path.join(HERE, "output", "odds_snapshots", "snapshots.csv"))
    ap.add_argument("--rerun", default="")
    ap.add_argument("--repair", action="store_true", help="修复侧边错配行(先备份)")
    args = ap.parse_args()
    if args.repair:
        sys.exit(repair_snapshot(args.snap))
    rc = audit_snapshot(args.snap)
    if args.rerun:
        audit_rerun(args.rerun)
    sys.exit(rc)


if __name__ == "__main__":
    main()