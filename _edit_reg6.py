# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\regression_test.py"
s = io.open(P, encoding="utf-8").read()
repl = [
    ('check("中超league_calib(开季校准)", round(su.CAL.get("中超", {}).get("league_avg"), 3), 3.518)',
     'check("中超league_calib(基准对齐)", round(su.CAL.get("中超", {}).get("league_avg"), 3), 3.04)'),
    ('check("葡超league_calib(开季校准)", round(su.CAL.get("葡超", {}).get("league_avg", 0), 2), 2.84)',
     'check("葡超league_calib(基准对齐)", round(su.CAL.get("葡超", {}).get("league_avg", 0), 2), 2.63)'),
    ('check("中超league_avg=3.518(开季校准)", round(c["league_avg"], 3), 3.518)',
     'check("中超league_avg=3.04(基准对齐)", round(c["league_avg"], 3), 3.04)'),
]
cnt = 0
for o, n in repl:
    if o in s:
        s = s.replace(o, n); cnt += 1
    else:
        print("未找到:", o[:70])
# mock: 中超 (3.518, 30) -> (3.04, 30)  共6处
c1 = s.count('"中超": (3.518, 30)')
s = s.replace('"中超": (3.518, 30)', '"中超": (3.04, 30)')
# mock: 英冠 (2.55, 30) -> (2.51, 30)
c2 = s.count('"英冠": (2.55, 30)')
s = s.replace('"英冠": (2.55, 30)', '"英冠": (2.51, 30)')
io.open(P, "w", encoding="utf-8").write(s)
print("值断言替换:", cnt, "/3 | 中超mock替换:", c1, "处 | 英冠mock替换:", c2, "处")
