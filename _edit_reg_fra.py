# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\regression_test.py"
s = io.open(P, encoding="utf-8").read()
anchor = '        check("方案A墨超负档下调大球>=3pp(强强-5pp)", _diff_mx <= -0.03, True)'
block = anchor + '''
        # 法甲负校准(2026-08-24): 612场拟合模型高估大球总-3.3pp(混合-3.9/弱弱-8.1) -> 负档位下调大球
        _fra_adj = su.CAL.get("法甲", {}).get("ou_strength_adj") or {}
        check("方案A法甲混合负档-0.03", _fra_adj.get("混合"), -0.03)
        check("方案A法甲弱弱负档-0.06", _fra_adj.get("弱弱"), -0.06)
        check("方案A法甲强强反向不配", _fra_adj.get("强强") is None, True)
        _save_fra = su.CAL["法甲"].get("ou_strength_adj")
        m_fra = _mk("Nantes", "Auxerre", "法甲", {"home": 2.0, "draw": 3.4, "away": 3.6},
                    {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
                    {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r_fra_on = su.analyze_match(m_fra, ts, lavg, index)
        su.CAL["法甲"]["ou_strength_adj"] = {}
        r_fra_off = su.analyze_match(m_fra, ts, lavg, index)
        su.CAL["法甲"]["ou_strength_adj"] = _save_fra
        _ov_fra_on = next((b for b in r_fra_on["bets"] if b["name"] == "大2.50"), None)
        _ov_fra_off = next((b for b in r_fra_off["bets"] if b["name"] == "大2.50"), None)
        _diff_fra = (_ov_fra_on["prob"] - _ov_fra_off["prob"]) if (_ov_fra_on and _ov_fra_off) else 0.0
        check("方案A法甲负档下调大球>=3pp(弱弱-6pp)", _diff_fra <= -0.03, True)'''
if anchor in s:
    s = s.replace(anchor, block)
    io.open(P, "w", encoding="utf-8").write(s)
    print("法甲断言已插入")
else:
    print("anchor未找到")
