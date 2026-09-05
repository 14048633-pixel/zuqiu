# -*- coding: utf-8 -*-
"""对手强度加权攻防(SportsBook/SRS 思想) — 修复"弱队刷弱对手虚高"(Pafos类).

2026-09-03 双轨说明(重要, 防混淆):
  - fit_league_opp() 已被生产 poisson_fit 按 config.MODEL['strength_v2_leagues']
    白名单路由调用(默认含16联赛) -> 本模块现为"生产路由的一部分", 不是纯实验.
  - poisson_fit_v2() 仅供开发/复算对照用, 内部旧基准已强制禁用路由(防自比自).
  - 旧占位壳 config.MODEL['strength_v2'](bool) 与真实路由(list)是两回事, 勿混.
方法(2-pass, 轻量):
  1) 先按旧法算每队原始攻防率(时间衰减);
  2) 对每场比赛按"对手防守/进攻强度"加权: 打强队进球/零封算得多, 刷弱队算得少
     factor = clip(1 + 0.6*(联赛均值 / 对手该侧均值 - 1), 0.7, 1.3)
  3) 用加权后的场均替换 tstats, 其余(基准/衰减/OU窗口)沿用旧管线.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from model import _time_weight, _strength


def _league_base(g):
    ref = g["date"].max()
    days = (ref - g["date"]).dt.days.values.astype(float)
    w = _time_weight(days)
    return {
        "n": len(g),
        "home_avg": float(np.average(g["hg"].values, weights=w)),
        "away_avg": float(np.average(g["ag"].values, weights=w)),
        "total_avg": float(np.average((g["hg"] + g["ag"]).values, weights=w)),
    }


def _collect(g):
    teams = {}
    for _, r in g.iterrows():
        for side, team, gf, ga in (
            ("h", r["home"], r["hg"], r["ag"]),
            ("a", r["away"], r["ag"], r["hg"]),
        ):
            rec = teams.setdefault(team, {"h_gf": [], "h_ga": [], "a_gf": [], "a_ga": []})
            if side == "h":
                rec["h_gf"].append((r["date"], gf, r["away"]))
                rec["h_ga"].append((r["date"], ga, r["away"]))
            else:
                rec["a_gf"].append((r["date"], gf, r["home"]))
                rec["a_ga"].append((r["date"], ga, r["home"]))
    return teams


def _clip(x, lo=0.7, hi=1.3):
    return max(lo, min(hi, x))


def fit_league_opp(g):
    """单联赛对手强度加权拟合 -> 返回 (lg, teams) 结构同 poisson_fit."""
    lg = _league_base(g)
    ref = g["date"].max()
    raw_teams = _collect(g)
    # pass1: 原始率(供对手强度估计)
    def _wavg_rate(pairs):
        if not pairs:
            return np.nan
        w = np.array([_time_weight((ref - d).days) for d, _, _ in pairs])
        return float(np.average([v for _, v, _ in pairs], weights=w))

    raw = {}
    for team, rec in raw_teams.items():
        raw[team] = {
            "h_gf": _wavg_rate(rec["h_gf"]), "h_ga": _wavg_rate(rec["h_ga"]),
            "a_gf": _wavg_rate(rec["a_gf"]), "a_ga": _wavg_rate(rec["a_ga"]),
        }
    # pass2: 对手加权(主队进球按客队防守强度加权, 主队失球按客队进攻强度加权; 客队对称)
    out = {}
    for team, rec in raw_teams.items():
        rt = raw.get(team, {})

        def _adj(pairs, side_rate_kind, opp_key):
            """pairs: (date, 值, 对手); 权重 = 时间衰减 × 对手该侧强度因子."""
            ws, vals = [], []
            for d, v, opp in pairs:
                opp_r = (raw.get(opp) or {}).get(opp_key)
                base = lg["home_avg"] if opp_key in ("a_gf", "a_ga") else lg["away_avg"]
                if opp_r is None or not np.isfinite(opp_r) or base <= 0 or opp_r <= 0:
                    f = 1.0
                else:
                    f = _clip(1.0 + 0.6 * (base / opp_r - 1.0))
                w = _time_weight((ref - d).days) * f
                ws.append(w)
                vals.append(v)
            if not ws:
                return np.nan
            return float(np.average(vals, weights=ws))

        out[team] = {
            "h_gf": _adj(rec["h_gf"], "h_gf", "a_ga"),   # 对手客场防守
            "h_ga": _adj(rec["h_ga"], "h_ga", "a_gf"),   # 对手客场进攻
            "a_gf": _adj(rec["a_gf"], "a_gf", "h_ga"),   # 对手主场防守
            "a_ga": _adj(rec["a_ga"], "a_ga", "h_gf"),   # 对手主场进攻
            "n": len(rec["h_gf"]) + len(rec["a_gf"]),
        }
    # 归一化: 对手加权会让全联赛 λ 整体收缩 -> 按侧拉回联赛基准(平均队≈base)
    for key, col in (("h_gf", "home_avg"), ("h_ga", "home_avg"),
                     ("a_gf", "away_avg"), ("a_ga", "away_avg")):
        vals = [t[key] for t in out.values() if t[key] is not None and np.isfinite(t[key])]
        if vals:
            m = float(np.mean(vals))
            if m > 0:
                f = lg[col] / m
                for t in out.values():
                    if t[key] is not None and np.isfinite(t[key]):
                        t[key] *= f
    return lg, out


def poisson_fit_v2(df_train):
    """实验版 poisson_fit: 与旧版同结构, 但球队强度换为对手加权."""
    fit = {}
    for league, g in df_train.groupby("league"):
        try:
            lg, teams = fit_league_opp(g)
        except Exception:
            continue
        fit[league] = {"lg": lg, "teams": teams}
    # 复用旧版结构字段, 保证 poisson_predict 兼容(不重算 OU/rho, A/B 只比 λ/方向)
    try:
        from model import poisson_fit as _old
        from config import MODEL as _M
        _save = _M.get("strength_v2_leagues")
        _M["strength_v2_leagues"] = []   # 旧基准必须真旧(防白名单路由污染 A/B)
        try:
            old_fit = _old(df_train)
        finally:
            _M["strength_v2_leagues"] = _save
        fit["_ou_calibration"] = old_fit.get("_ou_calibration")
        fit["_dc_rho"] = old_fit.get("_dc_rho")
        fit["_league_era"] = old_fit.get("_league_era")
        # 总分对齐: v2 对手加权会压缩 λ 总进球 -> 按训练段把 v2 总进球缩放回旧口径
        # (保留排序修正, 消除总分副作用; 缩放系数 = sqrt(旧均总/新均总))
        from model import poisson_predict as _pp
        for league in list(fit.keys()):
            if league.startswith("_"):
                continue
            g = df_train[df_train["league"] == league]
            if len(g) < 60 or league not in old_fit:
                continue
            samp = g.sample(min(len(g), 300), random_state=7)
            s_old = []
            s_new = []
            for _, row in samp.iterrows():
                try:
                    o1 = _pp(old_fit, row)
                    o2 = _pp(fit, row)
                except Exception:
                    continue
                if np.isfinite(o1[0]) and np.isfinite(o2[0]) and o1[0] > 0 and o2[0] > 0:
                    s_old.append(o1[0] + o1[1])
                    s_new.append(o2[0] + o2[1])
            if len(s_old) >= 30 and len(s_new) >= 30:
                ratio = float(np.mean(s_old) / np.mean(s_new))
                c = float(np.sqrt(max(0.6, min(1.5, ratio))))
                for t in (fit[league].get("teams") or {}).values():
                    for k in ("h_gf", "h_ga", "a_gf", "a_ga"):
                        if t.get(k) is not None and np.isfinite(t[k]):
                            t[k] *= c
    except Exception:
        pass
    return fit
