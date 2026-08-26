"""Walk-Forward 回测 —— 无泄漏、开/收盘双口径。

规则：
  1. 特征只使用严格早于比赛日期的数据（features.py 构造保证）。
  2. 训练只用 cutoff 之前的数据（XGB 每折重训）。
  3. 投注比较基准 = 去水后的开盘赔率（开赛前可得）。
  4. 同一注同时按"开盘价"和"收盘价"结算，揭示价格时点差异。
  5. 仓位 = 1/4 凯利，单注上限 10% 本金。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .markets import (devig, devig2, kelly_fraction, profit_for,
                      settle_ah, settle_ou, p_over, p_ah_quarter, p_ou_quarter)


def _get_odds(row, cols):
    """按列顺序取第一个非空赔率。"""
    for c in cols:
        v = row.get(c)
        if v is not None and not pd.isna(v) and v > 1.0:
            return float(v)
    return None


def _1x2_odds(row) -> tuple:
    """返回 (oh, od, oa, src)。优先 Pinnacle 开盘，其次 B365 开盘。"""
    oh = _get_odds(row, ["PSH", "B365H"])
    od = _get_odds(row, ["PSD", "B365D"])
    oa = _get_odds(row, ["PSA", "B365A"])
    src = "pinn" if not pd.isna(row.get("PSH")) else "b365"
    return oh, od, oa, src


def _1x2_close(row) -> tuple:
    oh = _get_odds(row, ["PSCH", "B365CH"])
    od = _get_odds(row, ["PSCD", "B365CD"])
    oa = _get_odds(row, ["PSCA", "B365CA"])
    return oh, od, oa


def _ou_odds(row, open_: bool) -> tuple:
    if open_:
        over = _get_odds(row, ["P>2.5", "B365>2.5"])
        under = _get_odds(row, ["P<2.5", "B365<2.5"])
        src = "pinn" if not pd.isna(row.get("P>2.5")) else "b365"
        return over, under, src
    return (_get_odds(row, ["PC>2.5", "B365C>2.5"]),
            _get_odds(row, ["PC<2.5", "B365C<2.5"]), None)


def _ah_odds(row, open_: bool) -> tuple:
    line = row.get("AHh")
    if line is None or pd.isna(line):
        return None, None, None
    if open_:
        return (float(line),
                _get_odds(row, ["PAHH", "B365AHH"]),
                _get_odds(row, ["PAHA", "B365AHA"]))
    return (float(line),
            _get_odds(row, ["PCAHH", "B365CAHH"]),
            _get_odds(row, ["PCAHA", "B365CAHA"]))


def run_backtest(feat: pd.DataFrame, cfg: dict, model_type: str = "poisson",
                 model=None, progress: bool = True, target: str = "1x2") -> dict:
    """执行回测，返回 {bets, preds, meta}。target: 1x2(默认) | ou(大小球2.5二分类, ML适用)"""
    bt = cfg["backtest"]
    mk = cfg["markets"]
    feat = feat.sort_values("date").reset_index(drop=True)
    start = feat["date"].min() + pd.Timedelta(days=bt["warmup_days"])
    end = feat["date"].max()
    if start >= end:
        raise ValueError("warmup 覆盖全部数据，无法回测")

    model_obj = model or _build_model(model_type, cfg)
    ml_ready = model_type in ("xgb", "lgb", "cat")
    ycol = "target_ou" if target == "ou" else "target"
    Xmat = None
    if ml_ready:
        from .features import feature_matrix
        Xmat = feature_matrix(feat, extra=cfg.get("model", {}).get("extra_ml_features", []))

    bet_records, pred_records = [], []
    bankroll = mk["initial_bankroll"]
    cutoff = start
    folds = 0
    while cutoff < end:
        fold_end = cutoff + pd.Timedelta(days=bt["retrain_days"])
        train = feat[feat["date"] < cutoff]
        test = feat[(feat["date"] >= cutoff) & (feat["date"] < fold_end)]

        if ml_ready:
            if len(train) < bt["min_train_matches"]:
                cutoff = fold_end
                continue
            model_obj.fit(Xmat.loc[train.index].values, train[ycol].values)
            folds += 1

        for _, row in test.iterrows():
            # ---- 模型概率 ----
            if ml_ready:
                X = Xmat.loc[[row.name]].values
                lam_h = lam_a = None
                if target == "1x2":
                    pa, pd_, ph = model_obj.predict_proba(X)[0]
                    mprobs = {"home": float(ph), "draw": float(pd_), "away": float(pa)}
                else:
                    # OU目标: 1X2腿置NaN, 靠edge_1x2=1.0屏蔽(或--market ou)
                    mprobs = {"home": float("nan"), "draw": float("nan"), "away": float("nan")}
            else:
                pred = model_obj.predict(row)
                mprobs = {"home": pred["p_home"], "draw": pred["p_draw"], "away": pred["p_away"]}
                lam_h, lam_a = pred["lam_h"], pred["lam_a"]

            # ---- 1X2（开盘价） ----
            oh, od, oa, src = _1x2_odds(row)
            if oh and od and oa:
                mh, md, ma = devig(oh, od, oa)
                ch, cd, ca = _1x2_close(row)
                for side, mp, mkt_p, odds_o, odds_c in [
                    ("home", mprobs["home"], mh, oh, ch),
                    ("draw", mprobs["draw"], md, od, cd),
                    ("away", mprobs["away"], ma, oa, ca),
                ]:
                    if odds_c is None:
                        odds_c = odds_o
                    if mp - mkt_p >= mk["edge_1x2"] and mk["min_odds"] <= odds_o <= mk["max_odds"]:
                        bet_records.append(_make_bet(
                            row, "1x2", f"{side}_win", mp, mkt_p, odds_o, odds_c,
                            bankroll, mk,
                            lambda r: 1.0 if (side == "home" and r["gh"] > r["ga"])
                                       else 1.0 if (side == "draw" and r["gh"] == r["ga"])
                                       else 1.0 if (side == "away" and r["gh"] < r["ga"])
                                       else -1.0,
                            lam_h, lam_a, src))
                        bankroll += bet_records[-1]["profit_open"]

            # ---- 大小球 2.5（开盘价） ----
            o_over, o_under, ou_src = _ou_odds(row, open_=True)
            if o_over and o_under:
                m_over, m_under = devig2(o_over, o_under)
                c_over, c_under, _ = _ou_odds(row, open_=False)
                line = mk.get("ou_line", 2.5)
                pred = model_obj.predict(row) if not ml_ready else None
                if ml_ready:
                    if target == "ou":
                        _po = model_obj.predict_proba(X)[0]
                        p_over_model = float(_po[1]) if len(_po) > 1 else float("nan")
                    else:
                        p_over_model = float("nan")  # 1X2 ML 不做 OU
                else:
                    p_over_model = p_ou_quarter(pred["M"], line)
                p_under_model = 1.0 - p_over_model
                for side, mp, mkt_p, odds_o, odds_c, sign in [
                    ("over", p_over_model, m_over, o_over, c_over, 1.0),
                    ("under", p_under_model, m_under, o_under, c_under, -1.0),
                ]:
                    if odds_c is None:
                        odds_c = odds_o
                    if not np.isnan(mp) and mp - mkt_p >= mk["edge_ou"] and mk["min_odds"] <= odds_o <= mk["max_odds"]:
                        bet_records.append(_make_bet(
                            row, "ou", side, mp, mkt_p, odds_o, odds_c,
                            bankroll, mk,
                            lambda r: sign * settle_ou(line, int(r["gh"] + r["ga"])),
                            lam_h, lam_a, ou_src))
                        bankroll += bet_records[-1]["profit_open"]

            # ---- 让球（开盘价） ----
            ah_line, ah_h, ah_a = _ah_odds(row, open_=True)
            if ah_h and ah_a and not ml_ready:
                m_ah, m_away_ah = devig2(ah_h, ah_a)
                pred = model_obj.predict(row)
                p_home_ah = p_ah_quarter(pred["M"], ah_line)
                p_away_ah = 1.0 - p_home_ah
                ch_h, ch_a = _ah_close(row)
                for side, mp, mkt_p, odds_o, odds_c, sign in [
                    ("home", p_home_ah, m_ah, ah_h, ch_h, 1.0),
                    ("away", p_away_ah, m_away_ah, ah_a, ch_a, -1.0),
                ]:
                    if odds_c is None:
                        odds_c = odds_o
                    if mp - mkt_p >= mk["edge_ah"] and mk["min_odds"] <= odds_o <= mk["max_odds"]:
                        bet_records.append(_make_bet(
                            row, "ah", f"{side}_{ah_line:+.2f}", mp, mkt_p, odds_o, odds_c,
                            bankroll, mk,
                            lambda r: sign * settle_ah(ah_line, int(r["gh"]), int(r["ga"])),
                            lam_h, lam_a, "pinn"))
                        bankroll += bet_records[-1]["profit_open"]

            # ---- 全量预测记录（校准/指标用） ----
            m_fav, m_fav_odds = np.nan, np.nan
            if oh and od and oa:
                m_probs = {"home": mh, "draw": md, "away": ma}
                m_fav = max(m_probs, key=m_probs.get)
                m_fav_odds = {"home": oh, "draw": od, "away": oa}[m_fav]
            pred_records.append({
                "date": row["date"], "league": row["league"], "home": row["home"],
                "away": row["away"], "gh": row["gh"], "ga": row["ga"], "target": row["target"],
                "p_home": mprobs["home"], "p_draw": mprobs["draw"], "p_away": mprobs["away"],
                "m_home": mh if oh else np.nan, "m_draw": md if oh else np.nan,
                "m_away": ma if oh else np.nan,
                "m_fav": m_fav, "m_fav_odds": m_fav_odds,
            })

        if not ml_ready:
            folds += 1
        cutoff = fold_end
        if progress:
            print(f"  折完成: {cutoff.date()} | 测试场次 {len(test)} | 累计投注 {len(bet_records)}")

    bets = pd.DataFrame(bet_records)
    preds = pd.DataFrame(pred_records)
    return {"bets": bets, "preds": preds, "folds": folds, "cfg": cfg}


def _ah_close(row):
    line, h, a = _ah_odds(row, open_=False)
    return h, a


def _make_bet(row, market, side, prob, mkt_prob, odds_o, odds_c,
              bankroll, mk, settle_fn, lam_h, lam_a, src):
    """构造一条投注记录（不更新 bankroll，由调用方按时间顺序结算）。"""
    stake = kelly_fraction(prob, odds_o, mk["kelly_fraction"], mk["kelly_cap"]) * bankroll
    r = settle_fn(row)
    return {
        "date": row["date"], "league": row["league"],
        "home": row["home"], "away": row["away"],
        "market": market, "side": side,
        "prob": round(prob, 4), "market_prob": round(mkt_prob, 4),
        "edge": round(prob - mkt_prob, 4),
        "odds_open": round(odds_o, 3), "odds_close": round(odds_c, 3) if odds_c else None,
        "stake": round(stake, 4), "settle": r,
        "profit_open": round(profit_for(r, stake, odds_o), 4),
        "profit_close": round(profit_for(r, stake, odds_c if odds_c else odds_o), 4),
        "lam_h": lam_h, "lam_a": lam_a, "odds_src": src,
    }


def _build_model(model_type, cfg):
    if model_type == "poisson":
        from .models import PoissonGoalModel
        return PoissonGoalModel(max_goals=cfg["features"]["max_goals"],
                                xg_blend=cfg.get("model", {}).get("xg_blend", 0.0))
    if model_type == "xgb":
        from .models import XGBModel
        return XGBModel(cfg["model"]["xgb_params"])
    if model_type == "lgb":
        from .models import LGBModel
        return LGBModel(cfg["model"]["lgb_params"])
    if model_type == "cat":
        from .models import CatModel
        return CatModel(cfg["model"]["cat_params"])
    raise ValueError(f"未知模型: {model_type}")
