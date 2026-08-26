# -*- coding: utf-8 -*-
import json, io, sys, re, unicodedata, time, collections
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import requests
sys.path.insert(0, 'D:/足球分析/prediction_v2')
from settle_batch import settle_leg, pnl_for_result

ROOT = 'D:/足球分析'
BJT = timezone(timedelta(hours=8))
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open(ROOT + '/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H_BSD = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
KEY_ODDS = env['ODDS_API_KEY_6']
BASE_ODDS = 'https://api.the-odds-api.com/v4'

BSD_LEAGUE = {'土超':11,'意甲':4,'巴甲':9,'巴乙':34,'西甲':3,'西乙':38,'波甲':25,'中超':52,
 '瑞超':26,'丹超':84,'英超':1,'德国杯':43,'比甲':14,'葡超':2,'芬超':55}
ODDS_SPORT = {'智利甲':'soccer_chile_campeonato','意乙':'soccer_italy_serie_b','芬超':'soccer_finland_veikkausliiga'}

def deaccent(s):
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s if not unicodedata.combining(c))
def tokens(s):
    return set(re.findall(r'[a-z]{3,}', deaccent(s).lower()))

def bsd_events(lid, d1, d2):
    out, off = [], 0
    while True:
        u = (BASE + '/api/v2/events/?league_id=%d&status=finished&date_from=%s&date_to=%s&limit=100&offset=%d'
             % (lid, d1, d2, off))
        d = requests.get(u, headers=H_BSD, timeout=40).json()
        rows = d.get('results') or []
        out.extend(rows)
        if not d.get('next') or not rows: break
        off += len(rows)
    return out

def odds_scores(sport):
    u = '%s/sports/%s/scores/?apiKey=%s&daysFrom=2&dateFormat=iso' % (BASE_ODDS, sport, KEY_ODDS)
    r = requests.get(u, headers={'Accept': 'application/json'}, timeout=40)
    return r.json() if r.status_code == 200 else []

# ---- 出单场次 ----
scan = json.load(io.open(ROOT + '/analysis_records/20260823_scan_upcoming.json', encoding='utf-8'))
w0 = datetime(2026, 8, 23, 20, 0, tzinfo=BJT); w1 = datetime(2026, 8, 24, 13, 0, tzinfo=BJT)
sel = [m for m in scan['matches'] if w0 <= datetime.fromisoformat(m['ct'].replace('Z','+00:00')).astimezone(BJT) <= w1]
st = [m for m in sel if m['result'].get('best_bet')]

# ---- BSD 拉取 ----
ev_idx = collections.defaultdict(list)
for lid in sorted({BSD_LEAGUE[m['league']] for m in st if m['league'] in BSD_LEAGUE}):
    try:
        ev_idx[lid] = bsd_events(lid, '2026-08-22', '2026-08-25')
    except Exception as e:
        print('BSD lid', lid, 'ERR', repr(e)[:80])
    time.sleep(0.3)

def bsd_score(m):
    lid = BSD_LEAGUE.get(m['league'])
    if not lid: return None, None
    hk, ak = tokens(m['home']), tokens(m['away'])
    for ev in ev_idx.get(lid, []):
        h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
        th, ta = tokens(h), tokens(a)
        if th and ta and (th <= hk or hk <= th) and (ta <= ak or ak <= ta):
            return ev.get('home_score'), ev.get('away_score')
    return None, None

# ---- the-odds-api 补 ----
odds_cache = {}
for sport in set(ODDS_SPORT.values()):
    try:
        odds_cache[sport] = odds_scores(sport)
    except Exception as e:
        print('odds', sport, 'ERR', repr(e)[:80])
    time.sleep(0.3)

def odds_score(m):
    sport = ODDS_SPORT.get(m['league'])
    if not sport: return None, None
    hk, ak = tokens(m['home']), tokens(m['away'])
    for ev in odds_cache.get(sport, []):
        h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
        th, ta = tokens(h), tokens(a)
        if th and ta and (th <= hk or hk <= th) and (ta <= ak or ak <= ta) and ev.get('completed'):
            sc = ev.get('scores') or []
            hs = as_ = None
            for s in sc:
                if s.get('name') == ev.get('home_team'): hs = s.get('score')
                if s.get('name') == ev.get('away_team'): as_ = s.get('score')
            if hs is not None and as_ is not None:
                return int(hs), int(as_)
    return None, None

# ---- 汇总结算 ----
rows = []
for m in sorted(st, key=lambda x: x['ct']):
    r = m['result']; bb = r['best_bet']
    ct = datetime.fromisoformat(m['ct'].replace('Z','+00:00')).astimezone(BJT)
    hg, ag = bsd_score(m)
    src = 'BSD'
    if hg is None:
        hg, ag = odds_score(m); src = 'odds'
    if hg is None:
        rows.append(dict(ct=ct, lg=m['league'], h=m['home'], a=m['away'], bet=bb['name'], odds=bb['odds'], ev=bb['ev'], star=r.get('star'), hg=None, ag=None, res='未取到', ret=None, pnl=None, src='-'))
        continue
    res, ret = settle_leg(bb['name'], bb['odds'], hg, ag)
    pnl = pnl_for_result(res, ret)
    rows.append(dict(ct=ct, lg=m['league'], h=m['home'], a=m['away'], bet=bb['name'], odds=bb['odds'], ev=bb['ev'], star=r.get('star'), hg=hg, ag=ag, res=res, ret=ret, pnl=pnl, src=src))

print('%-6s %-5s %-28s %-28s %-14s %6s %6s %-7s %8s' % ('时间','联赛','主队','客队','BEST','比分','EV%','结果','盈亏'))
n_win = n_lose = n_push = n_half = n_miss = 0
pnl_sum = 0.0; stake = 0.0
for o in sorted(rows, key=lambda x: x['ct']):
    sc = '%s-%s' % (o['hg'], o['ag']) if o['hg'] is not None else '--'
    evs = '%+.1f' % (o['ev']*100)
    r_, p = o['res'], o['pnl']
    print('%-6s %-5s %-28s %-28s %-14s %6s %6s %-7s %8s' % (o['ct'].strftime('%H:%M'), o['lg'], o['h'], o['a'], o['bet'], sc, evs, r_, '' if p is None else ('%+.2f' % p)))
    if r_ is None: n_miss += 1; continue
    stake += 1.0
    pnl_sum += (p or 0)
    if r_ == 'win': n_win += 1
    elif r_ == 'half': n_half += 1
    elif r_ == 'push': n_push += 1
    else: n_lose += 1

print('='*120)
print('统计: 中%d / 半赢%d / 走水%d / 错%d / 未取到%d | 总PnL=%+.2f 本金=%d ROI=%+.1f%% (按每注1本金)' % (n_win, n_half, n_push, n_lose, n_miss, pnl_sum, int(stake), pnl_sum/stake*100 if stake else 0))
# 保存
io.open(ROOT + '/analysis_records/20260824_prematch_results.json', 'w', encoding='utf-8').write(json.dumps([{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in o.items()} for o in rows], ensure_ascii=False, indent=1))
print('saved: analysis_records/20260824_prematch_results.json')
