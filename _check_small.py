# -*- coding: utf-8 -*-
import json, io
ROOT = r"D:\足球分析"
d = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json", encoding="utf-8"))
name_of = d["name_of"]
inv = {str(v): k for k, v in name_of.items()}
# 小联赛队名单(未覆盖国内联赛)
small = ["Inter Club d'Escaldes","Lincoln Red Imps","FC Drita","KF Egnatia","Kauno Žalgiris","Víkingur Reykjavík","Klaksvíkar Ítróttarfelag","FC Iberia 1999","Larne FC","Shamrock Rovers","FK Borac Banja Luka","Dinamo City","FC Ararat-Armenia","Sabah FK","Riga FC","NK Celje","Pafos FC","FK Austria Wien","Red Bull Salzburg","FK Crvena Zvezda","GNK Dinamo Zagreb","Ferencváros TC","Maccabi Tel Aviv","Viktoria Plzeň"]
print("%-26s lvl  v2主gf/ga  v2客gf/ga  n主/客" % "队名")
for nm in small:
    tid = inv.get(nm)
    if tid is None: continue
    s = d["stats"][str(tid)]
    print("%-26s %.2f  %s/%s  %s/%s  %s/%s" % (nm, s["level"], s["v2_home_gf"], s["v2_home_ga"], s["v2_away_gf"], s["v2_away_ga"], s["n_home"], s["n_away"]))
