"""数据加载 —— 唯一数据入口。

读取 football-data.co.uk 原始 CSV（matches_2015_2025.csv + football_data_recent.csv），
清洗、去重、排序，保留回测所需字段。
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

DIV_LEAGUE = {
    "E0": "英超", "SP1": "西甲", "I1": "意甲", "D1": "德甲", "F1": "法甲",
    "E1": "英冠", "SP2": "西乙", "D2": "德乙", "N1": "荷甲",
}

# 需要的赔率字段
ODDS_1X2_OPEN = {"PSH", "PSD", "PSA", "B365H", "B365D", "B365A"}
ODDS_1X2_CLOSE = {"PSCH", "PSCD", "PSCA", "B365CH", "B365CD", "B365CA"}
ODDS_OU = {"P>2.5", "P<2.5", "B365>2.5", "B365<2.5",
           "PC>2.5", "PC<2.5", "B365C>2.5", "B365C<2.5"}
ODDS_AH = {"AHh", "PAHH", "PAHA", "B365AHH", "B365AHA",
           "PCAHH", "PCAHA", "B365CAHH", "B365CAHA"}
ALL_ODDS = ODDS_1X2_OPEN | ODDS_1X2_CLOSE | ODDS_OU | ODDS_AH

SOURCE_FILES = ["matches_2015_2025.csv", "football_data_recent.csv"]


def _parse_date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return pd.NaT
    s = str(v).strip()
    if len(s) == 8 and s[2] == "/" and s[5] == "/":
        return pd.to_datetime(s, format="%d/%m/%y", errors="coerce")
    return pd.to_datetime(s, dayfirst=True, errors="coerce")


def load_football_data_xg(data_dir: str, xg_cache: Optional[str] = None,
                          min_date: Optional[str] = None,
                          max_date: Optional[str] = None) -> pd.DataFrame:
    """加载 football-data 并按 (日期,主客队) 合并逐场 xG 缓存（无匹配则 xG 为 NaN）。"""
    df = load_football_data(data_dir, min_date=min_date, max_date=max_date)
    if not xg_cache or not os.path.exists(xg_cache):
        return df
    xg = pd.read_csv(xg_cache, encoding="utf-8-sig", low_memory=False)
    xg["date"] = pd.to_datetime(xg["date"], errors="coerce").dt.normalize()
    xg = xg.dropna(subset=["date", "home_xg", "away_xg"])
    df["__d"] = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()
    df = df.merge(xg[["date", "HomeTeam", "AwayTeam", "home_xg", "away_xg"]],
                  left_on=["__d", "HomeTeam", "AwayTeam"],
                  right_on=["date", "HomeTeam", "AwayTeam"],
                  how="left").drop(columns=["date", "__d"])
    return df


def load_football_data(data_dir: str,
                       min_date: Optional[str] = None,
                       max_date: Optional[str] = None) -> pd.DataFrame:
    """加载并清洗足球数据。返回按日期升序、去重后的 DataFrame。"""
    frames = []
    for fname in SOURCE_FILES:
        path = os.path.join(data_dir, fname)
        if os.path.exists(path):
            frames.append(pd.read_csv(path, low_memory=False))
    if not frames:
        raise FileNotFoundError(f"{data_dir} 下未找到 {SOURCE_FILES}")
    df = pd.concat(frames, ignore_index=True)

    # 基础清洗（兼容 dd/mm/yyyy 与 dd/mm/yy 混合格式）
    df["Date"] = df["Date"].map(_parse_date)
    df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam"])
    for col in ("FTHG", "FTAG"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["FTHG", "FTAG"])
    df["FTHG"] = df["FTHG"].astype(int)
    df["FTAG"] = df["FTAG"].astype(int)

    # 联赛名（优先 Div 映射）
    df["league"] = df["Div"].map(DIV_LEAGUE)
    if df["league"].isna().all():
        df["league"] = df.get("league_cn", "")
    df["league"] = df["league"].fillna("未知")

    # 去重 + 排序
    df = df.drop_duplicates(subset=["Date", "HomeTeam", "AwayTeam"], keep="last")
    df = df.sort_values("Date").reset_index(drop=True)

    # 时间过滤
    if min_date:
        df = df[df["Date"] >= pd.Timestamp(min_date)]
    if max_date:
        df = df[df["Date"] <= pd.Timestamp(max_date)]

    # 赔率转数值
    for c in ALL_ODDS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.reset_index(drop=True)


def odds_available(df: pd.DataFrame, market: str) -> pd.Series:
    """返回某市场在指定行是否数据齐全。"""
    need = {
        "1x2_pinn_open": ["PSH", "PSD", "PSA"],
        "1x2_pinn_close": ["PSCH", "PSCD", "PSCA"],
        "1x2_b365_open": ["B365H", "B365D", "B365A"],
        "ou_pinn_open": ["P>2.5", "P<2.5"],
        "ou_b365_open": ["B365>2.5", "B365<2.5"],
        "ou_pinn_close": ["PC>2.5", "PC<2.5"],
        "ou_b365_close": ["B365C>2.5", "B365C<2.5"],
        "ah_pinn_open": ["AHh", "PAHH", "PAHA"],
        "ah_b365_open": ["AHh", "B365AHH", "B365AHA"],
        "ah_pinn_close": ["AHh", "PCAHH", "PCAHA"],
    }[market]
    have = [c for c in need if c in df.columns]
    if len(have) < len(need):
        return pd.Series(False, index=df.index)
    return df[have].notna().all(axis=1)
