# -*- coding: utf-8 -*-
"""补丁A: 修复 odds_compare 重算 CSV 的 h2h/spreads 队名容错匹配
  根因: the-odds-api outcome name 是全名(SJK Seinäjoki/Marseille), rows 是缩写(SJK/Olympique de Marseille)
  -> uniq 精确相等失败 -> side=? -> 1X2/亚盘整条丢弃, 只剩大小球
  修复: 完全一致 > 包含 > 长度比>=0.5(缩写保护), 防止歧义错配"""
import io
fp = r"analysis_records/research/_recompute_0822_intel.py"
s = io.open(fp, encoding="utf-8").read()

helper = '''# 容错队名匹配: 完全一致 > 包含(短名在长名中) > 长度比>=0.5(缩写保护)
def _side_of(name, h, a):
    no, nh, na = uniq(name), uniq(h), uniq(a)
    if not no:
        return None
    if no == nh or (len(no) >= 4 and no in nh):
        return "home"
    if no == na or (len(no) >= 4 and no in na):
        return "away"
    if "draw" in name.lower():
        return "draw"
    # 缩写保护: 缩写名是长名的子序列(按词), 或长度比>=0.5
    def _sub(a_, b_):
        return a_ and b_ and (a_ in b_ or b_ in a_)
    if len(no) >= 5 and len(nh) >= 5 and (_sub(no, nh) or _sub(nh, no)):
        return "home"
    if len(no) >= 5 and len(na) >= 5 and (_sub(no, na) or _sub(na, no)):
        return "away"
    return None

'''
old = '''hdr = ["snapshot_ts","event_id","league","commence_time","home_team","away_team",
       "bookmaker","market","outcome","side","side_key","point","price","last_update"]
crows = []'''
new = helper + '''hdr = ["snapshot_ts","event_id","league","commence_time","home_team","away_team",
       "bookmaker","market","outcome","side","side_key","point","price","last_update"]
crows = []'''
assert old in s, "helper insert not found"
s = s.replace(old, new)

old2 = '''                    if mkey == "h2h":
                        nh, na = uniq(h), uniq(a); no = uniq(name)
                        if no == nh: side = "home"
                        elif no == na: side = "away"
                        elif "draw" in name.lower(): side = "draw"
                        else: side = "?"
                        if side == "?": continue'''
new2 = '''                    if mkey == "h2h":
                        side = _side_of(name, h, a)
                        if not side: continue'''
assert old2 in s, "h2h block not found"
s = s.replace(old2, new2)

old3 = '''                    elif mkey == "spreads":
                        nh, na = uniq(h), uniq(a); no = uniq(name)
                        side = "home" if no == nh else ("away" if no == na else "?")
                        if side == "?" or pt is None: continue'''
new3 = '''                    elif mkey == "spreads":
                        side = _side_of(name, h, a)
                        if side in (None, "draw") or pt is None: continue'''
assert old3 in s, "spreads block not found"
s = s.replace(old3, new3)
io.open(fp, "w", encoding="utf-8").write(s)
print("patched tolerant team match")
