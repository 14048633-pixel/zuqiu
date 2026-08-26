# -*- coding: utf-8 -*-
"""扫描指定窗口比赛 (BJT): _scan_window.py --from '2026-08-21 08:00' --to '2026-08-22 08:00'"""
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

ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="frm", default="2026-08-21 08:00")
ap.add_argument("--to", dest="to", default="2026-08-22 08:00")
args = ap.parse_args()
BJT = timezone(timedelta(hours=8))
w0 = datetime.strptime(args.frm, "%Y-%m-%d %H:%M").replace(tzinfo=BJT)
w1 = datetime.strptime(args.to, "%Y-%m-%d %H:%M").replace(tzinfo=BJT)
d_from = w0.astimezone(timezone.utc).strftime("%Y-%m-%d")
d_to = (w1.astimezone(timezone.utc)).strftime("%Y-%m-%d")

leagues = {}
for x in (get("/leagues/?limit=200").get("results") or []):
    leagues[x["id"]] = (x.get("name") or "", x.get("country") or "")

all_ev = []
offset = 0
while True:
    j = get("/events/?status=upcoming&date_from=%s&date_to=%s&limit=200&offset=%d" % (d_from, d_to, offset))
    res = j.get("results") or []
    all_ev += res
    if len(res) < 200: break
    offset += 200

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
}
def lg_cn(lid):
    name, country = leagues.get(lid, ("", ""))
    return LG_CN.get(name, name or ("未知%d" % lid))

now = datetime.now(timezone.utc)
matches = []
for e in all_ev:
    try:
        ko = datetime.fromisoformat(e["event_date"].replace("Z", "+00:00"))
    except Exception:
        continue
    if ko < now - timedelta(minutes=30): continue
    if not (w0.astimezone(timezone.utc) <= ko < w1.astimezone(timezone.utc)): continue
    ko8 = ko.astimezone(BJT)
    matches.append({
        "id": e["id"], "league": lg_cn(e.get("league_id")),
        "league_id": e.get("league_id"), "league_en": leagues.get(e.get("league_id"), ("", ""))[0],
        "home": e["home_team"], "away": e["away_team"],
        "home_id": e.get("home_team_id"), "away_id": e.get("away_team_id"),
        "kickoff": ko8.strftime("%m-%d %H:%M"), "kickoff_iso": e["event_date"],
    })
matches.sort(key=lambda m: m["kickoff_iso"])
by_lg = collections.Counter(m["league"] for m in matches)
print("window: %s ~ %s | total: %d | leagues: %d" % (args.frm, args.to, len(matches), len(by_lg)))
for lg, n in by_lg.most_common():
    print("  %-10s %d" % (lg, n))

out = {"window_start": args.frm, "window_end": args.to,
       "n_matches": len(matches), "n_leagues": len(by_lg),
       "n_teams": len({m["home"] for m in matches} | {m["away"] for m in matches}),
       "matches": matches}
fn = "scan48h_%s.json" % datetime.now(BJT).strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
lines = []
for m in matches:
    lines.append("%s | %s %s vs %s" % (m["home"], m["kickoff"], m["league"], m["away"]))
    lines.append("%s | %s %s vs %s" % (m["away"], m["kickoff"], m["league"], m["home"]))
tn = "scan48h_teams_%s.txt" % datetime.now(BJT).strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + tn, "w", encoding="utf-8").write("\n".join(lines))
print("saved -> analysis_records/%s" % fn)
print("saved -> analysis_records/%s" % tn)
