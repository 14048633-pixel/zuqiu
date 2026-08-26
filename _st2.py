import json, io, sys, re, unicodedata, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
KEY = env['ODDS_API_KEY_6']
def deaccent(s):
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s if not unicodedata.combining(c))
def tokens(s):
    return set(re.findall(r'[a-z]{3,}', deaccent(s).lower()))
def scores(sport):
    u = 'https://api.the-odds-api.com/v4/sports/%s/scores/?apiKey=%s&daysFrom=2&dateFormat=iso' % (sport, KEY)
    r = requests.get(u, headers={'Accept':'application/json'}, timeout=40)
    return r.json() if r.status_code==200 else []
def find(sport, home, away):
    hk, ak = tokens(home), tokens(away)
    for ev in scores(sport):
        h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
        th, ta = tokens(h), tokens(a)
        if th and ta and (th <= hk or hk <= th) and (ta <= ak or ak <= ta):
            sc = ev.get('scores') or []
            hs = as_ = None
            for s in sc:
                if s.get('name')==ev.get('home_team'): hs=s.get('score')
                if s.get('name')==ev.get('away_team'): as_=s.get('score')
            print(' ', sport, '->', ev.get('home_team'), 'vs', ev.get('away_team'), hs, as_, 'completed:', ev.get('completed'))
            return
    print(' ', sport, '未找到', home, 'vs', away)
find('soccer_sweden_superettan', 'IK Brage', 'Nordic United FC')
find('soccer_sweden_superettan', 'Norrby IF', 'Sandvikens IF')
find('soccer_france_ligue_one', 'Paris Saint Germain', 'Rennes')
# 德女足 sport key 探测
u = 'https://api.the-odds-api.com/v4/sports/?apiKey=%s' % KEY
r = requests.get(u, headers={'Accept':'application/json'}, timeout=40)
for s in r.json():
    if 'women' in s.get('key','').lower() or 'frauen' in s.get('key','').lower() or ('germany' in s.get('key','') and 'bundes' in s.get('key','')):
        print('GER women?', s.get('key'), '|', s.get('title'), '| active:', s.get('active'))
