# -*- coding: utf-8 -*-
import sys, io, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE='https://site.api.espn.com/apis/site/v2/sports/soccer'
codes=['jpn.emperor','jpn.1','jpn.2','jpn.3','kor.1','jpn.league_cup','jpn.cup','intl.japan']
for c in codes:
    for dt in ('20260826','20260825'):
        try:
            r=requests.get('%s/%s/scoreboard?dates=%s'%(BASE,c,dt),headers={'User-Agent':'Mozilla/5.0'},timeout=25)
            if r.status_code!=200:
                print(c,dt,'HTTP',r.status_code); continue
            d=r.json(); evs=d.get('events') or []
            if not evs: continue
            print('==',c,dt,'n=',len(evs))
            for ev in evs[:40]:
                try:
                    comp=ev['competitions'][0]
                    teams={t['homeAway']:t['team']['displayName'] for t in comp['competitors']}
                    scores={t['homeAway']:t.get('score') for t in comp['competitors']}
                    st=ev.get('status',{}).get('type',{}).get('state')
                    stt=ev.get('status',{}).get('type',{}).get('detail','')
                    print('   ',teams.get('home'),'vs',teams.get('away'),'|',scores.get('home'),scores.get('away'),'|',st,stt)
                except Exception: pass
        except Exception as e:
            print(c,dt,'ERR',repr(e)[:80])
