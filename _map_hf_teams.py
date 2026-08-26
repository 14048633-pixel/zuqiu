# -*- coding: utf-8 -*-
import pandas as pd, json, io, sys, unicodedata, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
t = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\teams.parquet")
v2 = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json", encoding="utf-8"))
name_of = v2["name_of"]  # bsd team_id -> bsd name
# 只取 uncovered 队伍
uncovered = [tid for tid, s in v2["stats"].items() if s["src_bias"] == "uncovered"]
def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\b(fc|fk|sk|sc|ak|bk|nk|if|sv|ks)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()
hf_names = {}
for _, r in t.iterrows():
    for n in [r["name"], r.get("fd_name")]:
        if pd.notna(n):
            hf_names.setdefault(norm(str(n)), r["id"])
print("== 37 支 uncovered 队 HF 匹配 ==")
matched, miss = [], []
for tid in sorted(uncovered, key=lambda x: name_of.get(x, "")):
    nm = name_of.get(tid, "?")
    key = norm(nm)
    cand = hf_names.get(key)
    # 尝试去尾(如 'Red Bull Salzburg' vs 'RB Salzburg')
    if cand is None:
        toks = key.split()
        for L in range(len(toks), 1, -1):
            if hf_names.get(" ".join(toks[:L])):
                cand = hf_names[" ".join(toks[:L])]
                break
    if cand is not None:
        matched.append((nm, cand))
        print("OK  %-26s -> hf_id=%s" % (nm, cand))
    else:
        miss.append(nm)
        print("MISS %-26s" % nm)
print()
print("matched:", len(matched), "| missing:", len(miss))
