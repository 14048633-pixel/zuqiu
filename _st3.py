import json, io, sys, re, unicodedata, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
KEY = env['ODDS_API_KEY_6']
def deaccent(s):
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s if not unicodedata.combining(c))
def tokens(s):
    return set(re.findall(r'[a-z]{3,}', deaccent(s).lower()))
# 德女足
u = 'https://api.the-odds-api.com/v4/sports/soccer_germany_bundesliga_women/scores/?apiKey=%s&daysFrom=2&dateFormat=iso' % KEY
r = requests.get(u, headers={'Accept':'application/json'}, timeout=40)
for ev in r.json():
    if 'Leipzig' in (ev.get('home_team') or '') or 'Hamburg' in (ev.get('home_team') or ''):
        sc = {s['name']: s['score'] for s in (ev.get('scores') or [])}
        print('WOMEN:', ev.get('home_team'), 'vs', ev.get('away_team'), sc, 'completed:', ev.get('completed'))
# BSD 法甲 Rennes/PSG
d = requests.get(BASE + '/api/v2/events/?league_id=6&status=finished&date_from=2026-08-22&date_to=2026-08-26', headers=H, timeout=40).json()
for ev in (d.get('results') or []):
    h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
    if 'Rennes' in h or 'Rennes' in a or 'Saint Germain' in h or 'Saint Germain' in a:
        print('L1:', h, 'vs', a, ev.get('home_score'), ev.get('away_score'))
