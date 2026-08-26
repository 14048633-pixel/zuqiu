# -*- coding: utf-8 -*-
"""扫描未来 N 小时比赛队伍 v2 (补全联赛中文名 + 过滤已开赛 + 标题标注)
用法:
  python _scan48h_new.py                    # 默认 48h
  python _scan48h_new.py --hours 24 --title "2026-8-22-早上8点拉取的比赛"
输出: analysis_records/scan{h:02d}h_{ts}.json (含 title 字段)
"""
import sys, io, json, urllib.request, collections, argparse
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"D:\足球分析"
tok = ""
for line in io.open(ROOT + r"\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        tok = line.split("=", 1)[1].strip().strip('"').strip("'")

def get(path):
    url = "https://sports.bzzoiro.com/api/v2" + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
    return json.load(urllib.request.urlopen(req, timeout=40))

leagues = {}
for x in (get("/leagues/?limit=200").get("results") or []):
    leagues[x["id"]] = (x.get("name") or "", x.get("country") or "")

now = datetime.now(timezone.utc)
ap = argparse.ArgumentParser()
ap.add_argument("--hours", type=int, default=48)
ap.add_argument("--title", default="")
args = ap.parse_args()
hours = max(1, min(args.hours, 96))
title = args.title or "scan%dh_%s" % (hours, datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M"))

d0 = now.strftime("%Y-%m-%d")
d1 = (now + timedelta(hours=hours)).strftime("%Y-%m-%d")
all_ev = []
offset = 0
while True:
    j = get("/events/?status=upcoming&date_from=%s&date_to=%s&limit=200&offset=%d" % (d0, d1, offset))
    res = j.get("results") or []
    all_ev += res
    if len(res) < 200:
        break
    offset += 200

# 主映射: strategy_data/leagues_map.json (BSD英文联赛名 -> 系统中文名), 与 scan/pull 全链一致
_LM = {}
try:
    _lm = json.load(io.open(ROOT + r"\strategy_data\leagues_map.json", encoding="utf-8"))
    _LM = _lm.get("map") or {}
except Exception:
    pass

LG_CN = {
    "Emperor Cup": "天皇杯", "Conference League": "欧协联", "Club Friendlies": "友谊赛",
    "MLS": "美职", "Europa League": "欧联", "Brasileirão Serie B": "巴乙",
    "Champions League": "欧冠", "Copa Colombia": "哥伦比亚杯", "Liga MX Apertura": "墨超",
    "Chinese Super League": "中超", "La Liga": "西甲", "Categoría Primera A": "哥甲",
    "NWSL": "美职女足", "Liga Profesional de Fútbol": "阿甲", "USL Championship": "美乙",
    "League One": "英甲", "Saudi Pro League": "沙超", "Copa del Rey": "西杯",
    "Coppa Italia": "意杯", "UEFA Champions League Qualification": "欧冠资格",
    "Denmark Superliga": "丹超", "Sweden Allsvenskan": "瑞超",
    "Spain Segunda Division": "西乙", "Argentina Primera Division": "阿甲",
    "Turkey Super Lig": "土超", "England Championship": "英冠",
    "Portugal Primeira Liga": "葡超", "Chile Primera Division": "智利甲",
    "Copa Sudamericana": "南美杯", "Copa Libertadores": "解放者杯",
    "Finland Veikkausliiga": "芬超", "Romania Liga I": "罗甲",
    "Bulgaria Parva Liga": "保甲", "Brazil Serie A": "巴甲",
    "Japan J League": "J1", "Netherlands Eredivisie": "荷甲",
    "Germany Bundesliga 2": "德乙", "USA MLS": "美职",
    "England Premier League": "英超", "Italy Serie A": "意甲",
    "Germany Bundesliga": "德甲", "Greece Super League": "希超",
    "Switzerland Super League": "瑞甲", "Austria Bundesliga": "奥甲",
    "Poland Ekstraklasa": "波甲", "Russia Premier League": "俄超",
    "Scotland Premiership": "苏超", "Ireland Premier Division": "爱超",
    "Korea K League 1": "K1", "Belgium First Division A": "比甲",
    "Norway Eliteserien": "挪超", "Spain La Liga": "西甲",
    # 补漏 2026-08-22 (BSD 实际返回名)
    "DFB Pokal": "德国杯", "National League": "英议联", "League Two": "英乙",
    "J1 League": "J1", "Championship": "英冠", "Liga 3": "葡丙",
    "Liga Portugal 2": "葡乙", "Liga Portugal Betclic": "葡超",
    "Brasileirão Serie A": "巴甲", "Stoiximan Super League": "希超",
    "Super League": "瑞超", "Tunisian Ligue Professionnelle 1": "突尼甲",
    "K League 1": "K1", "Ligue 1": "法甲", "Ligue 2": "法乙",
    "Premier League": "英超", "Scottish Premiership": "苏超", "Eredivisie": "荷甲",
    "Segunda División": "西乙", "Serie A": "意甲", "Pro League": "比甲",
    "Parva Liga": "保甲", "Ekstraklasa": "波甲", "Trendyol Super Lig": "土超",
    "Veikkausliiga": "芬超",
}
def lg_cn(lid):
    name, country = leagues.get(lid, ("", ""))
    return _LM.get(name) or LG_CN.get(name) or name or ("未知%d" % lid)

matches = []
for e in all_ev:
    try:
        ko = datetime.fromisoformat(e["event_date"].replace("Z", "+00:00"))
    except Exception:
        continue
    if ko < now - timedelta(minutes=30):
        continue  # 过滤已开赛/已结束
    ko8 = ko.astimezone(timezone(timedelta(hours=8)))
    matches.append({
        "id": e["id"], "league": lg_cn(e.get("league_id")),
        "league_id": e.get("league_id"), "league_en": leagues.get(e.get("league_id"), ("", ""))[0],
        "home": e["home_team"], "away": e["away_team"],
        "home_id": e.get("home_team_id"), "away_id": e.get("away_team_id"),
        "kickoff": ko8.strftime("%m-%d %H:%M"), "kickoff_iso": e["event_date"],
    })
matches.sort(key=lambda m: m["kickoff_iso"])
by_lg = collections.Counter(m["league"] for m in matches)
now8 = now.astimezone(timezone(timedelta(hours=8))).strftime("%m-%d %H:%M")
print("title: %s" % title)
print("window: %s ~ +%dh | total: %d | leagues: %d" % (now8, hours, len(matches), len(by_lg)))
for lg, n in by_lg.most_common():
    print("  %-8s %d" % (lg, n))

now8 = now.astimezone(timezone(timedelta(hours=8)))
out = {"title": title,
       "window_hours": hours,
       "window_start": now8.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
       "window_end": (now8 + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
       "n_matches": len(matches), "n_leagues": len(by_lg), "n_teams": len({m["home"] for m in matches} | {m["away"] for m in matches}),
       "matches": matches}
fn = "scan%dh_%s.json" % (hours, datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M"))
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
lines = []
for m in matches:
    lines.append("%s | %s %s vs %s" % (m["home"], m["kickoff"], m["league"], m["away"]))
    lines.append("%s | %s %s vs %s" % (m["away"], m["kickoff"], m["league"], m["home"]))
tn = "scan%dh_teams_%s.txt" % (hours, datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M"))
io.open(ROOT + r"\analysis_records\\" + tn, "w", encoding="utf-8").write("\n".join(lines))
print("saved -> analysis_records/%s" % fn)
print("saved -> analysis_records/%s" % tn)
