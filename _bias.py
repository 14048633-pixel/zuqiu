# -*- coding: utf-8 -*-
import json, io, sys, re, unicodedata, time, collections
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import requests
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
LEAGUE_IDS = {'土超':11,'意甲':4,'巴甲':9,'巴乙':34,'西甲':3,'西乙':38,'波甲':25,'中超':52,
 '瑞超':26,'丹超':84,'英超':1,'德国杯':43,'比甲':14,'葡超':2,'芬超':55,'荷甲':10,'J1':49,
 '英冠':12,'英乙':87,'美职':18,'法甲':6,'法乙':89,'德甲':5,'阿甲':85,'墨超':19,'挪超':54,'K联赛':50,'智利甲':None}
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
# ---- 收集场次 (league, home, away, lambda_sum, ou_side) ----
def ou_side_from_bets(bets):
    if not bets: return None
    best = None
    for b in bets:
        if (b.get('name') or '').startswith(('大','小')):
            if best is None or (b.get('ev') or -9) > (best.get('ev') or -9):
                best = b
    return (best.get('name'), best.get('ev')) if best else None
recs = []
# 1) 2136 扫描
d1 = json.load(io.open('D:/足球分析/analysis_records/scan24h_analysis_20260822_2136.json', encoding='utf-8'))
for m in d1['matches']:
    lam = (m.get('lambda') or {}).get('sum')
    if lam is None: continue
    ou = ou_side_from_bets(m.get('bets'))
    recs.append({'league': m['league'], 'home': m['home'], 'away': m['away'], 'lam': lam, 'ou': ou})
# 2) 1824 扫描
d2 = json.load(io.open('D:/足球分析/analysis_records/scan24h_analysis_20260823_1824.json', encoding='utf-8'))
for m in d2['matches']:
    r = m.get('result') or {}
    lam = (r.get('lambda') or {}).get('sum')
    if lam is None: continue
    ou = ou_side_from_bets(r.get('bets'))
    recs.append({'league': m['league'], 'home': m['home'], 'away': m['away'], 'lam': lam, 'ou': ou})
print('收集场次(含λ):', len(recs))
lgs = collections.Counter(r['league'] for r in recs)
print('联赛分布:', dict(lgs.most_common(30)))
# ---- BSD 拉比分 ----
lids = {LEAGUE_IDS[r['league']] for r in recs if LEAGUE_IDS.get(r['league'])}
ev_idx = {}
for lid in sorted(x for x in lids if x):
    try: ev_idx[lid] = bsd_events(lid, '2026-08-20', '2026-08-25')
    except Exception as e: print('ERR lid', lid, repr(e)[:60])
    time.sleep(0.25)
def find_score(rec):
    lid = LEAGUE_IDS.get(rec['league'])
    if not lid: return None
    hk, ak = tokens(rec['home']), tokens(rec['away'])
    for ev in ev_idx.get(lid, []):
        h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
        th, ta = tokens(h), tokens(a)
        if th and ta and (th <= hk or hk <= th) and (ta <= ak or ak <= ta):
            hs, as_ = ev.get('home_score'), ev.get('away_score')
            if hs is not None and as_ is not None:
                return int(hs) + int(as_)
    return None
# ---- 汇总 ----
G = defaultdict(lambda: {'n':0,'lam':0.0,'goals':0.0,'ou_n':0,'ou_win':0,'ou_half':0,'ou_push':0,'ou_lose':0,'big':0,'small':0,'big_ok':0,'small_ok':0})
for r in recs:
    tot = find_score(r)
    if tot is None: continue
    g = G[r['league']]
    g['n'] += 1; g['lam'] += r['lam']; g['goals'] += tot
    if r['ou']:
        name, ev = r['ou']
        side = name[0]
        g['ou_n'] += 1
        if side=='大': g['big'] += 1
        else: g['small'] += 1
        # 命中: 大 -> tot>2.5; 小 -> tot<2.5 (简化按2.5盘)
        m2 = re.match(r'^(大|小)([\d.]+)', name)
        line = float(m2.group(2)) if m2 else 2.5
        ok = None
        if side=='大': ok = tot > line
        else: ok = tot < line
        if ok is True:
            g['ou_win'] += 1
            if side=='大': g['big_ok'] += 1
            else: g['small_ok'] += 1
        elif ok is False:
            g['ou_lose'] += 1
        else:
            g['ou_push'] += 1
print('='*118)
print('%-6s %4s %7s %7s %7s %7s %6s %6s  %8s  %4s %4s %6s' % ('联赛','场','λ均值','实际均值','偏差','命中率','大','小','大中','小中','中','错'))
res = []
for lg, g in G.items():
    lam_avg = g['lam']/g['n']; act_avg = g['goals']/g['n']; bias = lam_avg - act_avg
    hit = (g['ou_win'] + g['ou_half']*0.5) / g['ou_n'] * 100 if g['ou_n'] else 0
    res.append((lg, g, lam_avg, act_avg, bias, hit))
for lg, g, la, aa, bias, hit in sorted(res, key=lambda x: x[4], reverse=True):
    print('%-6s %4d %7.2f %7.2f %+6.2f %6.1f%% %6d %6d  %4d/%-4d %4d/%-4d %4d %4d' % (lg, g['n'], la, aa, bias, hit, g['big'], g['small'], g['big_ok'], g['big'], g['small_ok'], g['small'], g['ou_win'], g['ou_lose']))
