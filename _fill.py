# -*- coding: utf-8 -*-
import json, io, sys, re, unicodedata, time, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import requests
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
ODDS_KEY = env['ODDS_API_KEY_6']
ODDS_BASE = 'https://api.the-odds-api.com/v4'
BSD_LEAGUE = {'土超':11,'意甲':4,'巴甲':9,'巴乙':34,'西甲':3,'西乙':38,'波甲':25,'中超':52,
 '瑞超':26,'丹超':84,'英超':1,'德国杯':43,'比甲':14,'葡超':2,'芬超':55,'荷甲':10,'J1':49,
 '英冠':12,'英乙':87,'美职':18,'法甲':6,'法乙':89,'德甲':5,'阿甲':85,'墨超':19,'挪超':54,
 'K联赛':50,'希腊超':24,'欧联':8,'欧协联':83,'欧冠资格':7,'意杯':42,'沙超':17,'保甲':22}
ODDS_SPORT = {'智利甲':'soccer_chile_campeonato','意乙':'soccer_italy_serie_b','德乙':'soccer_germany_bundesliga2',
 '俄超':'soccer_russia_premier_league','瑞甲':'soccer_switzerland_superleague','瑞士超':'soccer_switzerland_superleague',
 '罗甲':'soccer_league_of_ireland','土超':'soccer_turkey_super_league','丹超':'soccer_denmark_superliga',
 '芬超':'soccer_finland_veikkausliiga','意杯':'soccer_italy_coppa_italia','沙超':'soccer_saudi_pro_league',
 '英冠':'soccer_efl_champ','挪超':'soccer_norway_eliteserien','德国杯':'soccer_germany_dfb_pokal',
 '葡超':'soccer_portugal_primeira_liga','瑞超':'soccer_sweden_allsvenskan','西甲':'soccer_spain_la_liga',
 '西乙':'soccer_spain_segunda_division','法甲':'soccer_france_ligue_one','中超':'soccer_china_superleague'}
def deaccent(s):
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s if not unicodedata.combining(c))
def tokens(s):
    return set(re.findall(r'[a-z]{3,}', deaccent(s).lower()))
def bsd_events(lid, d1, d2):
    out, off = [], 0
    while True:
        u = (BASE + '/api/v2/events/?league_id=%d&status=finished&date_from=%s&date_to=%s&limit=100&offset=%d' % (lid, d1, d2, off))
        d = requests.get(u, headers=H, timeout=40).json()
        rows = d.get('results') or []
        out.extend(rows)
        if not d.get('next') or not rows: break
        off += len(rows)
    return out
def odds_scores(sport):
    u = '%s/sports/%s/scores/?apiKey=%s&daysFrom=4&dateFormat=iso' % (ODDS_BASE, sport, ODDS_KEY)
    r = requests.get(u, headers={'Accept':'application/json'}, timeout=40)
    return r.json() if r.status_code == 200 else []
miss = json.load(io.open('_miss_passed.json', encoding='utf-8'))
print('待补场次:', len(miss))
# ---- BSD 拉取 ----
ev_idx = {}
for lid in sorted({BSD_LEAGUE[r['league']] for r in miss if r['league'] in BSD_LEAGUE}):
    try:
        evs = bsd_events(lid, '2026-08-15', '2026-08-26')
        if evs: ev_idx[lid] = evs
        print('BSD lid', lid, '->', len(evs))
    except Exception as e:
        print('BSD lid', lid, 'ERR', repr(e)[:60])
    time.sleep(0.2)
# ---- the-odds-api 拉取 ----
scores_idx = {}
for sport in {ODDS_SPORT[r['league']] for r in miss if r['league'] in ODDS_SPORT}:
    try:
        evs = odds_scores(sport)
        if evs: scores_idx[sport] = evs
        print('ODDS', sport, '->', len(evs))
    except Exception as e:
        print('ODDS', sport, 'ERR', repr(e)[:60])
    time.sleep(0.2)
def bsd_score(r):
    lid = BSD_LEAGUE.get(r['league'])
    if not lid or lid not in ev_idx: return None
    hk, ak = tokens(r['home']), tokens(r['away'])
    for ev in ev_idx[lid]:
        h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
        th, ta = tokens(h), tokens(a)
        if th and ta and (th <= hk or hk <= th) and (ta <= ak or ak <= ta):
            hs, as_ = ev.get('home_score'), ev.get('away_score')
            if hs is not None and as_ is not None: return (int(hs), int(as_))
    return None
def odds_score(r):
    sport = ODDS_SPORT.get(r['league'])
    if not sport or sport not in scores_idx: return None
    hk, ak = tokens(r['home']), tokens(r['away'])
    for ev in scores_idx[sport]:
        h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
        th, ta = tokens(h), tokens(a)
        if th and ta and (th <= hk or hk <= th) and (ta <= ak or ak <= ta) and ev.get('completed'):
            sc = ev.get('scores') or []
            hs = as_ = None
            for s in sc:
                if s.get('name') == ev.get('home_team'): hs = s.get('score')
                if s.get('name') == ev.get('away_team'): as_ = s.get('score')
            if hs is not None and as_ is not None: return (int(hs), int(as_))
    return None
got, still = [], []
for r in miss:
    sc = bsd_score(r) or odds_score(r)
    if sc: got.append({**r, 'score': '%d-%d' % sc})
    else: still.append(r)
print('补齐:', len(got), '仍缺:', len(still))
by = collections.Counter(r['league'] for r in still)
print('仍缺按联赛:', dict(by.most_common(30)))
io.open('_miss_filled.json','w',encoding='utf-8').write(json.dumps(got, ensure_ascii=False, indent=1))
io.open('_miss_still.json','w',encoding='utf-8').write(json.dumps(still, ensure_ascii=False, indent=1))
print('saved _miss_filled.json / _miss_still.json')
