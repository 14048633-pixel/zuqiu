# -*- coding: utf-8 -*-
"""球队目录治理: 统一 数据键/别名/BSD名/ESPN名/联赛 映射 -> strategy_data/team_catalog.json
============================================================
用法: python prediction_v2/build_team_catalog.py
数据源: load_team_stats()数据键 + teams_alias.json + ESPN CSV队名 + BSD v1/v2事件队名
输出: strategy_data/team_catalog.json (norm -> {canon, stats_key, divs, aliases, bsd_names, espn_names, leagues})
     + 控制台: 未匹配BSD队名清单(队名缺口)
"""
import csv, io, json, os, sys, unicodedata, glob, collections
sys.path.insert(0, os.path.join(os.getcwd(), "prediction_v2"))
import scan_upcoming as SC

ROOT = os.getcwd()
OUT = os.path.join(ROOT, "strategy_data", "team_catalog.json")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace("-", " ").replace(".", " ").replace("'", " ").replace("&", " ").split())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    team_stats, lavg, index = SC.load_team_stats()
    al = json.load(io.open(os.path.join(ROOT, "strategy_data", "teams_alias.json"), encoding="utf-8")).get("alias", {})

    # 1) 数据键 + 联赛(div)
    cat = {}
    for key, divs in team_stats.items():
        r = cat.setdefault(norm(key), {"canon": key, "stats_key": key, "divs": sorted(divs),
                                       "aliases": [], "bsd_names": [], "espn_names": [], "leagues": []})
        r["divs"] = sorted(set(r["divs"]) | set(divs))

    # 2) 别名(反向: 别名->标准键)
    for alias, std in al.items():
        r = cat.setdefault(norm(alias), {"canon": std, "stats_key": std, "divs": [],
                                         "aliases": [], "bsd_names": [], "espn_names": [], "leagues": []})
        if alias not in r["aliases"]:
            r["aliases"].append(alias)

    # 3) ESPN CSV 队名
    for fp in glob.glob(os.path.join(ROOT, "data", "raw", "football_data", "espn_*_results.csv")):
        try:
            with io.open(fp, encoding="utf-8", errors="replace") as f:
                for row in csv.DictReader(f):
                    for k in ("home", "away", "HomeTeam", "AwayTeam"):
                        v = row.get(k)
                        if not v:
                            continue
                        n = str(v).strip()
                        r = cat.setdefault(norm(n), {"canon": n, "stats_key": None, "divs": [],
                                                     "aliases": [], "bsd_names": [], "espn_names": [], "leagues": []})
                        if n not in r["espn_names"]:
                            r["espn_names"].append(n)
        except Exception:
            pass

    # 4) BSD v1/v2 队名
    bsd_names = collections.Counter()
    for fp in ("analysis_records/bzzoiro_events_2026-08-17.json",
               "analysis_records/bzzoiro_events_2026-08-16.json"):
        if not os.path.exists(fp):
            continue
        try:
            j = json.load(io.open(fp, encoding="utf-8"))
            for ev in j.get("events") or []:
                for side in ("home_team", "away_team"):
                    n = ev.get(side)
                    if n:
                        bsd_names[str(n).strip()] += 1
        except Exception:
            pass
    for n in bsd_names:
        r = cat.setdefault(norm(n), {"canon": n, "stats_key": None, "divs": [],
                                     "aliases": [], "bsd_names": [], "espn_names": [], "leagues": []})
        if n not in r["bsd_names"]:
            r["bsd_names"].append(n)

    # 5) 词集匹配: BSD名 -> 已有stats_key条目(如 "CA Lanús" -> "Lanús", "Olympique Lyonnais" -> "Lyon")
    keys_norm = [k for k, v in cat.items() if v.get("stats_key")]
    for n in bsd_names:
        r = cat.get(norm(n), {})
        if r.get("stats_key"):
            continue
        ws = set(norm(n).split())
        hit = None
        for k in keys_norm:
            wk = set(k.split())
            if ws and wk and (ws <= wk or wk <= ws):
                if len(ws) == 1 or len(wk) == 1 or min(len(ws), len(wk)) / max(len(ws), len(wk)) >= 0.5:
                    hit = k
                    break
        if hit:
            target = cat[hit]
            if n not in target["bsd_names"]:
                target["bsd_names"].append(n)
            del cat[norm(n)]
    # 6) 未匹配BSD队名: 未被任何stats_key条目收录 = 无攻防数据
    matched_bsd = set()
    for k, v in cat.items():
        if v.get("stats_key"):
            matched_bsd.update(v.get("bsd_names", []))
    unmatched = [n for n in bsd_names if n not in matched_bsd]

    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": "2026-08-17",
                   "note": "统一球队目录: norm -> {canon/stats_key/divs/aliases/bsd_names/espn_names/leagues}",
                   "n_entries": len(cat), "n_unmatched_bsd": len(unmatched),
                   "teams": {k: v for k, v in cat.items() if v.get("stats_key") or v.get("bsd_names")}},
                  f, ensure_ascii=False, indent=1)
    print("saved team_catalog.json, entries=%d" % len(cat))
    print("\n== 未匹配BSD队名(无攻防数据) ==")
    for n in sorted(unmatched):
        print("  ⚠ %s" % n)
    print("\n未匹配 %d / %d BSD队名" % (len(unmatched), len(bsd_names)))


if __name__ == "__main__":
    main()
