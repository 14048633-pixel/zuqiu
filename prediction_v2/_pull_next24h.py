# -*- coding: utf-8 -*-
"""拉取 2026-08-24 23:00 BJT -> 08-25 23:00 BJT 窗口赔率(the-odds-api 逐联赛) -> 追加 snapshots.csv"""
import os, sys, io, json, time, urllib.request, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import live_odds
from odds.api_router import OddsApiRouter

SNAP = os.path.join(HERE, "output", "odds_snapshots", "snapshots.csv")
API_BASE = "https://api.the-odds-api.com/v4"
FROM = "2026-08-24T14:00:00Z"
TO = "2026-08-25T15:00:00Z"

SPORT_CN = {v: k for k, v in live_odds.LEAGUE_SPORT_KEYS.items()}
SPORT_CN.update({
    "soccer_russia_premier_league": "俄超",
    "soccer_saudi_arabia_pro_league": "沙超",
    "soccer_greece_super_league": "希腊超",
    "soccer_switzerland_superleague": "瑞士超",
    "soccer_austria_bundesliga": "奥甲",
    "soccer_spl": "苏超",
    "soccer_league_of_ireland": "爱超",
    "soccer_australia_aleague": "澳超",
    "soccer_korea_kleague1": "K联赛",
    "soccer_england_league1": "英甲",
    "soccer_germany_liga3": "德丙",
    "soccer_italy_serie_b": "意乙",
    "soccer_brazil_serie_b": "巴乙",
    "soccer_sweden_superettan": "瑞甲",
    "soccer_poland_ekstraklasa": "波甲",
    "soccer_finland_veikkausliiga": "芬超",
    "soccer_china_superleague": "中超",
    "soccer_germany_dfb_pokal": "德国杯",
    "soccer_italy_coppa_italia": "意大利杯",
    "soccer_england_efl_cup": "英联杯",
    "soccer_france_coupe_de_france": "法国杯",
    "soccer_spain_copa_del_rey": "国王杯",
    "soccer_conmebol_copa_libertadores": "解放者杯",
    "soccer_conmebol_copa_sudamericana": "南美杯",
    "soccer_uefa_champs_league": "欧冠",
    "soccer_uefa_europa_league": "欧联",
    "soccer_uefa_europa_conference_league": "欧协联",
    "soccer_uefa_champs_league_qualification": "欧冠资格赛",
    "soccer_africa_cup_of_nations": "非洲杯",
    "soccer_concacaf_leagues_cup": "中北美联赛杯",
})

def datetime_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    router = OddsApiRouter(project_root=ROOT, base_dir=HERE)
    pool = list(router.keys)
    all_rows = []
    try:
        sp_url = API_BASE + "/sports/?apiKey=%s&all=true" % pool[0][0]
        sp = json.loads(urllib.request.urlopen(urllib.request.Request(sp_url, headers={"Accept": "application/json"}), timeout=30).read().decode("utf-8", "replace"))
        sports = sorted(s["key"] for s in sp if s["key"].startswith("soccer"))
    except Exception as ex:
        print("sports列表失败: %r" % ex)
        sports = sorted(live_odds.LEAGUE_SPORT_KEYS.values())

    idx = 0; ok_cnt = fail_cnt = 0
    for sk in sports:
        lg = SPORT_CN.get(sk, sk)
        got = False
        for _ in range(len(pool)):
            key, src = pool[idx % len(pool)]
            idx += 1
            try:
                url = (API_BASE + "/sports/%s/odds?apiKey=%s&regions=eu&markets=h2h,spreads,totals"
                       "&oddsFormat=decimal&dateFormat=iso&commenceTimeFrom=%s&commenceTimeTo=%s" % (sk, key, FROM, TO))
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    rem = resp.headers.get("x-requests-remaining", "0")
                    data = json.loads(resp.read().decode("utf-8", "replace"))
                rows = live_odds.flatten_events(data, lg, datetime_now())
                all_rows.extend(rows)
                ok_cnt += 1
                print("OK %-42s %s rows=%d quota_rem=%s" % (sk, lg, len(data), rem))
                got = True
                break
            except urllib.error.HTTPError as ex:
                if ex.code == 404:
                    print("EMPTY %-42s %s (无比赛)" % (sk, lg))
                    got = True
                    break
                print("KEYFAIL %s HTTP %s -> 换key" % (src, ex.code))
            except Exception as ex:
                print("KEYFAIL %s %r -> 换key" % (src, ex))
        if not got:
            print("FAIL %-42s %s (全部key失败)" % (sk, lg))
            fail_cnt += 1
        time.sleep(0.4)

    if all_rows:
        live_odds.append_snapshots(SNAP, all_rows)
        print("\nTOTAL appended:", len(all_rows), "->", SNAP)
    else:
        print("\nnothing appended")
    print("OK联赛=%d FAIL=%d" % (ok_cnt, fail_cnt))
    by_league = collections.Counter(r["league"] for r in all_rows)
    print("按联赛场次(带赔率):", dict(by_league))

if __name__ == "__main__":
    main()
