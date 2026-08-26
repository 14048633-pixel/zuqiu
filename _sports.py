import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
d = json.load(io.open(r'prediction_v2/output/odds_snapshots/sports.json', encoding='utf-8'))
sports = d if isinstance(d, list) else d.get('sports') or []
soc = [s for s in sports if s.get('group') == 'Soccer']
print('Soccer sports:', len(soc))
for s in sorted(soc, key=lambda x: x.get('key','')):
    print(s.get('key'))
