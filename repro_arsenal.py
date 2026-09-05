# -*- coding: utf-8 -*-
"""可复现 fixture: Arsenal vs Chelsea λ (旧 vs 生产路由).

固定输入口径(2026-09-03 对账用):
  df = load_master(include_espn=False)
  train = E0 全历史, date < '2026-08-01'
  match = Arsenal(home) vs Chelsea(away), date 2026-08-20
输出含数据指纹, 数据一变即漂移, 方便定位"换数据/改代码"造成的数字差异.
用法: python repro_arsenal.py
"""
from __future__ import annotations

import sys
import pandas as pd

sys.path.insert(0, r"D:\发家致富\football_analyzer")

from config import MODEL
from data_loader import load_master
from model import poisson_fit, poisson_predict


def data_fp():
    try:
        from cache_utils import data_fingerprint
        return data_fingerprint()
    except Exception:
        return "n/a"


def produce(espn=False, cut="2026-08-01", match_date="2026-08-20"):
    df = load_master(include_espn=espn)
    e0 = df[df["league"] == "E0"]
    train = e0[e0["date"] < pd.Timestamp(cut)]
    row = {"league": "E0", "home": "Arsenal", "away": "Chelsea",
           "date": pd.Timestamp(match_date)}
    save = list(MODEL.get("strength_v2_leagues") or [])
    MODEL["strength_v2_leagues"] = []
    fo = poisson_fit(train)
    lo = poisson_predict(fo, row)
    MODEL["strength_v2_leagues"] = save
    fn = poisson_fit(train)
    ln = poisson_predict(fn, row)
    MODEL["strength_v2_leagues"] = save
    return {
        "fingerprint": data_fp(),
        "espn": espn, "cut": cut, "match_date": match_date,
        "master_rows": int(len(df)), "e0_rows": int(len(e0)),
        "e0_date_max": str(e0["date"].max().date()),
        "enabled_leagues": len(save),
        "old_lh": round(float(lo[0]), 4), "old_la": round(float(lo[1]), 4),
        "routed_lh": round(float(ln[0]), 4), "routed_la": round(float(ln[1]), 4),
    }


if __name__ == "__main__":
    import json
    r = produce()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    print("期望(基线, 数据指纹不变时): 旧 2.35/0.68 | 路由 2.16/0.78")
