# -*- coding: utf-8 -*-
"""补丁A2: _side_of 升级为词集交集匹配(覆盖缩写/顺序不同/前缀差异)
  SJK vs SJK Seinäjoki / KS Cracovia vs Cracovia Kraków / Marseille vs Olympique de Marseille"""
import io
fp = r"analysis_records/research/_recompute_0822_intel.py"
s = io.open(fp, encoding="utf-8").read()

old = '''# 容错队名匹配: 完全一致 > 包含 > 长度比>=0.5(缩写保护)
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
new = '''# 容错队名匹配: 完全一致 > 词集交集(覆盖缩写/顺序不同/前后缀差异) > draw
_GEN_WORDS = {"fc", "fk", "ks", "sc", "us", "ac", "cd", "cf", "de", "sv", "1", "st", "as",
              "ud", "su", "if", "ff", "is", "sk", "nk", "ofk", "sf", "sfk", "afc", "cfc",
              "ks", "sport", "club", "deportivo", "societa", "ss", "sd", "ud", "cd"}
def _side_of(name, h, a):
    no, nh, na = uniq(name), uniq(h), uniq(a)
    if not no:
        return None
    if no == nh or (no and nh and no in nh) or (no and nh and nh in no and len(nh) >= 3):
        return "home"
    if no == na or (no and na and no in na) or (no and na and na in no and len(na) >= 3):
        return "away"
    if "draw" in name.lower():
        return "draw"
    def _ws(s_):
        return set(re.sub(r"[^a-z0-9 ]+", " ", (s_ or "").lower()).split())
    def _hit(xs, ys):
        if not xs or not ys:
            return False
        inter = xs & ys
        if not inter:
            return False
        if inter == xs or inter == ys:
            return True
        return any(len(w) >= 4 and w not in _GEN_WORDS for w in inter)
    if _hit(_ws(name), _ws(h)):
        return "home"
    if _hit(_ws(name), _ws(a)):
        return "away"
    return None

'''
assert old in s, "side_of block not found"
s = s.replace(old, new)
io.open(fp, "w", encoding="utf-8").write(s)
print("patched word-set matching")
