import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
for tid, tag in ((735,'O Higgins'), (744,'Palestino')):
    for path in ('/api/v2/teams/%d/fixtures/?date_from=2026-08-20&date_to=2026-08-26' % tid,
                 '/api/v2/events/?team_id=%d&status=finished&date_from=2026-08-22&date_to=2026-08-25' % tid,
                 '/api/v2/events/?team_id=%d&date_from=2026-08-22&date_to=2026-08-25' % tid):
        try:
            d = requests.get(BASE + path, headers=H, timeout=40).json()
            rows = d.get('results') or []
            print(tag, path.split('?')[0], 'count=', d.get('count'), 'rows=', len(rows))
            for ev in rows[:3]:
                print('   ', ev.get('home_team'), 'vs', ev.get('away_team'), ev.get('home_score'), ev.get('away_score'), ev.get('status'))
        except Exception as e:
            print(tag, 'ERR', repr(e)[:80])
