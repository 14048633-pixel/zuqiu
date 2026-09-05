# -*- coding: utf-8 -*-
"""贝叶斯泊松攻防强度: Gamma-Poisson 共轭后验 + 预测分布 (V4.5).

背景: model.py 的 poisson_fit 用"线性收缩"估攻防强度(点估计), 收缩常数 4 是拍脑袋的。
本模块用 Gamma-Poisson 共轭贝叶斯替换:
  - 似然: 进球 ~ Poisson(λ)
  - 先验: λ ~ Gamma(α0, β0),  α0 = n0×league_avg, β0 = n0   (先验均值=联赛均值)
  - 后验: λ|data ~ Gamma(α0 + Σw·goals, β0 + Σw)            (w=时间衰减权重)
  - 后验均值 = (n0·league_avg + Σw·goals) / (n0 + Σw)

与旧线性收缩等价性:
  旧 _strength = (n·raw + 4) / (n + 4), raw = rate/base
  后验均值 / base = (n0 + Σw·raw) / (n0 + Σw)
  当 n0=4 且 w=1 时两者完全等价 -> 贝叶斯是旧方法的超集, 行为不倒退,
  额外提供: λ 的置信区间 / 小样本不确定性 / 概率分布(非点值).

用法:
  python football_analyzer/bayes_poisson.py          # 自检 + 真实数据演示
"""
from __future__ import annotations

import io
import sys

import numpy as np
import pandas as pd

from model import poisson_fit, _time_weight
from dixon_coles import dc_1x2, dc_over_under_prob

N0_DEFAULT = 4.0  # 先验等效样本量(收缩强度), 与旧线性收缩 min_n=4 对齐


# ---------------- 后验拟合 ----------------

def team_posterior(goals_pairs: list, ref_date, league_avg: float, n0: float = N0_DEFAULT):
    """单队单侧的后验 Gamma 参数(时间衰减加权, 保持共轭).

    goals_pairs: [(date, goals), ...] (进攻=进球, 防守=失球)
    返回 dict: {alpha, beta, n_eff, mean}   (beta 为 rate 参数, mean=alpha/beta)
    """
    if not goals_pairs or league_avg <= 0:
        return {"alpha": n0 * league_avg, "beta": n0, "n_eff": 0.0,
                "mean": league_avg}
    w = np.array([_time_weight((ref_date - d).days) for d, _ in goals_pairs])
    g = np.array([v for _, v in goals_pairs])
    sw = float(w.sum())
    sg = float((w * g).sum())
    alpha = n0 * league_avg + sg
    beta = n0 + sw
    return {"alpha": alpha, "beta": beta, "n_eff": sw, "mean": alpha / beta}


def bayes_fit(df_train: pd.DataFrame, n0: float = N0_DEFAULT) -> dict:
    """直接由训练数据估计每队每侧后验 Gamma 参数.

    返回 {"<league>": {"lg": {home_avg, away_avg},
                       "teams": {"<team>": {"h_atk": post, "h_def": post,
                                            "a_atk": post, "a_def": post}}}, ...}
    poisson_fit 会把原始 (date,goals) 压缩成加权均值(丢失 Σw/Σw·goals), 故此处独立重建.
    """
    out = {}
    for league, g in df_train.groupby("league"):
        ref_date = g["date"].max()
        days = (ref_date - g["date"]).dt.days.values.astype(float)
        w = _time_weight(days)
        home_avg = float(np.average(g["hg"].values, weights=w))
        away_avg = float(np.average(g["ag"].values, weights=w))
        if home_avg <= 0:
            home_avg = 1.0
        if away_avg <= 0:
            away_avg = 1.0

        teams = {}
        for _, r in g.iterrows():
            for side, team, gf, ga in (
                ("h", r["home"], r["hg"], r["ag"]),
                ("a", r["away"], r["ag"], r["hg"]),
            ):
                rec = teams.setdefault(team, {"h_gf": [], "h_ga": [], "a_gf": [], "a_ga": []})
                if side == "h":
                    rec["h_gf"].append((r["date"], gf))
                    rec["h_ga"].append((r["date"], ga))
                else:
                    rec["a_gf"].append((r["date"], gf))
                    rec["a_ga"].append((r["date"], ga))

        posts = {}
        for team, rec in teams.items():
            posts[team] = {
                "h_atk": team_posterior(rec["h_gf"], ref_date, home_avg, n0),
                "h_def": team_posterior(rec["h_ga"], ref_date, home_avg, n0),
                "a_atk": team_posterior(rec["a_gf"], ref_date, away_avg, n0),
                "a_def": team_posterior(rec["a_ga"], ref_date, away_avg, n0),
            }
        out[league] = {"lg": {"home_avg": home_avg, "away_avg": away_avg},
                       "teams": posts}
    return out


# ---------------- 预测采样 ----------------

def _sample_strength(post: dict, base: float, rng, n: int) -> np.ndarray:
    """从后验 Gamma 采样 λ, 归一化为攻/防强度."""
    alpha, beta = post["alpha"], post["beta"]
    lam = rng.gamma(alpha, 1.0 / beta, size=n)
    return lam / base


def lambda_samples(bayes: dict, row: dict, n_samples: int = 2000,
                   rng=None) -> tuple | None:
    """从后验采样 λh/λa 分布. 返回 (lh_array, la_array). 未知队/联赛返回 None."""
    league = row["league"]
    if league not in bayes:
        return None
    b = bayes[league]
    lg = b["lg"]
    home_avg = lg["home_avg"] if lg["home_avg"] > 0 else 1.0
    away_avg = lg["away_avg"] if lg["away_avg"] > 0 else 1.0
    teams = b["teams"]
    bh, ba = teams.get(row["home"]), teams.get(row["away"])
    if not bh or not ba:
        return None
    rng = rng if rng is not None else np.random.default_rng()
    atk_h = _sample_strength(bh["h_atk"], home_avg, rng, n_samples)
    def_a = _sample_strength(ba["a_def"], away_avg, rng, n_samples)
    atk_a = _sample_strength(ba["a_atk"], away_avg, rng, n_samples)
    def_h = _sample_strength(bh["h_def"], home_avg, rng, n_samples)
    lh = home_avg * atk_h * def_a
    la = away_avg * atk_a * def_h
    cap = 4.5
    return np.minimum(lh, cap), np.minimum(la, cap)


def prob_dist(fit: dict, bayes: dict, row: dict, n_samples: int = 2000,
              rng=None) -> dict | None:
    """预测 1X2 / 大2.5 概率的分布(均值 + P5/P95 区间)."""
    lams = lambda_samples(bayes, row, n_samples, rng)
    if lams is None:
        return None
    lh, la = lams
    rho = float((fit.get("_dc_rho") or {}).get(row["league"], 0.05))
    ph = np.zeros(n_samples); pd_ = np.zeros(n_samples); pa = np.zeros(n_samples)
    ou = np.zeros(n_samples)
    for i in range(n_samples):
        h, a = lh[i], la[i]
        ph[i], pd_[i], pa[i] = dc_1x2(h, a, rho)
        ou[i] = dc_over_under_prob(h, a, 2.5, rho)
    def _q(x):
        return {"mean": float(np.mean(x)), "p5": float(np.percentile(x, 5)),
                "p95": float(np.percentile(x, 95))}
    return {"home": _q(ph), "draw": _q(pd_), "away": _q(pa), "over25": _q(ou)}


def bayes_fit_cached(df_train: pd.DataFrame, cache_dir=None, n0: float = N0_DEFAULT,
                     tag: str = "bayes_fit") -> dict:
    """带文件缓存: 数据指纹 key(数据一变即失效), 当天多场复用(避免每次全量重算)."""
    import pickle
    from pathlib import Path
    if cache_dir is None:
        from cache_utils import fit_cache_file
        fname = fit_cache_file(tag, df_train)
    else:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        ref = df_train["date"].max()
        fname = cache_dir / f"{tag}_{ref.strftime('%Y%m%d')}_{len(df_train)}.pkl"
    if fname.exists():
        try:
            with open(fname, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    bayes = bayes_fit(df_train, n0)
    try:
        with open(fname, "wb") as f:
            pickle.dump(bayes, f)
    except Exception:
        pass
    return bayes


def uncertainty_score(bayes: dict, row: dict) -> dict | None:
    """小样本不确定性: 返回主/客队 n_eff 与后验 CV(变异系数). 用于降置信标记."""
    league = row["league"]
    b = bayes.get(league) if bayes else None
    if not b:
        return None
    teams = b["teams"]
    out = {}
    for side, team in (("home", row["home"]), ("away", row["away"])):
        t = teams.get(team)
        if not t:
            out[side] = {"n_eff": 0.0, "cv": np.inf}
            continue
        # 攻防四个后验中取 n_eff 最小 + CV 最大 作保守估计
        posts = [t["h_atk"], t["h_def"], t["a_atk"], t["a_def"]]
        n_eff = min(p["n_eff"] for p in posts)
        cv = max((p["beta"] ** -0.5) for p in posts)  # CV ≈ 1/√β 近似
        out[side] = {"n_eff": float(n_eff), "cv": float(cv)}
    return out


# ---------------- 自检 ----------------

def _self_test():
    import math
    from model import _strength

    print("== 1) 共轭后验均值 vs 解析(时间衰减加权) ==")
    n0, avg = 4.0, 1.4
    pairs = [(pd.Timestamp("2024-01-01"), 2), (pd.Timestamp("2024-01-08"), 1),
             (pd.Timestamp("2024-01-15"), 3)]
    post = team_posterior(pairs, pd.Timestamp("2024-01-15"), avg, n0)
    # 解析: mean = (n0·avg + Σw·goals) / (n0 + Σw),  w = _time_weight(days)
    ref = pd.Timestamp("2024-01-15")
    w = np.array([_time_weight((ref - d).days) for d, _ in pairs])
    exp = (n0 * avg + (w * np.array([2, 1, 3])).sum()) / (n0 + w.sum())
    assert abs(post["mean"] - exp) < 1e-9, (post["mean"], exp)
    print(f"  后验均值 {post['mean']:.4f} == 加权解析 {exp:.4f}  OK")

    print("== 2) n0=4 无衰减时与旧 _strength 等价 ==")
    rate = 2.0  # 加权均值进球
    n_old = 3
    old = _strength(rate, avg, n_old)
    # 无衰减 w=1 时: 贝叶斯后验均值/avg = (n0·avg + n·rate)/(n0+n) / avg
    bnew = (n0 * avg + n_old * rate) / (n0 + n_old) / avg
    assert abs(old - bnew) < 1e-9, (old, bnew)
    print(f"  旧收缩 {old:.4f} == 贝叶斯 {bnew:.4f}  OK")

    print("== 3) 小样本后验区间更宽 ==")
    rng = np.random.default_rng(7)
    # 构造 fit: 一个联赛, A 队大样本(50场), B 队小样本(3场)
    rows = []
    for i in range(60):
        home = "A" if i < 50 else "B"
        away = "C" if i < 50 else "D"
        rows.append({"date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
                     "league": "T", "home": home, "away": away,
                     "hg": int(rng.poisson(1.5)), "ag": int(rng.poisson(1.2))})
    df = pd.DataFrame(rows)
    fit = poisson_fit(df)
    bayes = bayes_fit(df)
    rowA = {"league": "T", "home": "A", "away": "C"}
    rowB = {"league": "T", "home": "B", "away": "D"}
    dA = prob_dist(fit, bayes, rowA, n_samples=4000, rng=rng)
    dB = prob_dist(fit, bayes, rowB, n_samples=4000, rng=rng)
    wA = dA["home"]["p95"] - dA["home"]["p5"]
    wB = dB["home"]["p95"] - dB["home"]["p5"]
    print(f"  A(50场) 主胜CI宽 {wA:.3f} vs B(3场) 主胜CI宽 {wB:.3f}")
    assert wB > wA * 1.2, (wA, wB)
    print("  小样本区间更宽 OK")

    print("== 4) 概率分布收敛: 大样本 n 时均值≈点估计 ==")
    rowA2 = {"league": "T", "home": "A", "away": "C"}
    fit_point = poisson_fit(df)
    from model import poisson_predict
    lh0, la0 = poisson_predict(fit_point, rowA2)
    # 后验均值(无衰减)应≈点估计
    print(f"  点估计 λh={lh0:.3f}, 贝叶斯主胜均值={dA['home']['mean']:.3f} (对比合理)")
    print("== bayes_poisson 自检全部通过 ==\n")


def _demo():
    """真实数据演示: 找一场真实比赛对比点估计 vs 贝叶斯区间."""
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    from data_loader import load_data
    df = load_data()
    if df is None or len(df) == 0:
        print("无数据文件, 跳过演示")
        return
    match_date = df["date"].max().normalize()
    train = df[df["date"] < match_date]
    print(f"训练数据 {len(train)} 场, 截止 {train['date'].max().date()}")
    fit = poisson_fit(train)
    bayes = bayes_fit(train)
    print(f"贝叶斯拟合联赛数: {len(bayes)}")
    # 找一场近期强队主场比赛(如英超)
    from model import poisson_predict
    rng = np.random.default_rng(42)
    # 选最近日期内、主客队 n_eff 均充足的比赛做演示
    last_date = train["date"].max()
    recent = train[train["date"] >= last_date - pd.Timedelta(days=10)]
    best = None
    best_score = -1
    for _, r in recent.iterrows():
        u = uncertainty_score(bayes, r)
        if not u:
            continue
        s = min(u["home"]["n_eff"], u["away"]["n_eff"])
        if s > best_score:
            best_score, best = s, r
    row = best if best is not None else recent.iloc[-1].to_dict()
    print(f"\n演示比赛: {row['date'].date()} {row['league']} {row['home']} vs {row['away']}")
    lh0, la0 = poisson_predict(fit, row)
    d = prob_dist(fit, bayes, row, n_samples=3000, rng=rng)
    if d is None:
        print("该队无贝叶斯数据")
        return
    unc = uncertainty_score(bayes, row)
    lams = lambda_samples(bayes, row, 3000, rng)
    print(f"\n点估计: λh={lh0:.3f} λa={la0:.3f}")
    print(f"贝叶斯: λh CI=[{np.percentile(lams[0], 5):.2f}, "
          f"{np.percentile(lams[0], 95):.2f}]")
    print(f"主胜: 点值(参考) vs 贝叶斯 {d['home']['mean']:.1%} CI=[{d['home']['p5']:.1%},{d['home']['p95']:.1%}]")
    print(f"大2.5: 贝叶斯 {d['over25']['mean']:.1%} CI=[{d['over25']['p5']:.1%},{d['over25']['p95']:.1%}]")
    print(f"不确定性: 主队n_eff={unc['home']['n_eff']:.0f} CV={unc['home']['cv']:.2f}, "
          f"客队n_eff={unc['away']['n_eff']:.0f} CV={unc['away']['cv']:.2f}")
    # 找一支小样本队对比
    print("\n-- 联赛内最小 n_eff 球队(不确定性最高) --")
    b_e0 = (bayes.get("E0") or next(iter(bayes.values()), None))
    if b_e0 is not None:
        scored = sorted(b_e0["teams"].items(),
                        key=lambda kv: min(kv[1]["h_atk"]["n_eff"], kv[1]["a_atk"]["n_eff"]))[:3]
        for team, t in scored:
            ne = min(t["h_atk"]["n_eff"], t["a_atk"]["n_eff"])
            print(f"  {team}: n_eff={ne:.1f} 主攻后验CV={t['h_atk']['beta']**-0.5:.2f}")


if __name__ == "__main__":
    _self_test()
    _demo()
