import sys, io, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
for url in ('https://sports.bzzoiro.com/docs/football/events.md', 'https://sports.bzzoiro.com/docs/football/teams-players.md'):
    try:
        r = requests.get(url, timeout=30)
        print('===', url.split('/')[-1], r.status_code)
        print(r.text[:3000])
    except Exception as e:
        print(url, 'ERR', repr(e)[:100])
