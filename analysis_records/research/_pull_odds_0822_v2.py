# -*- coding: utf-8 -*-
"""08-22 凌晨 27 场最新赔率: the-odds-api(13联赛23场) + API-Football(4场兜底)"""
import sys, os, json, io, time, unicodedata, urllib.request
from datetime import datetime, timezone
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
from live_odds import fetch_league_odds

OUT = os.path.join(ROOT, "analysis_records", "research")
clean = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan48h_20260821_0048_clean.json"), encoding="utf-8"))
TARGET_LEAGUE_SPORT = {
    "沙超": "soccer_saudi_arabia_pro_league",
    "DFB Pokal": "soccer_germany_dfb_pokal",
    "Veikkausliiga": "soccer_finland_veikkausliiga",
    "Allsvenskan": "soccer_sweden_allsvenskan",
    "Liga Profesional de Fútbol": "soccer_argentina_primera_division",
    "Ligue 2": "soccer_france_ligue_two",
    "Trendyol Super Lig": "soccer_turkey_super_league",
    "Ekstraklasa": "soccer_poland_ekstraklasa",
    "Pro League": "soccer_belgium_first_div",
    "Ligue 1": "soccer_france_ligue_one",
    "Segunda División": "soccer_spain_segunda_division",
    "La Liga": "soccer_spain_la_liga",
    "Premier League": "soccer_epl",
}
targets = []
for m in clean["matches"]:
    if m["kickoff"].startswith("08-22"):
        targets.append(m)
print("targets:", len(targets))

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).lower()
    for w in ("fc", "cf", "sc", "ac", "as", "us", "cd", "de", "sd", "ud", "ssc", "gnk", "ca", "esg", "fk", "ks", "sk", "sf", "if", "ik", "bk"):
        s = (" " + s + " ").replace(" " + w + " ", " ").strip()
    return " ".join(s.split())

def side_ok(a, b):
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return False
    return a == b or sa <= sb or sb <= sa or len(sa & sb) / len(sa | sb) >= 0.6

def find_event(events, t):
    ko = t["kickoff_iso"].replace("+00:00", "Z")
    for ev in events:
        ct = ev.get("commence_time") or ""
        try:
            d = abs((datetime.fromisoformat(ct.replace("Z", "+00:00")) - datetime.fromisoformat(t["kickoff_iso"].replace("Z", "+00:00"))).total_seconds())
        except Exception:
            continue
        if d > 3600:
            continue
        if side_ok(norm(t["home"]), norm(ev.get("home_team"))) and side_ok(norm(t["away"]), norm(ev.get("away_team"))):
            return ev
    return None

KEY = "8365acfd25968d4917f29474c2df5b2c"
ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
results = {}
sports_done = {}
# ---- Part A: the-odds-api 按联赛 ----
by_sport = {}
for t in targets:
    sp = TARGET_LEAGUE_SPORT.get(t["league"])
    if sp:
        by_sport.setdefault(sp, []).append(t)
print("sports:", {k: len(v) for k, v in by_sport.items()})
for sp, tlist in by_sport.items():
    events, quota = fetch_league_odds(KEY, sp, markets="h2h,spreads,totals", regions="eu,uk,us", timeout=60)
    print("sport", sp, "n_events:", len(events), "quota_rem:", quota.get("remaining"))
    sports_done[sp] = {"n_events": len(events), "quota": quota, "pulled_at": ts}
    for t in tlist:
        ev = find_event(events, t)
        if ev is None:
            print("  NO MATCH:", t["id"], t["home"], "vs", t["away"])
        else:
            results[str(t["id"])] = {"source": "the-odds-api", "sport": sp, "pulled_at": ts,
                                     "home_team": ev["home_team"], "away_team": ev["away_team"],
                                     "commence_time": ev.get("commence_time"),
                                     "bookmakers": ev.get("bookmakers") or []}
            print("  OK:", t["id"], t["home"], "vs", t["away"], "<->", ev["home_team"], "vs", ev["away_team"], "bk:", len(ev.get("bookmakers") or []))
    time.sleep(1.0)

# ---- Part B: API-Football 兜底 4 场 ----
AFB_KEY = "FOOTBALL_API_KEY_FROM_ENV"
fixture_map = {m["home"]: m for m in json.load(io.open(os.path.join(ROOT, "analysis_records", "apifb_fixture_map_20260821.json"), encoding="utf-8"))["matches"]}
fallback = []
for t in targets:
    if str(t["id"]) not in results:
        fm = fixture_map.get(t["home"])
        fallback.append((t, fm))
print("fallback:", [(t["home"], fm["fixture_id"] if fm else None) for t, fm in fallback])
for t, fm in fallback:
    if not fm:
        print("  NO FIXTURE MAP:", t["home"]); continue
    fid = fm["fixture_id"]
    url = "https://v3.football.api-sports.io/odds?fixture=%d" % fid
    req = urllib.request.Request(url, headers={"x-apisports-key": AFB_KEY})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
            rem = r.headers.get("x-ratelimit-remaining")
            print("  AFB ok", fid, t["home"], "quota_rem:", rem)
            resp = body.get("response") or []
            results[str(t["id"])] = {"source": "api-football", "sport": "apifb", "pulled_at": ts,
                                     "home_team": t["home"], "away_team": t["away"],
                                     "commence_time": t["kickoff_iso"],
                                     "bookmakers": resp}
    except Exception as e:
        print("  AFB ERR", fid, t["home"], repr(e))
    time.sleep(2.0)

out_fn = os.path.join(OUT, "odds_live_0822_matched_v2.json")
json.dump({"pulled_at": ts, "n_matched": len(results), "matches": results, "sports_done": sports_done},
          io.open(out_fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved:", out_fn, "n_matched:", len(results))
