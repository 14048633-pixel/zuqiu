# -*- coding: utf-8 -*-
import io
p = 'regression_test.py'
s = io.open(p, encoding='utf-8').read()
anchor = '        check("规则③降星后star<=2", r3["star"] <= 2, True)\n    finally:\n        su.recent_league_avg = _orig_avg'
print('anchor count:', s.count(anchor))
assert s.count(anchor) == 1
new = '''        check("规则③降星后star<=2", r3["star"] <= 2, True)

        # ---- 规则④(2026-08-23): 英冠/荷甲 小球反向标记 + 荷甲 league_avg 修正 ----
        check("英冠 ou_under_reverse 开启", su.CAL["英冠"].get("ou_under_reverse"), True)
        check("荷甲 ou_under_reverse 开启", su.CAL["荷甲"].get("ou_under_reverse"), True)
        check("荷甲 league_avg 修正 3.688->3.15", su.CAL["荷甲"].get("league_avg"), 3.15)
        _src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_v2", "scan_upcoming.py"), encoding="utf-8").read()
        check("规则④代码分支存在", "ou_under_reverse" in _src and "联赛小球反向标记" in _src, True)
        _pss = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_settle.py"), encoding="utf-8").read()
        check("settle账本比分字段", "home_score" in _pss and "is_draw" in _pss, True)
    finally:
        su.recent_league_avg = _orig_avg'''
s = s.replace(anchor, new)
io.open(p, 'w', encoding='utf-8').write(s)
print('regression rule4 assertions added')
