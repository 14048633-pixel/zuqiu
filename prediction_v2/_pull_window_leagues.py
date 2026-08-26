# -*- coding: utf-8 -*-
import os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.live_odds import fetch_league_odds, flatten_events, append_snapshots, DEFAULT_MARKETS

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src', 'odds'))
from api_router import OddsApiRouter

LEAGUES = [
    ("J1", "soccer_japan_j_league"),
    ("英超", "soccer_epl"),
    ("西甲", "soccer_spain_la_liga"),
    ("法甲", "soccer_france_ligue_one"),
    ("法乙", "soccer_france_ligue_two"),
    ("瑞超", "soccer_sweden_allsvenskan"),
    ("阿甲", "soccer_argentina_primera_division"),
    ("土超", "soccer_turkey_super_league"),
    ("波甲", "soccer_poland_ekstraklasa"),
    ("比甲", "soccer_belgium_first_div"),
    ("西乙", "soccer_spain_segunda_division"),
    ("芬超", "soccer_finland_veikkausliiga"),
    ("德国杯", "soccer_germany_dfb_pokal"),
    ("解放者杯", "soccer_conmebol_copa_libertadores"),
    ("南美杯", "soccer_conmebol_copa_sudamericana"),
]

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    router = OddsApiRouter(base_dir=HERE, project_root=PROJECT_ROOT)
    out = os.path.join(HERE, "output", "odds_snapshots", "snapshots.csv")
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    all_rows = []
    for lg, sport in LEAGUES:
        sel = router.key_for_league(lg)
        ok = False
        for _ in range(router.max_fail + 1):
            try:
                events, quota = fetch_league_odds(sel["key"], sport, markets=DEFAULT_MARKETS,
                                                  regions="eu,uk", base_url=sel["base_url"])
                rows = flatten_events(events, lg, ts)
                ah = sum(1 for r in rows if r["market"] == "asian_handicap")
                print("%s %s rows=%d asian_handicap=%d quota_rem=%s" % (
                    lg, sport, len(rows), ah, quota.get("remaining")))
                router.mark_success(sel["key"])
                all_rows.extend(rows)
                ok = True
                break
            except Exception as e:
                print("%s %s FAIL: %r" % (lg, sport, e))
                router.mark_failure(sel["key"])
                sel = router.rotate_sel(lg)
        if not ok:
            print("%s FAILED all keys" % lg)
    if all_rows:
        append_snapshots(out, all_rows)
        print("TOTAL appended:", len(all_rows), "->", out)
    else:
        print("nothing pulled")

if __name__ == "__main__":
    main()

