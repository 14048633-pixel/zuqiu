# -*- coding: utf-8 -*-
import json, io, sys, re, unicodedata, time, collections
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import requests

ROOT = 'D:/足球分析'
BJT = timezone(timedelta(hours=8))
BASE = 'https://sports.bzzoiro.com'
TOK = ''
for l in io.open(ROOT + '/.env', encoding='utf-8-sig'):
    if l.startswith('BZZOIRO_API_KEY='):
        TOK = l.split('=', 1)[1].strip().strip('"').strip("'")
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + TOK}

LEAGUE_IDS = {
 '土超': 11, '意甲': 4, '巴甲': 9, '巴乙': 34, '西甲': 3, '西乙': 38,
 '智利甲': 85, '波甲': 25, '中超': 52, '瑞超': 26, '丹超': 84, '英超': 1,
 '德国杯': 43, '比甲': 14, '葡超': 2, '芬超': 55, '希腊超': 24, '阿甲': 85,
 '英冠': 12, '英乙': 87, '美职': 18,
}
def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())
def tokens(s):
    return set(re.findall(r'[a-z]{3,}', (s or '').lower()))

def bsd_events(lid, date_from, date_to):
    out, off = [], 0
    while True:
        u = (BASE + '/api/v2/events/?league_id=%d&status=finished&date_from=%s&date_to=%s&limit=100&offset=%d'
             % (lid, date_from, date_to, off))
        r = requests.get(u, headers=HEADERS, timeout=40)
        d = r.json()
        rows = d.get('results') or []
        out.extend(rows)
        if not d.get('next') or not rows:
            break
        off += len(rows)
    return out

# 出单场次
scan = json.load(io.open(ROOT + '/analysis_records/20260823_scan_upcoming.json', encoding='utf-8'))
w0 = datetime(2026, 8, 23, 20, 0, tzinfo=BJT)
w1 = datetime(2026, 8, 24, 13, 0, tzinfo=BJT)
sel = [m for m in scan['matches'] if w0 <= datetime.fromisoformat(m['ct'].replace('Z','+00:00')).astimezone(BJT) <= w1]
st = [m for m in sel if m['result'].get('best_bet')]
print('出单场次:', len(st))

# 按联赛聚合拉取
date_from = '2026-08-23T00:00:00Z'
date_to = '2026-08-24T23:59:59Z'
ev_index = collections.defaultdict(list)
lids = {LEAGUE_IDS.get(m['league']) for m in st}
for lid in sorted(x for x in lids if x):
    try:
        evs = bsd_events(lid, date_from, date_to)
        ev_index[lid] = evs
        print('league_id=%d finished=%d' % (lid, len(evs)))
    except Exception as e:
        print('league_id=%d ERR %r' % (lid, e))
    time.sleep(0.5)

# 匹配
out = []
for m in sorted(st, key=lambda x: x['ct']):
    lid = LEAGUE_IDS.get(m['league'])
    hk = tokens(m['home']); ak = tokens(m['away'])
    best = None
    for ev in ev_index.get(lid, []):
        h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
        th, ta = tokens(h), tokens(a)
        if (th and ak and (th <= ak or ak <= th) and ta and (ta <= hk or hk <= ta)):
            best = ev; break
    r = m['result']; bb = r['best_bet']
    ct = datetime.fromisoformat(m['ct'].replace('Z','+00:00')).astimezone(BJT)
    if best is None:
        out.append((ct, m['league'], m['home'], m['away'], bb['name'], None, '未匹配'))
        continue
    hs = best.get('home_score'); as_ = best.get('away_score')
    if hs is None:
        sc = best.get('score') or ''
        mm = re.match(r'(\d+)\s*[-:]\s*(\d+)', sc)
        if mm: hs, as_ = int(mm.group(1)), int(mm.group(2))
    out.append((ct, m['league'], m['home'], m['away'], bb['name'], (hs, as_), '%s %s' % (hs, as_)))

for o in sorted(out, key=lambda x: x[0]):
    print('[%s] %s %s vs %s | BEST=%s | 比分=%s' % (o[0].strftime('%m-%d %H:%M'), o[1], o[2], o[3], o[4], o[6]))
