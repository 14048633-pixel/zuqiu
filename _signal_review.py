# -*- coding: utf-8 -*-
"""P5(2026-09-05): 伤停信号复盘闭环。

读 batch_predict 出单快照(含 injury_detail) -> 拉 BSD 实际比分 ->
逐信号判定"预测方向是否兑现" -> 累计到 signal_effectiveness.csv ->
按 位置/主力 分组输出命中率, 标记有效信号(防信息层过拟合)。

命中口径(固定, 可审计):
  atk>0 (该队进攻受损, 缺前锋/中场/门将) -> 命中 = 该队实际进球 <= 1
  def>0 (该队防守受损, 缺后卫/门将/中场) -> 命中 = 该队实际失球 >= 1

用法:
  python _signal_review.py <snapshot.json> [--write]   # --write 才落 CSV, 默认只预览
"""
import io, json, re, sys, os, csv
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CSV_PATH = r"D:\发家致富\strategy_data\signal_effectiveness.csv"
_POS_CN = {"G": "门将", "D": "后卫", "M": "中场", "F": "前锋"}


def norm(s):
    if not s:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", s)
    for suf in ("fc", "fk", "cf", "cfc", "afc", "ud", "cd", "ac", "sc", "sk", "bk", "if", "ff", "ss"):
        if s.endswith(suf) and len(s) > len(suf) + 2:
            s = s[: -len(suf)]
    return s


def fetch_scores(ko_list):
    """拉 BSD 比分: status=finished 显式拉已完赛 -> {norm(home,away): (hg, ag)}"""
    sys.path.insert(0, r"D:\足球分析\prediction_v2")
    import bsd_extra, requests
    dates = set()
    for ko in ko_list:
        if not ko:
            continue
        k = str(ko).strip()
        # 兼容 "09-05 00:00"(无年份) / "2026-09-05T.." / "2026-09-05"
        m = re.match(r"(\d{4})?-?(\d{2})-(\d{2})", k)
        if m:
            y, mo, da = m.groups()
            dates.add("%s-%s-%s" % (y or "2026", mo, da))
    # 北京凌晨 0-8 点的比赛 = UTC 前一天 16-24 点 -> 每个日期补拉前一天
    import datetime
    extra = set()
    for dd in dates:
        t = datetime.date(int(dd[:4]), int(dd[5:7]), int(dd[8:10])) - datetime.timedelta(days=1)
        extra.add(str(t))
    dates = sorted(dates | extra)
    score_map = {}
    for d in dates:
        off = 0
        while True:
            try:
                r = requests.get(bsd_extra.BASE_V2 + "/api/v2/events/", params={
                    "status": "finished",
                    "date_from": d + "T00:00:00Z", "date_to": d + "T23:59:59Z",
                    "limit": 100, "offset": off, "full": "true"},
                    headers=bsd_extra.HEADERS, timeout=60)
                if r.status_code != 200:
                    print("  拉取 %s 失败: HTTP %s" % (d, r.status_code))
                    break
            except Exception as e:
                print("  拉取 %s 失败: %s" % (d, repr(e)[:60]))
                break
            res = r.json().get("results") or []
            for j in res:
                h = j.get("home_team"); a = j.get("away_team")
                h = h.get("name") if isinstance(h, dict) else h
                a = a.get("name") if isinstance(a, dict) else a
                st = bsd_extra.event_settle_scores(j)
                if st["needs_verify"] or st["hg_90"] is None or st["ag_90"] is None:
                    continue
                score_map[(norm(h), norm(a))] = (st["hg_90"], st["ag_90"])
            if len(res) < 100:
                break
            off += 100
    return score_map


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    snap = sys.argv[1]
    write = "--write" in sys.argv
    d = json.load(io.open(snap, encoding="utf-8"))

    # 1) 收集信号 + 场次比分
    signals = []
    ko_list = [r.get("ko_bjt") for r in d]
    smap = fetch_scores(ko_list) if write else {}
    for r in d:
        home, away = r.get("home"), r.get("away")
        ko = r.get("ko_bjt")
        det = r.get("injury_detail") or {"home": [], "away": []}
        for side in ("home", "away"):
            team = home if side == "home" else away
            for sig in (det.get(side) or []):
                signals.append({"ko": ko, "match": "%s vs %s" % (home, away),
                                "side": side, "team": team, "name": sig.get("name"),
                                "pos": sig.get("pos"), "tag": sig.get("tag"),
                                "atk": sig.get("atk", 0), "def": sig.get("def", 0),
                                "hg": None, "ag": None, "hit_atk": None, "hit_def": None})
    print("快照场次:", len(d), "| 伤停信号:", len(signals))

    # 2) 判定命中
    scored = 0
    for s in signals:
        sc = smap.get((norm(s["match"].split(" vs ")[0]), norm(s["match"].split(" vs ")[1])))
        if sc is None:
            continue
        hg, ag = sc
        s["hg"], s["ag"] = hg, ag
        scored += 1
        my_goals = hg if s["side"] == "home" else ag
        opp_goals = ag if s["side"] == "home" else hg
        if s["atk"] > 0:
            s["hit_atk"] = 1 if my_goals <= 1 else 0
        if s["def"] > 0:
            s["hit_def"] = 1 if opp_goals >= 1 else 0
    print("已有比分的信号:", scored)

    # 3) 落 CSV(去重: ko+match+side+name)
    if write:
        exists = os.path.exists(CSV_PATH)
        seen = set()
        if exists:
            with io.open(CSV_PATH, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    seen.add((row["ko"], row["match"], row["side"], row["name"]))
        new_rows = [s for s in signals if s["hg"] is not None and
                    (s["ko"], s["match"], s["side"], s["name"]) not in seen]
        with io.open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["ko", "match", "side", "team", "name", "pos",
                                              "tag", "atk", "def", "hg", "ag",
                                              "hit_atk", "hit_def"])
            if not exists:
                w.writeheader()
            for s in new_rows:
                w.writerow({k: s[k] for k in w.fieldnames})
        print("写入 %d 条到 %s" % (len(new_rows), CSV_PATH))

    # 4) 聚合统计(含历史 CSV 全量)
    rows = []
    if os.path.exists(CSV_PATH):
        with io.open(CSV_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    rows.append({**row, "atk": float(row["atk"] or 0),
                                 "def": float(row["def"] or 0)})
                except (ValueError, TypeError):
                    pass
    print("\n== 信号有效性 (累计 %d 条, 全 CSV) ==" % len(rows))
    print("\n[按位置] 防守信号(def>0)命中率(丢球>=1):")
    by_pos = defaultdict(list)
    for r in rows:
        if r["def"] > 0 and r["hit_def"] is not None and r["hit_def"] != "":
            by_pos[r["pos"] or "?"].append(int(r["hit_def"]))
    for pos, hits in sorted(by_pos.items(), key=lambda x: -len(x[1])):
        n = len(hits); rate = sum(hits) / n * 100
        flag = "有效" if (n >= 30 and rate >= 52) else ("弱信号" if n >= 30 else "样本不足")
        print("  %-4s n=%3d 命中率=%5.1f%%  [%s]" % (pos, n, rate, flag))
    print("\n[按主力] 全部信号命中率(atk/def 任一):")
    by_tag = defaultdict(list)
    for r in rows:
        hits = []
        if r["hit_atk"] is not None and r["hit_atk"] != "":
            hits.append(int(r["hit_atk"]))
        if r["hit_def"] is not None and r["hit_def"] != "":
            hits.append(int(r["hit_def"]))
        if hits:
            by_tag[r["tag"] or "?"].append(sum(hits) / len(hits))
    for tag, hs in sorted(by_tag.items(), key=lambda x: -len(x[1])):
        n = len(hs); rate = sum(hs) / n * 100
        flag = "有效" if (n >= 30 and rate >= 52) else ("弱信号" if n >= 30 else "样本不足")
        print("  %-12s n=%3d 命中率=%5.1f%%  [%s]" % (tag, n, rate, flag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
