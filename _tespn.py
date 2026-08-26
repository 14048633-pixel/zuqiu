import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer'
for league, date in (('chi.1','20260824'), ('ita.2','20260824'), ('fin.1','20260823')):
    try:
        u = '%s/%s/scoreboard?dates=%s' % (BASE, league, date)
        r = requests.get(u, headers={'User-Agent':'Mozilla/5.0'}, timeout=30)
        print(league, r.status_code)
        d = r.json()
        for ev in (d.get('events') or [])[:10]:
            comp = ev['competitions'][0]
            teams = {t['homeAway']: t['team']['displayName'] for t in comp['competitors']}
            score = {t['homeAway']: t.get('score') for t in comp['competitors']}
            st = ev.get('status',{}).get('type',{}).get('description')
            print('  ', teams.get('home'), 'vs', teams.get('away'), '|', score.get('home'), score.get('away'), '|', st)
    except Exception as e:
        print(league, 'ERR', repr(e)[:120])
