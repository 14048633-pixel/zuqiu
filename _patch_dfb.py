# -*- coding: utf-8 -*-
import io
p = r'prediction_v2/scan_upcoming.py'
s = io.open(p, encoding='utf-8').read()
anchor = '    elif m.get("coach_missing"):\n        note.append("教练数据未提取(BSD缓存无该教练/联赛池退化)")\n\n    if h_rec and a_rec:\n        # 双方有独立数据: 标准泊松 (含收缩后的攻防)'
print('anchor count:', s.count(anchor))
insert = '''    elif m.get("coach_missing"):
        note.append("教练数据未提取(BSD缓存无该教练/联赛池退化)")

    # 德国杯第一轮客队进攻放大 (r1_away_boost): BSD 1148场实测 R1客均2.83球 >> 泊松基准,
    #   强弱悬殊大球被系统性低估; league_avg 在λ公式中为分母(升基准反降λ), 故用攻防侧放大
    if _cup_key == "德国杯" and cal.get("r1_away_boost") and agf_eff is not None:
        _r1_win = cal.get("r1_window")
        _d_str = None
        try:
            _d_str = m["ct"].date().isoformat()
        except Exception:
            _d_str = str(m.get("ct"))[:10]
        if _r1_win and _d_str and _r1_win[0] <= _d_str <= _r1_win[1]:
            agf_eff = round(agf_eff * cal["r1_away_boost"], 3)
            note.append("德国杯第一轮客队进攻放大×%.2f(BSD实测R1客均2.83球, 强弱悬殊大球)" % cal["r1_away_boost"])

    if h_rec and a_rec:
        # 双方有独立数据: 标准泊松 (含收缩后的攻防)'''
if s.count(anchor) != 1:
    raise SystemExit('anchor not found: %d' % s.count(anchor))
s = s.replace(anchor, insert)
io.open(p, 'w', encoding='utf-8').write(s)
print('patched ok')
