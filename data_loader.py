# -*- coding: utf-8 -*-
"""数据加载层：多源读取、字段标准化、联赛归一、去重合并。

主源  : data/raw/football_data/football_data_collected.json（含欧赔+比赛统计）
辅源 1: data/raw/football_data/football_data_recent.csv（足彩网，含初/临盘、亚盘）
辅源 2: data/raw/espn/*.csv（仅比分，用于补缺与近期数据）

输出统一 DataFrame，列：
  date, league, home, away, hg, ag,
  odds_h, odds_d, odds_a,
  odds_h_open, odds_d_open, odds_a_open, odds_h_close, odds_d_close, odds_a_close,
  ah_line, ah_h, ah_a,
  home_shots, away_shots, home_sot, away_sot, home_corners, away_corners,
  home_yellow, away_yellow, home_red, away_red,
  ht_hg, ht_ag, source
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import DATA, DIV_CN, CN_CANON

MASTER_COLS = [
    "date", "league", "home", "away", "hg", "ag",
    "odds_h", "odds_d", "odds_a",
    "odds_h_open", "odds_d_open", "odds_a_open",
    "odds_h_close", "odds_d_close", "odds_a_close",
    "ah_line", "ah_h", "ah_a",
    "ah_line_close", "ah_h_close", "ah_a_close",
    "ou25_over", "ou25_under", "ou25_over_close", "ou25_under_close",
    "home_shots", "away_shots", "home_sot", "away_sot",
    "home_corners", "away_corners", "home_yellow", "away_yellow",
    "home_red", "away_red", "ht_hg", "ht_ag", "source",
]


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=MASTER_COLS)


# J1 跨年改制: 2026 上半年过渡赛季(2026-02-01~2026-07-31) = 分区制 + 90分钟平局
# 点球决胜 + 无升降级, 与 2026-08 起的 20 队跨年正式赛季规则完全不同。过渡行混入
# 会把 J1 进球中枢/球队攻防/Elo 拖向旧规则, 必须剔除(2026-09-02 修正)。
JP1_TRANSITION_START = pd.Timestamp("2026-02-01")
JP1_TRANSITION_END = pd.Timestamp("2026-07-31")


def drop_jp1_transition(df: pd.DataFrame) -> pd.DataFrame:
    """剔除 J1 2026 过渡赛季行(跨年改制前后规则不可比)。"""
    if df is None or len(df) == 0 or "league" not in df.columns or "date" not in df.columns:
        return df
    d = pd.to_datetime(df["date"], errors="coerce")
    bad = ((df["league"] == "JP1") & d.notna()
           & (d >= JP1_TRANSITION_START) & (d <= JP1_TRANSITION_END))
    if not bad.any():
        return df
    return df[~bad].copy()


def _parse_date(value) -> pd.Timestamp | None:
    """兼容 dd/mm/yyyy 与 yyyy-mm-dd 两种格式。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return pd.Timestamp(datetime.strptime(s, fmt))
        except ValueError:
            continue
    return None


def _norm_team(name) -> str:
    if name is None:
        return ""
    s = str(name).strip()
    return s


def load_json_matches(path: Path | str | None = None) -> pd.DataFrame:
    path = Path(path) if path else DATA["json"]
    if not path.exists():
        return _empty_frame()
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    rows = []
    for key, matches in raw.items():
        league_key = key.split("_")[0] if "_" in key else key
        season = key.split("_")[1] if "_" in key else ""
        cn_name = matches[0].get("league", "") if matches else ""
        league = CN_CANON.get(cn_name, league_key)
        for m in matches:
            odds = m.get("odds") or {}
            rows.append({
                "date": _parse_date(m.get("date")),
                "league": league,
                "home": _norm_team(m.get("home")),
                "away": _norm_team(m.get("away")),
                "hg": _to_num(m.get("hg")),
                "ag": _to_num(m.get("ag")),
                "odds_h": _to_num(odds.get("home")),
                "odds_d": _to_num(odds.get("draw")),
                "odds_a": _to_num(odds.get("away")),
                "home_shots": _to_num(m.get("home_shots")),
                "away_shots": _to_num(m.get("away_shots")),
                "home_sot": _to_num(m.get("home_shots_on")),
                "away_sot": _to_num(m.get("away_shots_on")),
                "home_corners": _to_num(m.get("home_corners")),
                "away_corners": _to_num(m.get("away_corners")),
                "home_yellow": _to_num(m.get("home_yellow")),
                "away_yellow": _to_num(m.get("away_yellow")),
                "home_red": _to_num(m.get("home_red")),
                "away_red": _to_num(m.get("away_red")),
                "ht_hg": _to_num(m.get("ht_hg")),
                "ht_ag": _to_num(m.get("ht_ag")),
                "source": "json",
            })
    df = pd.DataFrame(rows, columns=MASTER_COLS)
    df["season"] = season
    return df


def _to_num(v):
    if v is None:
        return None
    try:
        f = float(v)
        return f if f == f else None  # NaN
    except (TypeError, ValueError):
        return None


def _neg(v):
    """取负; None/NaN 原样返回(用于 football-data AHh 符号统一)。"""
    return -v if v is not None else None


def load_recent_csv(path: Path | str | None = None) -> pd.DataFrame:
    """football-data.co.uk 格式，含初盘(B365H...)与临场(B365CH...)、亚盘(AHh)。"""
    path = Path(path) if path else DATA["recent_csv"]
    if not path.exists():
        return _empty_frame()
    df = pd.read_csv(path, low_memory=False)
    rows = []
    for _, r in df.iterrows():
        div = str(r.get("Div", "")).strip()
        if div not in DIV_CN:
            continue
        rows.append({
            "date": _parse_date(r.get("Date")),
            "league": CN_CANON.get(DIV_CN[div], DIV_CN[div]),
            "home": _norm_team(r.get("HomeTeam")),
            "away": _norm_team(r.get("AwayTeam")),
            "hg": _to_num(r.get("FTHG")),
            "ag": _to_num(r.get("FTAG")),
            "odds_h": _to_num(r.get("B365H")),
            "odds_d": _to_num(r.get("B365D")),
            "odds_a": _to_num(r.get("B365A")),
            "odds_h_open": _to_num(r.get("B365H")),
            "odds_d_open": _to_num(r.get("B365D")),
            "odds_a_open": _to_num(r.get("B365A")),
            "odds_h_close": _to_num(r.get("B365CH")),
            "odds_d_close": _to_num(r.get("B365CD")),
            "odds_a_close": _to_num(r.get("B365CA")),
            # football-data 的 AHh 语义与内部约定相反: AHh 负=主队让球, 正=主队受让。
            # 内部 asian_handicap.py 约定 positive=home gives, 故加载时取负统一。
            "ah_line": _neg(_to_num(r.get("AHh"))),
            "ah_h": _to_num(r.get("B365AHH")),
            "ah_a": _to_num(r.get("B365AHA")),
            "ah_line_close": _neg(_to_num(r.get("AHCh"))),
            "ah_h_close": _to_num(r.get("B365CAHH")),
            "ah_a_close": _to_num(r.get("B365CAHA")),
            "ou25_over": _to_num(r.get("B365>2.5")),
            "ou25_under": _to_num(r.get("B365<2.5")),
            "ou25_over_close": _to_num(r.get("B365C>2.5")),
            "ou25_under_close": _to_num(r.get("B365C<2.5")),
            "home_shots": _to_num(r.get("HS")),
            "away_shots": _to_num(r.get("AS")),
            "home_sot": _to_num(r.get("HST")),
            "away_sot": _to_num(r.get("AST")),
            "home_corners": _to_num(r.get("HC")),
            "away_corners": _to_num(r.get("AC")),
            "home_yellow": _to_num(r.get("HY")),
            "away_yellow": _to_num(r.get("AY")),
            "home_red": _to_num(r.get("HR")),
            "away_red": _to_num(r.get("AR")),
            "ht_hg": _to_num(r.get("HTHG")),
            "ht_ag": _to_num(r.get("HTAG")),
            "source": "recent_csv",
        })
    out = pd.DataFrame(rows, columns=MASTER_COLS)
    out["season"] = None
    return out


def load_espn_matches(espn_dir: Path | str | None = None) -> pd.DataFrame:
    """ESPN 比分数据（无赔率），用于补缺。"""
    espn_dir = Path(espn_dir) if espn_dir else DATA["espn_dir"]
    frames = []
    if not espn_dir.exists():
        return _empty_frame()
    for csv_path in sorted(espn_dir.glob("*.csv")):
        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
        except Exception:
            continue
        if not {"date", "home", "away", "hg", "ag"}.issubset(df.columns):
            continue
        league = csv_path.stem
        # 修复: ESPN 联赛名统一到 CN_CANON 规范 key(此前 swe_1→SW1/brazil_serie_a→BR1
        # 与规范 key SWE/BR 不一致, 导致同一联赛被当成两个联赛, 样本被拆半)
        league = {"premier_league": "E0", "eng_2": "E1", "eng_3": "E2", "eng_4": "E3",
                  "esp_1": "SP1", "fra_1": "F1", "ger_1": "D1", "ita_1": "I1",
                  "jpn_1": "JP1", "ned_1": "N1", "por_1": "P1", "swe_1": "SWE",
                  "uefa_champions": "UCL", "uefa_europa": "UEL",
                  "brazil_serie_a": "BR", "csl": "CSL"}.get(league, league)
        tmp = pd.DataFrame({
            "date": df["date"].map(_parse_date),
            "league": league,
            "home": df["home"].map(_norm_team),
            "away": df["away"].map(_norm_team),
            "hg": df["hg"].map(_to_num),
            "ag": df["ag"].map(_to_num),
            "source": "espn",
        })
        frames.append(tmp)
    if not frames:
        return _empty_frame()
    out = pd.concat(frames, ignore_index=True)
    for c in MASTER_COLS:
        if c not in out.columns:
            out[c] = None
    return out[MASTER_COLS]


def load_mls_mx() -> pd.DataFrame:
    """MLS + 墨超本地历史(补齐模型覆盖, 2026-08-29).

    MLS: data/raw/mls_matches.csv (2012-2026, 含 home_win/draw/away_win 赔率)
    墨超: data/raw/墨超_2024_2025.csv + 墨超_2026.csv (ESPN 赛果, 无赔率)
    返回列: date/league/home/away/hg/ag/odds_h/odds_d/odds_a (墨超赔率为 NaN)
    """
    from pathlib import Path
    _raw = Path(__file__).resolve().parent.parent / "data" / "raw"
    parts = []
    # MLS
    try:
        m = pd.read_csv(_raw / "mls_matches.csv")
        m = m.rename(columns={"date_utc": "date", "home_team": "home", "away_team": "away",
                              "goals_home": "hg", "goals_away": "ag",
                              "home_win": "odds_h", "draw": "odds_d", "away_win": "odds_a"})
        m["date"] = pd.to_datetime(m["date"], errors="coerce")
        m["league"] = "MLS"
        m = m[["date", "league", "home", "away", "hg", "ag", "odds_h", "odds_d", "odds_a"]].copy()
        parts.append(m)
    except Exception:
        pass
    # 墨超
    for mx_fp in ("墨超_2024_2025.csv", "墨超_2026.csv"):
        try:
            x = pd.read_csv(_raw / mx_fp)
            x = x.rename(columns={"Date": "date", "HomeTeam": "home", "AwayTeam": "away",
                                  "FTHG": "hg", "FTAG": "ag"})
            x["date"] = pd.to_datetime(x["date"], errors="coerce")
            x["league"] = "MX1"
            for c in ("odds_h", "odds_d", "odds_a"):
                x[c] = float("nan")
            x = x[["date", "league", "home", "away", "hg", "ag", "odds_h", "odds_d", "odds_a"]].copy()
            parts.append(x)
        except Exception:
            pass
    if not parts:
        return pd.DataFrame(columns=["date", "league", "home", "away", "hg", "ag",
                                     "odds_h", "odds_d", "odds_a"])
    return pd.concat(parts, ignore_index=True)


def load_arg_aus() -> pd.DataFrame:
    """阿甲 + 澳超本地历史(补齐模型覆盖, 2026-08-30).

    ARG: data/raw/football_data/arg_matches.csv (BSD 2024-2026, 1240 场)
    AUS: data/raw/football_data/aus_matches.csv (API-Football 2022-2025, 505 场)
    K1: data/raw/football_data/k1_matches.csv (BSD 2024-2026, 619 场)
    补充: supplement_matches.csv (升班马/降级队缺联赛数据补全, 2026-08-30)
    返回列: date/league/home/away/hg/ag/odds_h/odds_d/odds_a (无赔率)
    """
    from pathlib import Path
    _raw = None
    for _cand in (Path(r"D:\足球分析\data\raw\football_data"),
                  Path(__file__).resolve().parent.parent / "data" / "raw" / "football_data"):
        if (_cand / "arg_matches.csv").exists():
            _raw = _cand
            break
    if _raw is None:
        return pd.DataFrame(columns=["date", "league", "home", "away", "hg", "ag",
                                     "odds_h", "odds_d", "odds_a"])
    parts = []
    for fp, lg in (("arg_matches.csv", "ARG"), ("aus_matches.csv", "AUS"),
                   ("k1_matches.csv", "KR1"),
                   ("n1_hist.csv", None), ("b1_hist.csv", None),
                   ("p1_hist.csv", None), ("mx1_hist.csv", None),
                   ("jp1_hist.csv", None),
                   ("sau_matches.csv", "SAU"),   # 沙超 2023-2026 (2026-09-03 补全)
                   ("swiss_matches.csv", "SW1"), # 瑞士超 2019-2026 (2026-09-03 补全; CH=中超勿撞)
                   ("supplement_matches.csv", None)):
        try:
            x = pd.read_csv(_raw / fp)
            x["date"] = pd.to_datetime(x["date"], errors="coerce")
            if lg is not None:
                x["league"] = lg
            x = x[x["league"].notna()]
            for c in ("odds_h", "odds_d", "odds_a"):
                x[c] = float("nan")
            x = x[["date", "league", "home", "away", "hg", "ag",
                   "odds_h", "odds_d", "odds_a"]].copy()
            parts.append(x)
        except Exception:
            pass
    if not parts:
        return pd.DataFrame(columns=["date", "league", "home", "away", "hg", "ag",
                                     "odds_h", "odds_d", "odds_a"])
    return pd.concat(parts, ignore_index=True)


def load_master(include_espn: bool = True, recent_priority: bool = True) -> pd.DataFrame:
    """加载并合并全部来源；同场次去重（recent_csv 优先保留初/临盘）。"""
    parts = [load_json_matches(), load_recent_csv(), load_mls_mx(), load_arg_aus()]
    if include_espn:
        parts.append(load_espn_matches())
    df = pd.concat(parts, ignore_index=True)
    df = df[df["date"].notna()].copy()
    # J1 过渡赛季剔除(跨年改制后规则不可比, 防拖低新赛季进球中枢/攻防/Elo)
    df = drop_jp1_transition(df)
    df = df.sort_values("date").reset_index(drop=True)

    # 去重：主键 date+league+home+away；保留 odds 更全的版本
    df["_score"] = df[["odds_h", "odds_d", "odds_a", "odds_h_open", "ah_line"]].notna().sum(axis=1)
    key = ["date", "league", "home", "away"]
    df = df.sort_values(["_score"], ascending=False).drop_duplicates(subset=key, keep="first")
    df = df.drop(columns=["_score"]).sort_values("date").reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = load_master(include_espn=False)
    print("master rows:", len(df))
    print("date range:", df["date"].min().date(), "->", df["date"].max().date())
    print("leagues:", df["league"].value_counts().head(25).to_dict())
    print("odds coverage: h/d/a",
          df[["odds_h", "odds_d", "odds_a"]].notna().mean().round(3).to_dict())

# odds_source 契约使用 load_data 作为统一入口
load_data = load_master
