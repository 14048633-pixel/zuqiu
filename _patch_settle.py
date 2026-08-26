# -*- coding: utf-8 -*-
import io
p = 'paper_settle.py'
s = io.open(p, encoding='utf-8').read()

# 1) save_ledger: ensure score cols exist
old1 = '''def save_ledger(rows):
    cols = list(rows[0].keys()) if rows else ["date", "league", "match", "home", "away", "bet_name", "prob", "odds", "ev", "star", "ev_tier", "stake_factor", "result", "ret", "pnl", "status", "src"]'''
new1 = old1 + '''
    for _c in ("home_score", "away_score", "score", "is_draw"):
        if _c not in cols:
            cols.append(_c)'''
assert s.count(old1) == 1, 'old1 count: %d' % s.count(old1)
s = s.replace(old1, new1)

# 2) write score fields into ledger row after settle
old2 = '        pnl = pnl_for_result(res, ret)'
assert s.count(old2) == 1, 'old2 count: %d' % s.count(old2)
new2 = old2 + '''
        r["home_score"] = hg
        r["away_score"] = ag
        r["score"] = "%d-%d" % (hg, ag)
        r["is_draw"] = 1 if hg == ag else 0'''
s = s.replace(old2, new2)

io.open(p, 'w', encoding='utf-8').write(s)
print('paper_settle.py patched ok')
