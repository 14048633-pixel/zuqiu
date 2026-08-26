# -*- coding: utf-8 -*-
"""窗口内(18:00-24H) the-odds 比赛去重 + BSD 匹配 -> scan24h JSON"""
import sys, io, csv, json, unicodedata, re, collections
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "D:/足球分析/prediction_v2")
import bsd_extra

BJT = timezone(timedelta(hours=8))

def norm(t):
    t = unicodedata.normalize("NFKD", str(t))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace("-", " ").replace(".", " ").replace("'", " ").replace("/", " ")
    return " ".join(sorted(set(re.split(r"[^a-z0-9]+", t)) - {"fc", "cf", "club", "sc", "ac", "afc"}))

rows = list(csv.reader(io.open("D:/足球分析/prediction_v2/output/odds_snapshots/snapshots.csv", encoding="utf-8")))
hdr = rows[0]
FROM = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
TO = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)
games = {}
for r in rows[1:]:
    d = dict(zip(hdr, r))
    try:
        ct = datetime.fromisoformat(d.get("commence_time", "").replace("Z", "+00:00"))
    except Exception:
        continue
    if not (FROM <= ct < TO):
        continue
    lg = d.get("league")
    h, a = d.get("home_team"), d.get("away_team")
    pair = tuple(sorted([norm(h), norm(a)]))
    ukey = (lg, pair, int(ct.timestamp() / 1800))
    g = games.setdefault(ukey, {"league": lg, "ct": ct, "cand": []})
    g["cand"].append((h, a, d.get("event_id"), d.get("bookmaker")))

print("去重后比赛:", len(games))
final = []
for ukey, g in games.items():
    cnt = collections.Counter((h, a) for h, a, _, _ in g["cand"])
    (h, a), _ = cnt.most_common(1)[0]
    bks = {b for _, _, _, b in g["cand"]}
    final.append({"league": g["league"], "home": h, "away": a, "ct": g["ct"].isoformat(), "bks": len(bks)})
final.sort(key=lambda x: x["ct"])

# BSD 匹配
events = []
for date in ("2026-08-23", "2026-08-24"):
    evs = bsd_extra._load_events(date, True)
    if evs:
        events.extend(evs)
# 别名补充(the-odds 名 -> 常见 BSD 名)
ALIAS = {"Shanghai SIPG FC": "Shanghai Port",
         "Paris Saint Germain": "Paris Saint-Germain",
         "Rennes": "Stade Rennais",
         "KuPS Kuopio": "Kuopion Palloseura",
         "TPS Turku": "Turun Palloseura",
         "OFI Crete": "OFI Crete",
         "Volos FC": "NPS Volos",
         "Panetolikos Agrinio": "GFS Panetolikos",
         "Asteras Tripolis": "Asteras Aktor",
         "Daejeon Citizen": "Daejeon Hana Citizen",
         "BSC Young Boys": "Young Boys",
         }

def cand_names(v):
    out = [v]
    if v in ALIAS:
        out.append(ALIAS[v])
    return out

matched, unmatched = [], []
for f in final:
    bj = datetime.fromisoformat(f["ct"]).astimezone(BJT)
    match = {"home": f["home"], "away": f["away"], "time": bj.strftime("%m-%d %H:%M")}
    ev = bsd_extra._match_event(match, events)
    if not ev:
        # 别名重试
        match2 = dict(match)
        match2["home"] = ALIAS.get(f["home"], f["home"])
        match2["away"] = ALIAS.get(f["away"], f["away"])
        ev = bsd_extra._match_event(match2, events)
    if ev:
        matched.append({"id": ev.get("id"), "league": f["league"],
                        "kickoff": bj.strftime("%m-%d %H:%M"), "kickoff_iso": f["ct"],
                        "home": f["home"], "away": f["away"],
                        "home_id": bsd_extra._side_team_id(ev, "home"),
                        "away_id": bsd_extra._side_team_id(ev, "away")})
    else:
        unmatched.append(f)

print("匹配成功:", len(matched), "| 未匹配(BSD无覆盖/名字差异):", len(unmatched))
print()
print("== 未匹配 ==")
for f in unmatched:
    bj = datetime.fromisoformat(f["ct"]).astimezone(BJT).strftime("%m-%d %H:%M")
    print("  %-12s | %s vs %s | %s" % (f["league"], f["home"], f["away"], bj))

out = {"timestamp": "2026-08-23T17:40:00+08:00", "type": "scan24h(18:00-24H, the-odds+BSD)", "matches": matched}
with io.open("D:/足球分析/analysis_records/scan24h_20260823_1824.json", "w", encoding="utf-8") as fp:
    json.dump(out, fp, ensure_ascii=False, indent=1)
print()
print("saved: analysis_records/scan24h_20260823_1824.json (%d 场)" % len(matched))
by = collections.Counter(m["league"] for m in matched)
print("按联赛:", dict(by))
