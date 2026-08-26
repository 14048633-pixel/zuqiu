# -*- coding: utf-8 -*-
import pandas as pd, json, io, sys, unicodedata, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
t = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\teams.parquet")
def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", s)
miss = ["Dinamo City","FC Iberia 1999","FC Viktoria Plzeň","FK Austria Wien","Ferencváros TC","GNK Dinamo Zagreb","KF Egnatia","Klaksvíkar Ítróttarfelag","Red Bull Salzburg","SK Rapid Wien","Sabah FK"]
keys = {
    "Dinamo City": ["dinamo city", "dinamo tirana", "dinamo"],
    "FC Iberia 1999": ["iberia"],
    "FC Viktoria Plzeň": ["plzen", "plzen"],
    "FK Austria Wien": ["austria wien", "austria vienna", "austria"],
    "Ferencváros TC": ["ferencvaros", "ferencvarosi"],
    "GNK Dinamo Zagreb": ["dinamo zagreb"],
    "KF Egnatia": ["egnatia"],
    "Klaksvíkar Ítróttarfelag": ["klaksvik"],
    "Red Bull Salzburg": ["salzburg"],
    "SK Rapid Wien": ["rapid wien", "rapid vienna", "rapid"],
    "Sabah FK": ["sabah"],
}
for nm in miss:
    found = []
    for _, r in t.iterrows():
        n1 = norm(r["name"]); n2 = norm(r.get("fd_name"))
        for k in keys[nm]:
            if k in n1 or (n2 and k in n2):
                found.append((r["id"], r["name"], r.get("fd_name")))
    print("%-26s -> %s" % (nm, found[:4]))
