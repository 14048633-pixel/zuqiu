import sqlite3
from src.db import BetTracker
t = BetTracker()
conn = sqlite3.connect(t.db_path)
rows = conn.execute(
    "SELECT parlay_id, group_concat(match_text || ' -> ' || bet_type || '@' || odds, ' | ') "
    "FROM bets WHERE parlay_id IS NOT NULL GROUP BY parlay_id"
).fetchall()
for pid, desc in rows:
    print("串关 %s:" % pid[:8])
    for sel in desc.split(" | "):
        print("  " + sel)
    print()

rows2 = conn.execute(
    "SELECT match_text, bet_type, odds, edge, won FROM bets WHERE parlay_id IS NULL OR parlay_id = ''"
).fetchall()
if rows2:
    print("单场投注:")
    for mt, bt, od, ed, wn in rows2:
        status = "待结算" if wn is None else ("赢" if wn else "输")
        print("  %s -> %s@%.2f (edge %s) [%s]" % (mt, bt, od, ed, status))
conn.close()
