import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
d = json.load(io.open(r'strategy_data/league_calib.json', encoding='utf-8'))
print('top keys:', list(d.keys())[:20])
# 打印一个联赛的配置示例
for k in list(d.keys())[:3]:
    print(k, '=', json.dumps(d[k], ensure_ascii=False)[:400])
