# -*- coding: utf-8 -*-
import json, io, sys, re, unicodedata, time, collections
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import requests
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
ODDS_KEY = env['ODDS_API_KEY_6']; ODDS_BASE = 'https://api.the-odds-api.com/v4'
BSD_LEAGUE = {'土超':11,'意甲':4,'巴甲':9,'巴乙':34,'西甲':3,'西乙':38,'波甲':25,'中超':52,'瑞超':26,
 '丹超':84,'英超':1,'德国杯':43,'比甲':14,'葡超':2,'芬超':55,'荷甲':10,'J1':49,'英冠':12,'英乙':87,
 '美职':18,'法甲':6,'法乙':89,'德甲':5,'阿甲':85,'墨超':19,'挪超':54,'K联赛':50,'希腊超':24,
 '瑞士超':None,'瑞甲':None,'俄超':None,'智利甲':None,'意乙':None,'soccer_germany_bundesliga_women':None}
ODDS_SPORT = {'智利甲':'soccer_chile_campeonato','意乙':'soccer_italy_serie_b','俄超':'soccer_russia_premier_league',
 '瑞甲':'soccer_switzerland_superleague','瑞士超':'soccer_switzerland_superleague','德乙':'soccer_germany_bundesliga2',
 '丹超':'soccer_denmark_superliga','芬超':'soccer_finland_veikkausliiga','意杯':'soccer_italy_coppa_italia',
 '沙超':'soccer_saudi_pro_league','英冠':'soccer_efl_champ','挪超':'soccer_norway_eliteserien',
 '德国杯':'soccer_germany_dfb_pokal','葡超':'soccer_portugal_primeira_liga','瑞超':'soccer_sweden_allsvenskan',
 '西甲':'soccer_spain_la_liga','西乙':'soccer_spain_segunda_division','法甲':'soccer_france_ligue_one',
 '中超':'soccer_china_superleague','土超':'soccer_turkey_super_league','巴甲':'soccer_brazil_campeonato',
 '巴乙':'soccer_brazil_serie_b','荷甲':'soccer_netherlands_eredivisie','英超':'soccer_epl','意甲':'soccer_italy_serie_a',
 '阿甲':'soccer_argentina_primera_division','美职':'soccer_usa_mls','墨超':'soccer_mexico_ligamx',
 '波甲':'soccer_poland_ekstraklasa','比甲':'soccer_belgium_first_div','希腊超':'soccer_greece_super_league',
 '丹超':'soccer_denmark_superliga'}
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
    u = '%s/sports/%s/scores/?apiKey=%s&daysFrom=2&dateFormat=iso' % (ODDS_BASE, sport, ODDS_KEY)
    r = requests.get(u, headers={'Accept':'application/json'}, timeout=40)
    return r.json() if r.status_code == 200 else []
# 缺结果场次(昨晚窗口, 已过开赛)
scan = json.load(io.open(r'analysis_records/20260823_scan_upcoming.json', encoding='utf-8'))
CST = timezone(timedelta(hours=8)); now = datetime(2026,8,24,9,10,tzinfo=CST)
w0 = datetime(2026,8,23,20,0,tzinfo=CST); w1 = datetime(2026,8,24,13,0,tzinfo=CST)
sel = [m for m in scan['matches'] if w0 <= datetime.fromisoformat(m['ct'].replace('Z','+00:00')).astimezone(CST) <= w1]
res = { (o['lg'], o['h'], o['a']): o for o in json.load(io.open(r'analysis_records/20260824_prematch_results.json', encoding='utf-8')) }
todo = []
for m in sel:
    k = (m['league'], m['home'], m['away'])
    ct = datetime.fromisoformat(m['ct'].replace('Z','+00:00')).astimezone(CST)
    if k in res and res[k].get('hg') is not None: continue
    if ct <= now:
        todo.append({'league': m['league'], 'home': m['home'], 'away': m['away'], 'ct': m['ct']})
print('已过开赛且缺结果:', len(todo))
# 拉取
ev_idx = {}
for lid in sorted({BSD_LEAGUE[r['league']] for r in todo if BSD_LEAGUE.get(r['league'])}):
    try:
        evs = bsd_events(lid, '2026-08-22', '2026-08-26')
        if evs: ev_idx[lid] = evs
        print('BSD lid', lid, '->', len(evs))
    except Exception as e: print('BSD lid', lid, 'ERR', repr(e)[:60])
    time.sleep(0.2)
scores_idx = {}
for sport in {ODDS_SPORT[r['league']] for r in todo if r['league'] in ODDS_SPORT}:
    try:
        evs = odds_scores(sport)
        if evs: scores_idx[sport] = evs
        print('ODDS', sport, '->', len(evs))
    except Exception as e: print('ODDS', sport, 'ERR', repr(e)[:60])
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
            if hs is not None and as_ is not None: return (int(hs), int(as_), ev.get('home_team'), ev.get('away_team'))
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
            if hs is not None and as_ is not None: return (int(hs), int(as_), ev.get('home_team'), ev.get('away_team'))
    return None
got, still = [], []
for r in todo:
    sc = bsd_score(r) or odds_score(r)
    if sc: got.append({**r, 'score': '%d-%d' % (sc[0], sc[1])})
    else: still.append(r)
print('补齐:', len(got), '仍缺:', len(still))
by = collections.Counter(r['league'] for r in still)
print('仍缺按联赛:', dict(by.most_common(20)))
io.open('_win55_filled.json','w',encoding='utf-8').write(json.dumps(got, ensure_ascii=False, indent=1))
io.open('_win55_still.json','w',encoding='utf-8').write(json.dumps(still, ensure_ascii=False, indent=1))
print('saved _win55_filled.json / _win55_still.json')
