# -*- coding: utf-8 -*-
"""统一缓存工具: 可写缓存目录 + 数据指纹 key (2026-09-01).

背景: 原缓存写到发家致富目录(沙箱外不可写),
且 key 只用 日期+行数 导致数据变化但行数不变时误命中旧缓存。
本模块:
  - CACHE_DIR 指向 D:/足球分析/analysis_records/.cache (可写)
  - data_fingerprint() 汇总所有数据源文件 mtime+size 的 md5, 数据一变 key 即变
  - fit_cache_file() 返回带指纹的缓存文件路径
"""
from __future__ import annotations

import glob
import hashlib
import os
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(r"D:\足球分析\analysis_records\.cache")

# 数据源文件(指纹来源): 本地库 CSV + 主源 JSON + ESPN 补缺 + 补全 CSV
# 注: 必须覆盖 load_master() 实际读的全部源, 否则源更新时指纹不变、缓存误命中。
#   load_json_matches -> data/raw/football_data/*.json (主源)
#   load_recent_csv   -> data/raw/football_data/football_data_recent.csv
#   load_mls_mx       -> data/raw/*.csv (mls/墨超)
#   load_arg_aus      -> D:\足球分析\data\raw\football_data\*.csv (arg/aus/k1/supplement)
#   load_espn_matches -> data/raw/espn/*.csv (ESPN 补缺)
DATA_GLOBS = [
    Path(r"D:\发家致富\data\raw\football_data\*"),
    Path(r"D:\发家致富\data\raw\*.csv"),
    Path(r"D:\足球分析\data\raw\football_data\*.csv"),
    Path(r"D:\发家致富\data\raw\espn\*.csv"),
]


def data_fingerprint() -> str:
    """所有数据源文件 mtime+size 的 md5 指纹. 数据一变指纹即变."""
    h = hashlib.md5()
    # 代码级过滤/口径变更也要让缓存失效: 文件指纹只反映数据文件, 不反映加载逻辑
    # (2026-09-02: J1 过渡赛季剔除后, 版本号防旧 master/poisson_fit 缓存误命中)
    h.update(b"master_v1_j1_transition_drop;")
    seen = set()
    for g in DATA_GLOBS:
        for f in sorted(glob.glob(str(g))):
            p = Path(f)
            # 按完整路径去重: 不同目录的同名文件都计入指纹(防 load_arg_aus 与本地库同名错位)
            key = os.path.normcase(str(p))
            if key in seen:
                continue
            seen.add(key)
            try:
                st = p.stat()
                h.update(f"{p.name}:{st.st_mtime_ns}:{st.st_size};".encode())
            except OSError:
                pass
    return h.hexdigest()[:16]


def fit_cache_file(name: str, df_train: pd.DataFrame) -> Path:
    """返回带指纹的缓存文件路径(自动创建目录)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fp = data_fingerprint()
    ref = str(pd.Timestamp(df_train["date"].max()).date())
    return CACHE_DIR / f"{name}_{ref}_{len(df_train)}_{fp}.pkl"


def cache_file(name: str) -> Path:
    """通用带指纹缓存文件路径(无训练集依赖)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{name}_{data_fingerprint()}.pkl"


def load_master_cached() -> pd.DataFrame:
    """load_master 结果缓存(数据指纹失效). load 3-5s -> 0.1s."""
    import pickle
    fname = cache_file("master")
    if fname.exists():
        try:
            with open(fname, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    from data_loader import load_master
    df = load_master()
    try:
        with open(fname, "wb") as f:
            pickle.dump(df, f)
    except Exception:
        pass
    return df


def elo_history_cached(df: pd.DataFrame):
    """compute_elo_history 结果缓存(数据指纹+df内容标识失效). 每进程5.9s -> 0.1s.
    修复(2026-09-01): 原 key 只含全局数据指纹, 不区分传入 df 的过滤条件,
    曾用 10023 行子集写入缓存, 全量 train 命中同一指纹缓存 -> 大部分队 Elo 变 1500,
    并污染回测(ROI -10.98% -> -11.53%)。key 现加入 len(df)+df.date.max()。"""
    import pickle
    _n = len(df)
    _d = str(pd.Timestamp(df["date"].max()).date()) if _n > 0 else "empty"
    fname = cache_file(f"elo_history_{_n}_{_d}")
    if fname.exists():
        try:
            with open(fname, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    import elo
    hist = elo.compute_elo_history(df)
    try:
        with open(fname, "wb") as f:
            pickle.dump(hist, f)
    except Exception:
        pass
    return hist
