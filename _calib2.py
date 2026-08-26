import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
d = json.load(io.open(r'strategy_data/league_calib.json', encoding='utf-8'))
leagues = d.get('leagues', {})
print('联赛数:', len(leagues), list(leagues.keys()))
for lg in ('英超','西甲','土超','瑞超','荷甲','德国杯','中超','英冠'):
    if lg in leagues:
        print(lg, '=', json.dumps(leagues[lg], ensure_ascii=False)[:600])
