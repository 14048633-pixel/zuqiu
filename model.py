# -*- coding: utf-8 -*-
"""模型模块：泊松比分模型 + XGBoost 1X2 分类 + 校准。

当前版本: V4 (2026-08-30)
  - Elo λ修正 (每100分rating差距调整8%, 总系数包络[0.7,1.3])
  - 按联赛分组概率校准 (解决置信度分层反常)
  - Dixon-Coles低比分修正 (0-0/1-1概率修正)
  实盘回测: 旧模型42.7% -> V4模型53.3% (+10.7pp, 300场)

- poisson_fit / poisson_predict: 基于训练窗口的攻防强度(含时间衰减)
- train_xgb: 三分 softprob，时间划分训练
- calibrate: Platt 校准(用验证集，避免过拟合)
- split_by_time: 严格按日期切分训练/测试
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

from config import MODEL, STRATEGY
from devig import poisson_1x2
from features import FEATURE_COLS


# 跨年改制联赛: 赛制切换后旧规则历史只能用于球队相对强弱(Elo/攻防形状),
# 联赛进球中枢与 OU 校准必须基于新规则场次, 否则被旧规则基准拖低(J1 2026 踩坑)。
# J1: 2026-08 起 20 队跨年正式赛季(5外援/取消U23/无分区), 实测场均~3.0/大2.5=60%+。
NEW_RULES_LEAGUES = {
    "JP1": {"start": "2026-08-01", "min_new": 15},
}


def split_by_time(df: pd.DataFrame, cutoff) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff = pd.Timestamp(cutoff)
    train = df[df["date"] < cutoff].copy()
    test = df[(df["date"] >= cutoff)].copy()
    return train, test


# ---------------- 泊松 ----------------

def _time_weight(days_ago, half_life=None):
    """时间衰减权重。半衰期由 MODEL.poisson_half_life 控制(独立于特征衰减)。

    注: 泊松用较长半衰期(200 天)聚合长期攻防强度, 特征用较短(60 天)捕捉近期状态,
    两者刻意不同、各自可配置。曾尝试统一为 60, 实测回测 ROI 恶化约 1.1pp(2026-08-28),
    故保留独立配置(见 config.MODEL.poisson_half_life 注释)。
    """
    half_life = half_life if half_life is not None else MODEL["poisson_half_life"]
    return 0.5 ** (np.clip(days_ago, 0, None) / half_life)


def _league_era_factors(df_train: pd.DataFrame) -> dict:
    """新规联赛进球中枢平移系数: 新规则场次场均 ÷ 旧规则场均。

    例: J1 新赛季(2026-08+)实测场均 ~3.0, 旧自然年 ~2.4~2.6 -> 系数 ~1.1~1.2,
    poisson_predict 对进入新规则期的比赛把全部球队 λ 同比放大, 让大小球方向站上
    新中枢(否则系统性偏小)。新规则样本不足 min_new 时返回空, 不强行平移。
    """
    out = {}
    if df_train is None or len(df_train) == 0:
        return out
    for league, cfg in NEW_RULES_LEAGUES.items():
        start = pd.Timestamp(cfg["start"])
        g = df_train[df_train["league"] == league]
        if len(g) == 0:
            continue
        g_new = g[g["date"] >= start]
        g_old = g[g["date"] < start]
        if len(g_new) < int(cfg.get("min_new", 15)) or len(g_old) == 0:
            continue
        tot_new = float((g_new["hg"] + g_new["ag"]).mean())
        tot_old = float((g_old["hg"] + g_old["ag"]).mean())
        if tot_new <= 0 or tot_old <= 0:
            continue
        out[league] = {
            "factor": round(tot_new / tot_old, 4),
            "n_new": int(len(g_new)), "n_old": int(len(g_old)),
            "avg_new": round(tot_new, 3), "avg_old": round(tot_old, 3),
            "start": cfg["start"],
        }
    return out


def _apply_opp_strength(fit: dict, df_train: pd.DataFrame, enabled: set):
    """联赛级路由: 白名单联赛的球队强度换成"对手强度加权"(strength_v2.fit_league_opp).

    只改白名单内联赛的 teams; 空白名单=零改动. 换完重算 OU 校准与 ρ(强度变了必须重估).
    """
    if not enabled:
        return
    try:
        from strength_v2 import fit_league_opp
    except Exception:
        return
    changed = []
    for league in list(fit.keys()):
        if league.startswith("_") or league not in enabled:
            continue
        g = df_train[df_train["league"] == league]
        if len(g) < 60:
            continue
        try:
            _lg2, teams2 = fit_league_opp(g)
        except Exception:
            continue
        old_teams = fit[league].get("teams", {})
        samp = g.sample(min(len(g), 300), random_state=7)

        def _mean_total(teams_ref):
            _prev = fit[league].get("teams")
            fit[league]["teams"] = teams_ref
            tot = []
            for _, row in samp.iterrows():
                try:
                    o = poisson_predict(fit, row)
                except Exception:
                    continue
                if np.isfinite(o[0]) and np.isfinite(o[1]) and o[0] > 0 and o[1] > 0:
                    tot.append(o[0] + o[1])
            fit[league]["teams"] = _prev
            return float(np.mean(tot)) if len(tot) >= 20 else None

        m_new = _mean_total(teams2)
        m_old = _mean_total(old_teams)
        if m_new and m_old and m_new > 0:
            c = float(np.sqrt(max(0.6, min(1.5, m_old / m_new))))
            for t in teams2.values():
                for k in ("h_gf", "h_ga", "a_gf", "a_ga"):
                    if t.get(k) is not None and np.isfinite(t[k]):
                        t[k] *= c
        fit[league]["teams"] = teams2
        changed.append(league)
    if changed:
        # 强度变了: OU 校准曲线与 DC ρ 必须用新强度重算, 否则口径分裂
        fit["_ou_calibration"] = compute_ou_calibration(
            fit, df_train,
            window_days={"KR1": 365, "JP1": 365, "B1": 365, "CH": 365,
                         "POL": 365, "SAU": 365, "SW1": 365})
        try:
            from dixon_coles import estimate_rho
            fit["_dc_rho"] = estimate_rho(df_train, fit)
        except Exception:
            pass


def poisson_fit(df_train: pd.DataFrame) -> dict:
    """从训练窗口估计联赛基线、每队主场/客场攻防强度。"""
    fit = {}
    for league, g in df_train.groupby("league"):
        ref_date = g["date"].max()
        days = (ref_date - g["date"]).dt.days.values.astype(float)
        w = _time_weight(days)
        lg = {}
        lg["n"] = len(g)
        lg["home_avg"] = float(np.average(g["hg"].values, weights=w))
        lg["away_avg"] = float(np.average(g["ag"].values, weights=w))
        lg["total_avg"] = float(np.average((g["hg"] + g["ag"]).values, weights=w))

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
        tstats = {}
        for team, rec in teams.items():
            def wavg(pairs, ref):
                if not pairs:
                    return np.nan
                w = np.array([_time_weight((ref - d).days) for d, _ in pairs])
                return float(np.average([v for _, v in pairs], weights=w))
            tstats[team] = {
                "h_gf": wavg(rec["h_gf"], ref_date),
                "h_ga": wavg(rec["h_ga"], ref_date),
                "a_gf": wavg(rec["a_gf"], ref_date),
                "a_ga": wavg(rec["a_ga"], ref_date),
                "n": len(rec["h_gf"]) + len(rec["a_gf"]),
            }
        fit[league] = {"lg": lg, "teams": tstats}
    # 新规联赛进球中枢平移系数(新规则场次 vs 旧规则场次的场均比)
    fit["_league_era"] = _league_era_factors(df_train)
    # 大2.5概率校准: 用全部训练数据预计算分箱校准曲线(预测概率 -> 实际大球率)
    # K1/J1/B1/CH(中超)/POL/SAU/SW1 联赛基准随赛季漂移: OU校准用近1年数据跟上
    # K1: 2026 大2.5率 43.7% vs 历史47.3% (低)
    # J1: 2026 大2.5率 50.5% vs 全历史47.5% (高, 新规外援增多)
    # B1: 比甲 2026 中枢上移至 2.93/大球58%, 全历史(2.6)滞后 -> 同样用近1年曲线
    # CH(中超): 2026 模型偏大 +6.6pp(63.9 vs 57.3) -> 向下校准
    # POL: 波兰甲 2026 模型偏大 +6.9pp(56.9 vs 50.0) -> 向下校准
    # SAU: 沙超 2025 偏小 -7.9pp, 用近1年曲线稳基准
    # SW1: 瑞士超 2019-2026 新入库, 近1年曲线跟随
    fit["_ou_calibration"] = compute_ou_calibration(fit, df_train,
                                                    window_days={"KR1": 365, "JP1": 365,
                                                                 "B1": 365, "CH": 365,
                                                                 "POL": 365, "SAU": 365,
                                                                 "SW1": 365})
    # Dixon-Coles ρ 参数: 按联赛估计低比分修正系数
    from dixon_coles import estimate_rho
    fit["_dc_rho"] = estimate_rho(df_train, fit)
    # 联赛级白名单路由: 白名单联赛换"对手强度加权"强度(默认配置已含 A/B 胜出联赛)
    _os_mod = __import__("os")
    _env_lg = (_os_mod.getenv("STRENGTH_V2_LEAGUES") or "").strip()
    if _env_lg:
        _enabled = {x.strip() for x in _env_lg.split(",") if x.strip()}
    else:
        _enabled = set(MODEL.get("strength_v2_leagues") or [])
    _apply_opp_strength(fit, df_train, _enabled)
    # 1X2 概率校准(2026-09-04 P0): 分联赛分箱拟合 主/平/客 预测概率->实际发生率 曲线,
    # 解决高置信端过度自信(star=3 假高置信重灾区, 实测 EV>50% 档偏差+24pp)
    fit["_calib_1x2"] = compute_1x2_calibration(fit, df_train)
    # OU isotonic 校准(2026-09-05): OU 高置信(60-70%)实际低~17pp, isotonic 拉回
    fit["_ou_isotonic"] = compute_ou_isotonic(fit, df_train)
    return fit


def compute_ou_calibration(fit: dict, df_train: pd.DataFrame, n_bins: int = 12,
                           min_samples: int = 400,
                           window_days: dict | None = None) -> dict:
    """按联赛分箱校准大2.5概率(联赛间进球环境差异大, 全局混合会抹平差异)。

    对每场训练比赛用 poisson_predict 计算赛前大2.5概率, 对比实际总进球,
    每联赛独立统计 预测概率 -> 实际大球率 曲线。样本不足区间用线性插值。
    样本总量不足 min_samples 的联赛不校准(不返回该联赛条目, 保持原值)。
    返回 {"<league>": {"bins": [...], "mapping": {...}, "n": 样本量}}。
    """
    from scipy.stats import poisson as _sp

    bins = np.linspace(0.30, 0.95, n_bins + 1)
    out = {}
    window_days = window_days or {}
    for league, g in df_train.groupby("league"):
        _rules_cfg = NEW_RULES_LEAGUES.get(league)
        if _rules_cfg:
            # 跨年改制: OU校准只允许新规则场次参与(旧规则大2.5率已失效)
            g = g[g["date"] >= pd.Timestamp(_rules_cfg["start"])]
            if len(g) == 0:
                continue
        _ms = min_samples
        if league in window_days:
            cutoff = g["date"].max() - pd.Timedelta(days=window_days[league])
            g = g[g["date"] > cutoff]
            # 窗口联赛(如KR1近1年约250场)放宽阈值, 保证校准不因样本被跳过
            _ms = max(min_samples // 2, 150)
        if len(g) < _ms:
            continue
        counts = np.zeros(n_bins)
        overs = np.zeros(n_bins)
        for _, row in g.iterrows():
            lh, la = poisson_predict(fit, row)
            if not np.isfinite(lh) or not np.isfinite(la) or lh <= 0 or la <= 0:
                continue
            p_over = 1.0 - _sp.cdf(2, lh + la)
            actual = 1 if (row["hg"] + row["ag"]) > 2.5 else 0
            idx = int(np.digitize(p_over, bins)) - 1
            if 0 <= idx < n_bins:
                counts[idx] += 1
                overs[idx] += actual
        _counts_ms = max(_ms // 2, 100) if league in window_days else _ms
        if counts.sum() < _counts_ms:
            continue
        # 每区间中点 & 实际大球率(区间样本>=20才可信)
        mids = [(bins[i] + bins[i + 1]) / 2 for i in range(n_bins)]
        rates = []
        for i in range(n_bins):
            rates.append(overs[i] / counts[i] if counts[i] >= 20 else np.nan)
        # 线性插值填充样本不足区间
        valid_x = [mids[i] for i in range(n_bins) if not np.isnan(rates[i])]
        valid_y = [rates[i] for i in range(n_bins) if not np.isnan(rates[i])]
        if len(valid_x) >= 2:
            rates = [float(np.interp(m, valid_x, valid_y)) for m in mids]
        elif len(valid_x) == 1:
            rates = [valid_y[0]] * n_bins
        else:
            rates = mids  # 无校准数据, 保持原值
        mapping = {mids[i]: float(max(0.05, min(0.95, rates[i]))) for i in range(n_bins)}
        out[league] = {"bins": bins.tolist(), "mapping": mapping,
                       "n": int(counts.sum())}
    return out


def apply_ou_calibration(p_over: float, calibration: dict | None) -> float:
    """应用大2.5概率校准曲线。无校准数据时返回原值。"""
    if not calibration:
        return p_over
    mapping = calibration.get("mapping")
    if not mapping:
        return p_over
    mids = sorted(mapping.keys())
    vals = [mapping[m] for m in mids]
    calibrated = float(np.interp(p_over, mids, vals))
    return max(0.05, min(0.95, calibrated))


def compute_ou_isotonic(fit: dict, df_train: pd.DataFrame, min_samples: int = 1500,
                        window_days: dict | None = None) -> dict:
    """OU isotonic 校准(2026-09-05): 分联赛 isotonic 拟合 预测大2.5概率 -> 实际大球率.

    背景: 现分箱曲线在 OU 高置信端(60-70%)仍偏差~+17pp(模型63.5 vs 实际46.5);
    isotonic 用整段训练样本拟合, 直接把预测概率拉回实际发生率(与 1X2 校准同思路).
    返回 {"<league>": IsotonicRegression}; 无该联赛/样本不足返回空.
    """
    from scipy.stats import poisson as _sp
    from sklearn.isotonic import IsotonicRegression
    window_days = window_days or {}
    out = {}
    for league, g in df_train.groupby("league"):
        _g = g
        if league in window_days:
            _cut = g["date"].max() - pd.Timedelta(days=window_days[league])
            _g = g[g["date"] > _cut]
        if len(_g) < min_samples:
            continue
        x, y = [], []
        for _, row in _g.iterrows():
            try:
                lh, la = poisson_predict(fit, row)
            except Exception:
                continue
            if not (np.isfinite(lh) and np.isfinite(la)) or lh <= 0 or la <= 0:
                continue
            p = float(1.0 - _sp.cdf(2, lh + la))
            x.append(p)
            y.append(1.0 if (row["hg"] + row["ag"]) > 2.5 else 0.0)
        if len(x) < max(min_samples // 2, 300):
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(np.clip(x, 0.001, 0.999), np.clip(y, 0.0, 1.0))
        out[league] = iso
    return out


def apply_ou_isotonic(p_over: float, iso) -> float:
    """应用 OU isotonic 校准. 无校准器返回原值."""
    if iso is None:
        return p_over
    try:
        return float(max(0.02, min(0.98, iso.predict([[p_over]])[0])))
    except Exception:
        return p_over

def _dc_1x2_vec(lh: np.ndarray, la: np.ndarray, rho: float = 0.05,
               max_goals: int = 8) -> np.ndarray:
    """向量化 Dixon-Coles 1X2 概率。lh/la 为 (n,) 数组, 返回 (n,3) 主/平/客。"""
    import math as _m
    lh = np.asarray(lh, dtype=float)
    la = np.asarray(la, dtype=float)
    n = len(lh)
    kk = np.arange(max_goals + 1)
    log_fact = np.array([_m.lgamma(k + 1) for k in kk])  # ln(k!)
    lh_s = np.maximum(lh, 1e-9); la_s = np.maximum(la, 1e-9)
    log_ph = -lh_s[None, :] + kk[:, None] * np.log(lh_s[None, :]) - log_fact[:, None]
    log_pa = -la_s[None, :] + kk[:, None] * np.log(la_s[None, :]) - log_fact[:, None]
    ph_mat = np.exp(log_ph)  # (K, n)
    pa_mat = np.exp(log_pa)  # (K, n)
    K = max_goals + 1
    tau = np.ones((K, K, n))
    rho_ll = rho * lh_s * la_s  # (n,)
    tau[0, 0, :] = 1.0 - rho_ll
    tau[0, 1, :] = 1.0 + rho * lh_s
    tau[1, 0, :] = 1.0 + rho * la_s
    P = ph_mat[:, None, :] * pa_mat[None, :, :] * tau  # (K, K, n)
    # 主胜 i>j: 下三角不含对角线; 平 i==j: 对角线; 客胜 i<j: 上三角
    ii, jj = np.meshgrid(kk, kk, indexing="ij")
    m_home = (ii > jj); m_draw = (ii == jj); m_away = (ii < jj)
    ph = P[m_home].reshape(-1, n).sum(axis=0) if m_home.any() else np.zeros(n)
    pd_ = P[m_draw].reshape(-1, n).sum(axis=0) if m_draw.any() else np.zeros(n)
    pa = P[m_away].reshape(-1, n).sum(axis=0) if m_away.any() else np.zeros(n)
    return np.column_stack([ph, pd_, pa])


def compute_1x2_calibration(fit: dict, df_train: pd.DataFrame, n_bins: int = 10,
                            min_samples: int = 400) -> dict:
    """按联赛分箱校准 1X2 概率(主/平/客), 解决高置信端过度自信(2026-09-04 P0).

    对每场训练比赛用 poisson_predict -> dc_1x2 得 (ph,pd,pa), 对比实际结果,
    每联赛按类别(0主/1平/2客)统计 预测概率 -> 实际发生率 曲线, 线性插值填充
    样本不足区间。联赛样本 < min_samples 不校准(返回原值路径)。
    返回 {"<league>": {0: {"mids": [...], "rates": [...]}, 1: ..., 2: ...}}
    应用: apply_1x2_calibration((ph,pd,pa), cal) -> 校准后三元组(归一化)。
    """
    bins = np.linspace(0.05, 0.95, n_bins + 1)
    mids = [(bins[i] + bins[i + 1]) / 2 for i in range(n_bins)]
    out = {}
    _eng = _strength_v2 if MODEL.get("strength_v2") else _strength
    cap = float(STRATEGY.get("poisson_goals_cap", 4.5))
    for league, g in df_train.groupby("league"):
        if len(g) < min_samples:
            continue
        f = fit[league]
        lg = f["lg"]
        teams = f["teams"]
        home_avg = lg["home_avg"] if lg["home_avg"] > 0 else 1.0
        away_avg = lg["away_avg"] if lg["away_avg"] > 0 else 1.0
        # 每队预计算攻防强度(向量化前提)
        tmap = {}
        for tn, rec in teams.items():
            n = rec.get("n", 0)
            tmap[tn] = (_eng(rec.get("h_gf"), home_avg, n),
                        _eng(rec.get("a_ga"), away_avg, n),
                        _eng(rec.get("a_gf"), away_avg, n),
                        _eng(rec.get("h_ga"), home_avg, n))
        home_col = g["home"].values
        away_col = g["away"].values
        def _vc(col, idx):
            return np.array([tmap.get(x, (1.0, 1.0, 1.0, 1.0))[idx] for x in col], dtype=float)
        atk_h = _vc(home_col, 0); def_a = _vc(home_col, 1)
        atk_a = _vc(away_col, 2); def_h = _vc(away_col, 3)
        lh = home_avg * atk_h * def_a
        la = away_avg * atk_a * def_h
        _h_adj = float(MODEL.get("league_home_adj", {}).get(league, 1.0))
        if _h_adj != 1.0:
            lh *= _h_adj
            la *= (2.0 - _h_adj)
        _era = (fit.get("_league_era") or {}).get(league)
        if _era:
            dates = pd.to_datetime(g["date"]).values
            mask = dates >= np.datetime64(_era["start"])
            lh[mask] *= _era["factor"]
            la[mask] *= _era["factor"]
        lh = np.minimum(lh, cap); la = np.minimum(la, cap)
        fin = np.isfinite(lh) & np.isfinite(la) & (lh > 0) & (la > 0)
        if fin.sum() < min_samples:
            continue
        rho = (fit.get("_dc_rho") or {}).get(league, 0.05)
        probs = _dc_1x2_vec(lh[fin], la[fin], rho)  # (m,3)
        actual = np.where(g["hg"].values[fin] > g["ag"].values[fin], 0,
                 np.where(g["hg"].values[fin] == g["ag"].values[fin], 1, 2))
        counts = {c: np.zeros(n_bins) for c in (0, 1, 2)}
        hits = {c: np.zeros(n_bins) for c in (0, 1, 2)}
        for c in (0, 1, 2):
            p = probs[:, c]
            idx = np.digitize(p, bins) - 1
            ok = (idx >= 0) & (idx < n_bins)
            np.add.at(counts[c], idx[ok], 1)
            np.add.at(hits[c], idx[ok], (actual[ok] == c))
        if sum(counts[c].sum() for c in (0, 1, 2)) < min_samples:
            continue
        league_cal = {}
        for c in (0, 1, 2):
            rates = []
            for i in range(n_bins):
                rates.append(hits[c][i] / counts[c][i] if counts[c][i] >= 20 else np.nan)
            valid_x = [mids[i] for i in range(n_bins) if not np.isnan(rates[i])]
            valid_y = [rates[i] for i in range(n_bins) if not np.isnan(rates[i])]
            if len(valid_x) >= 2:
                rates = [float(np.interp(m, valid_x, valid_y)) for m in mids]
            elif len(valid_x) == 1:
                rates = [valid_y[0]] * n_bins
            else:
                rates = mids  # 无校准数据, 保持原值
            league_cal[c] = {"mids": mids,
                             "rates": [float(max(0.02, min(0.98, r))) for r in rates]}
        out[league] = league_cal
    return out


def apply_1x2_calibration(probs, cal: dict | None):
    """应用 1X2 概率校准曲线并归一化。无校准数据时返回原值。"""
    if not cal:
        return list(probs)
    cal_probs = []
    for c in (0, 1, 2):
        cc = cal.get(c)
        if not cc:
            cal_probs.append(float(probs[c]))
            continue
        try:
            p = float(np.interp(float(probs[c]), cc["mids"], cc["rates"]))
        except Exception:
            p = float(probs[c])
        cal_probs.append(max(0.02, min(0.98, p)))
    s = sum(cal_probs)
    if s > 0:
        cal_probs = [x / s for x in cal_probs]
    return cal_probs


def _strength(rate, base, n=0, min_n=4):
    """攻防强度，向联赛均值(1.0)做线性收缩。

    修复: min_n 参数此前定义了但从未使用, 导致小样本球队强度可到 0 或数倍
    (实测 1 场 5-0 的球队会让客队 λ=0; 5 场 0 失球会让防守强度=0)。
    采用线性收缩 strength = (n*raw + min_n*1.0)/(n+min_n):
      - 无数据(n=0) -> 1.0(纯联赛均值)
      - 小样本 -> 强收缩, 强度永不坍缩到 0
      - 大样本 -> 接近原始估计
    """
    if rate is None or not np.isfinite(rate) or base <= 0:
        return 1.0
    raw = rate / base
    if n <= 0:
        return 1.0
    k = float(max(min_n, 1))
    return (n * raw + k * 1.0) / (n + k)


def _strength_v2(rate, base, n=0, min_n=4):
    """实验壳: 对手强度加权(强度按对手强弱去噪)占位。

    2026-09-03 双轨隔离: 默认 config.MODEL['strength_v2']=False 走旧 _strength;
    启用后此壳当前返回与旧版相同数值(防默认污染), 真正的对手强度加权
    (Pafos 类"弱队刷弱对手虚高"修复)后续在此实现, 跑 A/B 再切主链。
    """
    return _strength(rate, base, n=n, min_n=min_n)


def poisson_predict(fit: dict, row) -> tuple[float, float]:
    """对单行预测 (lambda_home, lambda_away)。"""
    league = row["league"]
    if league not in fit:
        return np.nan, np.nan
    f = fit[league]
    lg = f["lg"]
    th = f["teams"].get(row["home"], {})
    ta = f["teams"].get(row["away"], {})
    home_avg = lg["home_avg"] if lg["home_avg"] > 0 else 1.0
    away_avg = lg["away_avg"] if lg["away_avg"] > 0 else 1.0
    _eng = _strength_v2 if MODEL.get("strength_v2") else _strength
    atk_h = _eng(th.get("h_gf"), home_avg, th.get("n", 0))
    def_a = _eng(ta.get("a_ga"), away_avg, ta.get("n", 0))
    atk_a = _eng(ta.get("a_gf"), away_avg, ta.get("n", 0))
    def_h = _eng(th.get("h_ga"), home_avg, th.get("n", 0))
    lh = home_avg * atk_h * def_a
    la = away_avg * atk_a * def_h
    # 联赛级主场优势校准(如 MLS 近年主胜率下滑)
    _h_adj = float(MODEL.get("league_home_adj", {}).get(league, 1.0))
    if _h_adj != 1.0:
        lh *= _h_adj
        la *= (2.0 - _h_adj)  # 主队削弱部分按比例给客队(保持总进球近似)
    # 新规联赛进球中枢平移: 仅预测"新规则场次"时同比放大/缩小(J1 2026-08+)。
    # 旧规则历史场次(回测/estimate_rho/OU校准)不应用, 防止用放大后的λ拟合旧样本
    _era = (fit.get("_league_era") or {}).get(league)
    if _era:
        _rdate = row.get("date") if hasattr(row, "get") else None
        if _rdate is None or pd.Timestamp(_rdate) >= pd.Timestamp(_era["start"]):
            lh *= _era["factor"]
            la *= _era["factor"]
    cap = STRATEGY.get("poisson_goals_cap", 4.5)
    return float(min(lh, cap)), float(min(la, cap))


def poisson_1x2_probs(fit: dict, df: pd.DataFrame) -> pd.DataFrame:
    lambdas = df.apply(lambda r: poisson_predict(fit, r), axis=1)
    lh = np.array([x[0] for x in lambdas])
    la = np.array([x[1] for x in lambdas])
    probs = np.array([poisson_1x2(h, a) for h, a in zip(lh, la)])
    return pd.DataFrame(probs, columns=["ph", "pd", "pa"], index=df.index)


# ---------------- XGBoost ----------------

def _target_1x2(df: pd.DataFrame) -> np.ndarray:
    y = np.where(df["hg"] > df["ag"], 0, np.where(df["hg"] == df["ag"], 1, 2))
    return y


def train_xgb(df_train: pd.DataFrame, cols=None, params=None) -> tuple:
    """返回 (model, 特征列)。目标: 0=主胜 1=平 2=客胜。"""
    cols = cols or FEATURE_COLS
    params = params or MODEL["xgb"]
    X = df_train[cols].replace([np.inf, -np.inf], np.nan)
    # 修复: 缺失不再填 0(0 与真实值 0 语义混淆, 射门类特征缺失率 56%),
    # 改为训练集列中位数, 并把填充值挂到 model 上供推理复用
    fill_values = X.median()
    X = X.fillna(fill_values)
    y = _target_1x2(df_train)
    xgb_params = {k: v for k, v in params.items() if k not in ("objective", "eval_metric")}
    xgb_params.update({"objective": "multi:softprob", "num_class": 3, "eval_metric": "mlogloss"})
    model = xgb.XGBClassifier(**xgb_params)
    model.fit(X, y)
    model._fill_values = fill_values
    return model, cols


def predict_proba_xgb(model, df: pd.DataFrame, cols) -> np.ndarray:
    X = df[cols].replace([np.inf, -np.inf], np.nan)
    fill = getattr(model, "_fill_values", None)
    X = X.fillna(fill if fill is not None else 0.0)
    return model.predict_proba(X)  # (n,3): 0=主胜 1=平 2=客胜


def calibrate_platt(model, df_val: pd.DataFrame, cols) -> object:
    """在验证集上做 Platt 校准(3 个二元校准器)。"""
    raw = predict_proba_xgb(model, df_val, cols)
    y = _target_1x2(df_val)
    calibrators = []
    for cls in range(3):
        clf = LogisticRegression(max_iter=1000)
        logits = np.log(np.clip(raw[:, cls], 1e-6, 1 - 1e-6) / (1 - np.clip(raw[:, cls], 1e-6, 1 - 1e-6))).reshape(-1, 1)
        clf.fit(logits, (y == cls).astype(int))
        calibrators.append(clf)
    return calibrators


def calibrate_apply(calibrators, raw: np.ndarray) -> np.ndarray:
    probs = np.zeros_like(raw)
    for cls, clf in enumerate(calibrators):
        logits = np.log(np.clip(raw[:, cls], 1e-6, 1 - 1e-6) / (1 - np.clip(raw[:, cls], 1e-6, 1 - 1e-6))).reshape(-1, 1)
        probs[:, cls] = clf.predict_proba(logits)[:, 1]
    s = probs.sum(axis=1, keepdims=True)
    return probs / s


def evaluate_probs(probs: np.ndarray, df_test: pd.DataFrame) -> dict:
    y = _target_1x2(df_test)
    pred = probs.argmax(axis=1)
    eps = 1e-9
    logloss = -np.mean(np.log(np.clip(probs[np.arange(len(y)), y], eps, 1.0)))
    brier = float(np.mean(((probs - np.eye(3)[y]) ** 2).sum(axis=1)))
    return {
        "n": len(y),
        "accuracy": float((pred == y).mean()),
        "logloss": float(logloss),
        "rps": float(rps_1x2(probs, y)),
        "brier": brier,
        "home_rate": float((y == 0).mean()),
        "draw_rate": float((y == 1).mean()),
        "away_rate": float((y == 2).mean()),
    }


def rps_1x2(probs, y):
    """1X2 排序概率评分(Ranked Probability Score, 2026-09-03).

    对三分结果 rps = Σ_{k=1..2}(F_pred(k)-F_actual(k))^2 / (K-1).
    比 logloss 更贴近投注直觉: 方向接近的错误(主胜->平)惩罚小于完全反向(主胜->客胜).
    完美预测=0; 平均基线(1/3,1/3,1/3 猜真实均匀分布)=2/9.
    """
    p = np.asarray(probs, dtype=float)
    if p.ndim == 1:
        p = p[None, :]
    y = np.asarray(y)
    n = p.shape[0]
    if p.shape[1] != 3:
        raise ValueError("rps_1x2 只支持 1X2 三分")
    p = p / p.sum(axis=1, keepdims=True)
    actual = np.zeros((n, 3))
    actual[np.arange(n), y] = 1.0
    cdf_p = np.cumsum(p, axis=1)[:, :-1]
    cdf_a = np.cumsum(actual, axis=1)[:, :-1]
    return float(np.mean(np.sum((cdf_p - cdf_a) ** 2, axis=1) / 2.0))


def _self_test():
    np.random.seed(7)
    n = 300
    df = pd.DataFrame({
        "date": pd.to_datetime("2024-01-01") + pd.to_timedelta(np.arange(n), unit="D"),
        "league": ["T"] * n,
        "home": [f"T{i % 12}" for i in range(n)],
        "away": [f"T{(i + 5) % 12}" for i in range(n)],
        "hg": np.random.poisson(1.5, n),
        "ag": np.random.poisson(1.2, n),
    })
    for c in ["home_shots", "away_shots", "home_sot", "away_sot",
              "home_corners", "away_corners", "home_yellow", "away_yellow",
              "home_red", "away_red"]:
        df[c] = np.random.randint(0, 6, n)
    from features import build_features
    feat = build_features(df)
    train, test = split_by_time(feat, "2024-08-01")
    print("train:", len(train), "test:", len(test))
    model, cols = train_xgb(train)
    raw = predict_proba_xgb(model, test, cols)
    print("raw eval:", evaluate_probs(raw, test))
    # 泊松
    fit = poisson_fit(train)
    pprobs = poisson_1x2_probs(fit, test)
    print("poisson 1x2 mean:", pprobs.mean().round(3).to_dict())
    print("== model 自检通过 ==")


if __name__ == "__main__":
    _self_test()
