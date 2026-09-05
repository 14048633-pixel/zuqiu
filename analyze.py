# -*- coding: utf-8 -*-
"""单场分析入口。

用法: python analyze.py "<主队> <客队> <联赛> [YYYY-MM-DD]" [--no-search] [--api-key xxx]

流程(参考旧系统 SOP 并修正缺陷):
  1. 数据加载与清洗
  2. 特征构建(严格截断)
  3. 市场去水(SHIN) -> 真实概率
  4. 泊松+XGB 模型概率(仅用赛前数据训练)
  5. 亚盘蒙特卡洛 EV
  6. 风控与 EV 打星
  7. 输出 Markdown 报告
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import STRATEGY, SEARCH, DIV_CN
from data_loader import load_master
from devig import devig_1x2, invert_lambdas, poisson_1x2
from features import build_features
from model import poisson_fit, poisson_1x2_probs, train_xgb, predict_proba_xgb
from strategy import ev, kelly_fraction
from asian_handicap import ah_ev

CACHE = Path(__file__).resolve().parent / "_master_feat.pkl"


def load_data(refresh: bool = False) -> pd.DataFrame:
    if CACHE.exists() and not refresh:
        return pd.read_pickle(CACHE)
    df = load_master(include_espn=False)
    df = df[df["odds_h"].notna()].copy()
    df = build_features(df)
    df.to_pickle(CACHE)
    return df


def _find_team(history, name: str, league: str):
    name = str(name).strip().lower()
    pool = history[(history["league"] == league) & (history["home"].str.lower() == name)]
    if pool.empty:
        pool = history[(history["league"] == league) &
                       (history["home"].str.lower().str.contains(name, na=False))]
    if pool.empty:
        pool = history[(history["home"].str.lower() == name)]
    if pool.empty:
        pool = history[history["home"].str.lower().str.contains(name, na=False)]
    if pool.empty:
        return None
    return pool.iloc[0]["home"]


def analyze_match(home: str, away: str, league: str, match_date=None,
                  df=None, verbose: bool = True, with_search: bool = False,
                  search_api_key=None) -> dict:
    df = df if df is not None else load_data()
    league = league.strip()
    home_t = _find_team(df, home, league)
    away_t = _find_team(df, away, league)
    if home_t is None or away_t is None:
        raise ValueError(f"未找到球队: {home}/{away} in {league}")

    if match_date is None:
        match_date = pd.Timestamp(dt.date.today())
    else:
        match_date = pd.Timestamp(match_date)

    # 训练数据: 严格早于比赛日
    train = df[df["date"] < match_date].copy()
    if len(train) < 300:
        raise ValueError(f"赛前训练样本不足({len(train)}): {match_date.date()}")

    # 是否已赛
    played = df[(df["date"] == match_date) & (df["league"] == league) &
                (df["home"] == home_t) & (df["away"] == away_t)]
    has_result = not played.empty

    # ---- 模型(仅用赛前数据) ----
    fit = poisson_fit(train)
    row = pd.Series({"league": league, "home": home_t, "away": away_t})
    lh, la = poisson_predict_row(fit, row)
    ph, pd_, pa = poisson_1x2(lh, la)

    xgb_probs = None
    try:
        from features import features_for_match, FEATURE_COLS
        from model import calibrate_platt, calibrate_apply
        model, cols = train_xgb(train)
        feat_row = features_for_match(df, match_date, league, home_t, away_t)
        row_df = pd.DataFrame([{c: feat_row.get(c, np.nan) for c in cols}])
        raw = predict_proba_xgb(model, row_df, cols)
        # 修复: 单场分析此前不做 Platt 校准(回测做了), 导致单场概率比回测更
        # 过度自信; 现与回测一致, 用训练集最后 20%(时间)做校准切片
        val_cut = train["date"].quantile(0.8)
        val = train[train["date"] >= val_cut]
        if len(val) >= 200:
            cal = calibrate_platt(model, val, cols)
            xgb_probs = calibrate_apply(cal, raw)[0]
        else:
            xgb_probs = raw[0]
    except Exception as exc:
        if verbose:
            print(f"(XGB skip: {exc})")

    if xgb_probs is not None:
        p_h = 0.5 * ph + 0.5 * xgb_probs[0]
        p_d = 0.5 * pd_ + 0.5 * xgb_probs[1]
        p_a = 0.5 * pa + 0.5 * xgb_probs[2]
    else:
        p_h, p_d, p_a = ph, pd_, pa
    s = p_h + p_d + p_a
    p_h, p_d, p_a = p_h / s, p_d / s, p_a / s

    # ---- 市场去水 ----
    if has_result:
        odds = (played.iloc[0]["odds_h"], played.iloc[0]["odds_d"], played.iloc[0]["odds_a"])
        odds_source = "result"
        odds_estimated = False
    else:
        # 未来场次: 统一走盘口源适配器(近期均盘近似或实时盘口源)
        # 2026-08-28: odds_estimated 改为跟随盘口源的 estimated 标志(实时源=False),
        # 修复原先 not has_result 一刀切导致 live 源接入后星级仍被压到 3 的问题。
        from odds_source import fetch_odds
        odds_res = fetch_odds(home_t, away_t, league, match_date,
                              train=train, df=df)
        odds = odds_res["odds"]
        odds_source = odds_res.get("source", "recent")
        odds_estimated = bool(odds_res.get("estimated", True))
    mkt = devig_1x2(*odds) if all(o and o > 1 for o in odds) else None

    # ---- 亚盘 EV(模型 λ) ----
    # line = ?????(?=????=???)
    # unify: invert blend probs back to lambdas (AH/OU consistent with 1X2)
    try:
        lh_r, la_r, _ = invert_lambdas(p_h, p_d, p_a)
    except RuntimeError:
        lh_r, la_r = lh, la

    ah_lines = [1.25, 1.0, 0.75, 0.5, 0.25, 0.0, -0.25, -0.5, -0.75]
    ah_report = []
    if mkt is not None:
        for line in ah_lines:
            ev_home = ah_ev(lh_r, la_r, line, 1.95, n=20000, seed=1)
            # 修复: 客队 EV 原先误用原始 λ(la,lh), 与主队的反推 λ(lh_r,la_r) 不一致,
            # 实测差异可达 0.088 且符号翻转; 统一为反推 λ(la_r, lh_r)
            ev_away = ah_ev(la_r, lh_r, -line, 1.95, n=20000, seed=1)
            ah_report.append({"line": line, "ev_home": ev_home, "ev_away": ev_away})

    # ---- 风控与打星 ----
    result = {
        "home": home_t, "away": away_t, "league": league, "date": match_date,
        "has_result": has_result,
        "actual": (int(played.iloc[0]["hg"]), int(played.iloc[0]["ag"])) if has_result else None,
        "lambda": (lh_r, la_r),
        "lambda_raw": (lh, la),
        "model_prob": (p_h, p_d, p_a),
        "poisson_prob": (ph, pd_, pa),
        "xgb_prob": tuple(xgb_probs) if xgb_probs is not None else None,
        "market_odds": odds,
        "odds_estimated": odds_estimated,
        "odds_source": odds_source,
        "market_prob": mkt,
        "ah_report": ah_report,
        "total_over25": 1.0 - sum(poisson_pmf_total(lh_r + la_r, k) for k in range(3)),
    }
    result.update(_rating(result))
    if with_search:
        try:
            backend = SEARCH.get("backend", "ark")
            if backend == "ark":
                from ark_search import gather_match_intel
                result["search"] = gather_match_intel(
                    home_t, away_t, DIV_CN.get(league, league),
                    max_queries=SEARCH["max_queries"],
                    per_query_sleep=SEARCH["per_query_sleep"],
                    max_output_tokens=SEARCH.get("ark", {}).get("max_output_tokens", 2048),
                    api_key=search_api_key)
            else:
                from search import gather_match_intel
                result["search"] = gather_match_intel(
                    home_t, away_t, DIV_CN.get(league, league),
                    count=SEARCH["count"], max_queries=SEARCH["max_queries"],
                    per_query_sleep=SEARCH["per_query_sleep"],
                    time_range=SEARCH["time_range"], auth_level=SEARCH["auth_level"],
                    query_rewrite=SEARCH["query_rewrite"],
                    api_key=search_api_key)
        except Exception as exc:
            result["search"] = {"enabled": False, "reason": f"error: {exc}",
                                "results": [], "queries": []}
    return result


def poisson_predict_row(fit, row):
    from model import poisson_predict
    return poisson_predict(fit, row)


def poisson_pmf_total(lam_total, k):
    import math
    return math.exp(-lam_total) * lam_total ** k / math.factorial(k)


def _rating(res: dict) -> dict:
    """打星: 以 EV 为主口径(结合概率差与置信度), 未来场次(估计赔率)自动降级。

    修复: 原先只用概率差 edge 打星(2 星分支还是死代码), 忽略 EV;
    高赔冷门概率差小而 EV 大, 或热门概率差大而 EV 小, 会错配。
    现要求 EV 与 edge 双确认, 避免高赔冷门虚高。
    """
    p = res["model_prob"]
    mkt = res["market_prob"]
    if mkt is None:
        return {"stars": 0, "best_pick": None, "edge": 0.0, "ev_unit": 0.0,
                "kelly": 0.0, "note": "无市场赔率，无法评估边际"}
    edge = np.array(p) - np.array(mkt)
    idx = int(np.argmax(edge))
    o = res["market_odds"][idx]
    best_edge = float(edge[idx])
    best_ev = ev(p[idx], o)
    kelly = kelly_fraction(p[idx], o)
    names = ["主胜", "平局", "客胜"]
    stars = 0
    if best_ev >= 0.03 and best_edge >= 0.03:
        stars = 2
    if best_ev >= 0.05 and best_edge >= 0.04:
        stars = 3
    if best_ev >= 0.08 and best_edge >= 0.05 and p[idx] >= 0.45:
        stars = 4
    if best_ev >= 0.10 and best_edge >= 0.08 and p[idx] >= 0.5:
        stars = 5
    # 未来场次: 赔率为近期均盘估计, 不确定性大 -> 星级上限 3
    if res.get("odds_estimated") and stars >= 4:
        stars = 3
    note = f"最优方向 {names[idx]}: 模型 {p[idx]:.1%} vs 市场 {mkt[idx]:.1%}"
    if res.get("odds_estimated") and stars >= 3:
        note += " | 赔率为估计值, 星级已降级, 请以实时盘口复核"
    return {
        "stars": stars, "best_pick": names[idx], "edge": best_edge,
        "ev_unit": best_ev, "kelly": kelly, "note": note,
    }


def render_markdown(res: dict) -> str:
    lines = []
    lines.append(f"# 足球分析报告: {res['home']} vs {res['away']}")
    lines.append(f"- 联赛: {res['league']} | 日期: {res['date'].date()}")
    lines.append(f"- Odds 源: {res.get('odds_source', '?')}" + (" (estimated, 需复核)" if res.get("odds_estimated") else ""))
    if res["has_result"]:
        lines.append(f"- 赛果: {res['actual'][0]}:{res['actual'][1]}")
    lines.append("")
    lh, la = res["lambda"]
    lines.append("## 1. 比分模型(泊松)")
    lines.append(f"- 主队期望进球 λ={lh:.2f} | 客队期望进球 λ={la:.2f}")
    lines.append(f"- 总进球期望 {lh + la:.2f} | 大2.5概率 {res['total_over25']:.1%}")
    lines.append("")
    ph, pd_, pa = res["model_prob"]
    lines.append("## 2. 概率")
    lines.append(f"| 方向 | 模型概率 | 市场去水概率 | 边际 |")
    lines.append(f"|------|---------|-------------|------|")
    mkt = res["market_prob"]
    for i, name in enumerate(["主胜", "平局", "客胜"]):
        mp = [ph, pd_, pa][i]
        mk = mkt[i] if mkt else float("nan")
        lines.append(f"| {name} | {mp:.1%} | {mk:.1%} | {mp - mk:+.1%} |")
    lines.append("")
    lines.append("## 3. EV 与仓位")
    lines.append(f"- **打星**: {'★' * res['stars']}{'☆' * (5 - res['stars'])} ({res['stars']}/5)")
    lines.append(f"- 最优方向: {res['best_pick']} | 边际 {res['edge']:+.1%} | "
                 f"单位EV {res['ev_unit']:+.3f} | 凯利仓位 {res['kelly']:.2%}")
    lines.append(f"- 提示: {res['note']}")
    lines.append("")
    lines.append("## 4. 亚盘蒙特卡洛 EV(水位 1.95)")
    lines.append("| 盘口(主让) | 主队EV | 客队EV |")
    lines.append("|-----------|--------|--------|")
    for ah in res["ah_report"]:
        lines.append(f"| {ah['line']:+.2f} | {ah['ev_home']:+.3f} | {ah['ev_away']:+.3f} |")
    lines.append("")
    lines.append("## 5. 风控提示")
    if res["stars"] >= 4:
        lines.append("- 高置信信号，可考虑按凯利仓位下注，注意串关相关性。")
    elif res["stars"] >= 3:
        lines.append("- 中等信号，建议半仓，严格止损。")
    else:
        lines.append("- 无优势或数据不足，建议观望。")
    if res["has_result"] and res["actual"]:
        pred_idx = int(np.argmax(res["model_prob"]))
        actual = 0 if res["actual"][0] > res["actual"][1] else (1 if res["actual"][0] == res["actual"][1] else 2)
        names = ["主胜", "平局", "客胜"]
        lines.append(f"- 回测校验: 模型预测={names[pred_idx]} 实际={names[actual]} -> " + ("正确" if pred_idx == actual else "错误"))
    search = res.get("search")
    if search is not None:
        lines.append("")
        lines.append("## 6. 情报检索(火山引擎联网)")
        if search.get("enabled"):
            answers = search.get("answers") or []
            if answers:
                lines.append(f"- **AI 情报摘要**({search.get('backend', 'ark')} 联网): {answers[0]['text'][:400]}")
            results = search.get("results") or []
            if not results:
                lines.append(f"- 未检索到有效引用({len(search.get('queries') or [])} 组查询)")
            for it in results[:8]:
                lines.append(f"- **{it.get('title', '')}**")
                if it.get("site"):
                    lines.append(f"  - 来源: {it['site']}")
                if it.get("url"):
                    lines.append(f"  - {it['url']}")
                if it.get("publish_time"):
                    lines.append(f"  - 时间: {it['publish_time']}")
                if it.get("summary"):
                    lines.append(f"  - {it['summary'][:200]}")
            if search.get("warnings"):
                lines.append(f"- 提示: {';'.join(search['warnings'][:3])}")
        else:
            if SEARCH.get("backend", "ark") == "ark":
                lines.append("- 未启用: 请配置 ARK_API_KEY + ARK_ENDPOINT_ID(.env)")
            else:
                lines.append("- 未启用: 请配置 WEB_SEARCH_API_KEY(联网搜索控制台创建)")
    return "\n".join(lines)


def main(argv=None):
    argv = argv if argv is not None else list(sys.argv[1:])
    if len(argv) < 3:
        print(__doc__)
        return
    with_search = True
    track = True
    save_report = True
    api_key = None
    if "--no-search" in argv:
        with_search = False
        argv.remove("--no-search")
    if "--no-save" in argv:
        # 沙箱/只读环境: 不写任何盘(报告 + 追踪), 纯 stdout 输出
        save_report = False
        track = False
        argv.remove("--no-save")
    if "--no-track" in argv:
        track = False
        argv.remove("--no-track")
    if "--api-key" in argv:
        i = argv.index("--api-key")
        if i + 1 < len(argv):
            api_key = argv.pop(i + 1)
        argv.pop(i)
    if with_search and not api_key:
        backend = SEARCH.get("backend", "ark")
        if backend == "ark":
            from ark_search import has_credentials
            cred_msg = "ARK_API_KEY + ARK_ENDPOINT_ID"
        else:
            from search import has_credentials
            cred_msg = "WEB_SEARCH_API_KEY"
        if not has_credentials():
            print(f"[联网检索] 未配置 {cred_msg}，跳过情报检索(不影响模型分析)")
            with_search = False
    home, away, league = argv[0], argv[1], argv[2]
    match_date = argv[3] if len(argv) > 3 else None
    df = load_data()
    res = analyze_match(home, away, league, match_date, df=df,
                        with_search=with_search, search_api_key=api_key)
    print(render_markdown(res))
    # 落盘(沙箱/只读环境可用 --no-save 跳过)
    if save_report:
        out_dir = Path(__file__).resolve().parent.parent / "analysis_records"
        try:
            out_dir.mkdir(exist_ok=True)
            fname = out_dir / f"{res['date'].date()}_{res['league']}_{res['home']}_vs_{res['away']}.md"
            fname.write_text(render_markdown(res), encoding="utf-8")
            print(f"\n报告已保存: {fname}")
        except PermissionError as e:
            print(f"\n[警告] 写报告被拦截(沙箱/权限): {e}")
            print("[提示] 可用 --no-save 跳过落盘纯输出, 或换到有写权限的目录运行")
    # 实盘追踪: 分析后自动落库(有市场赔率才记)
    if track and res.get("market_odds") and res.get("stars", 0) >= 1:
        from tracker import record, report
        rec = record(res)
        rep = report()
        s = rep["settled"]
        print(f"\n[追踪] 已记录 {rec['id']} -> {rec['pick']} "
              f"(stars={rec['stars']}, odds_source={rec['odds_source']})")
        print(f"[追踪] 累计已结算 {s} 条" +
              (f", ROI={rep['all']['roi']:.1%}, 命中={rep['all']['hit_rate']:.0%}"
               if rep["all"]["n"] else ""))
        if not rep["conclusion_ready"]:
            from tracker import MIN_SAMPLE
            print(f"[追踪] 样本 < {MIN_SAMPLE} 条, 暂不出结论")


if __name__ == "__main__":
    main()
