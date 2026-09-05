# -*- coding: utf-8 -*-
"""完整比赛分析报告生成器(8章节, 含实时赔率+联网伤停情报)。

用法:
    python generate_report.py 主队 客队 联赛key [日期]
    python generate_report.py Lille "Paris SG" F1 2026-08-29
    python generate_report.py Arsenal Chelsea E0 --no-intel --save

联赛key: E0英超 SP1西甲 D1德甲 I1意甲 F1法甲 N1荷甲 ...
日期格式: YYYY-MM-DD, 不传默认今天。
--no-intel: 关闭联网伤停情报检索(更快, 无ARK凭证时自动关闭)
--save: 保存报告到 analysis_records/
--no-odds: 不用实时赔率(用近期均盘估计)
"""
import sys
import os
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

import pandas as pd

from data_loader import load_master
from model import poisson_fit
from match_report import match_model_report
from bayes_poisson import bayes_fit_cached
from report_rules import analyze_rules
from report_renderer import render_full_report
from odds_source import fetch_odds


def main():
    parser = argparse.ArgumentParser(description="完整比赛分析报告生成器")
    parser.add_argument("home", help="主队名(英文, 如 Lille)")
    parser.add_argument("away", help="客队名(英文, 如 Paris SG)")
    parser.add_argument("league", help="联赛key, 如 F1/E0/SP1/D1/I1")
    parser.add_argument("date", nargs="?", default=None, help="比赛日期 YYYY-MM-DD, 默认今天")
    parser.add_argument("--no-intel", action="store_true", help="关闭联网伤停情报")
    parser.add_argument("--no-odds", action="store_true", help="不用实时赔率")
    parser.add_argument("--save", action="store_true", help="保存报告到 analysis_records/")
    parser.add_argument("--track", action="store_true",
                        help="有正EV的1X2推荐自动写入 live_tracker.json(闭环追踪)")
    args = parser.parse_args()

    match_date = pd.Timestamp(args.date) if args.date else pd.Timestamp.now().normalize()
    row = {"league": args.league, "home": args.home, "away": args.away, "date": match_date}

    print(f"[1/5] 加载数据 + 拟合泊松模型...", file=sys.stderr)
    from cache_utils import load_master_cached
    df = load_master_cached()
    train = df[df["date"] < match_date]

    # poisson_fit 缓存: 数据指纹 key(数据一变即失效), 当天多场复用(24s -> 0.1s)
    import pickle as _pickle
    from cache_utils import fit_cache_file
    _cache_file = fit_cache_file("poisson_fit", train)
    if _cache_file.exists():
        print(f"      命中拟合缓存: {_cache_file.name}", file=sys.stderr)
        with open(_cache_file, "rb") as _f:
            fit = _pickle.load(_f)
    else:
        fit = poisson_fit(train)
        try:
            with open(_cache_file, "wb") as _f:
                _pickle.dump(fit, _f)
            print(f"      拟合完成并缓存: {_cache_file.name}", file=sys.stderr)
        except Exception as _e:
            print(f"      拟合完成(缓存失败: {_e})", file=sys.stderr)

    # 贝叶斯泊松后验(含缓存): 提供 λ 样本量 n_eff, 用于不确定性标记
    print(f"      贝叶斯后验拟合(缓存复用)...", file=sys.stderr)
    try:
        bayes = bayes_fit_cached(train)
        print(f"      贝叶斯后验就绪, 覆盖联赛 {len(bayes)}", file=sys.stderr)
    except Exception as _e:
        print(f"      贝叶斯后验失败(降级为无 n_eff): {_e}", file=sys.stderr)
        bayes = None

    market_odds = None
    if not args.no_odds:
        print(f"[2/5] 获取实时赔率(composite源)...", file=sys.stderr)
        try:
            od = fetch_odds(args.home, args.away, args.league, match_date)
            market_odds = od.get("odds") if od else None
            if market_odds:
                print(f"      赔率: 主{market_odds[0]:.2f} / 平{market_odds[1]:.2f} / 客{market_odds[2]:.2f}", file=sys.stderr)
            else:
                print("      未获取到实时赔率, 用近期均盘估计", file=sys.stderr)
        except Exception as e:
            print(f"      赔率获取失败: {e}, 用近期均盘估计", file=sys.stderr)
    else:
        print("[2/5] 跳过实时赔率(用近期均盘估计)", file=sys.stderr)

    lineup = None
    injury_coef = (1.0, 1.0)
    try:
        from lineup_intel import find_event_id, fetch_lineups, injury_coefs
        _eid = find_event_id(args.home, args.away, match_date)
        if _eid:
            lineup = fetch_lineups(_eid)
            injury_coef = injury_coefs(lineup) if lineup else (1.0, 1.0)
            print(f"[2.5/5] BSD 首发: event={_eid} status={lineup.get('lineup_status') if lineup else '?'} "
                  f"| λ修正 主x{injury_coef[0]:.3f} 客x{injury_coef[1]:.3f}", file=sys.stderr)
        else:
            print("[2.5/5] 未找到 BSD 事件(无首发核验)", file=sys.stderr)
    except Exception as e:
        print(f"[2.5/5] lineup 获取失败: {e}", file=sys.stderr)

    print(f"[3/5] 生成模型报告(比分矩阵/BTTS/主客场分层/融合校准)...", file=sys.stderr)
    report = match_model_report(fit, train, row, market_odds=market_odds,
                                injury_coef=injury_coef, bayes=bayes)

    print(f"[4/5] 规则分析(强方向/双源同向/冲突分级/比分触发/置信度/意外路径)...", file=sys.stderr)
    rules = analyze_rules(report, market_odds=market_odds)

    with_intel = not args.no_intel
    ark_records = []
    if with_intel:
        # 用阿里云百炼(qwen-plus)联网检索伤停
        print(f"[5/5] 联网检索伤停/首发情报(百炼 qwen-plus)...", file=sys.stderr)
        try:
            from dashscope_search import extract_injury_json
            _cache_dir = Path(__file__).resolve().parent.parent / "analysis_records" / ".cache" / "injury"
            _r = extract_injury_json(args.home, args.away, args.league, cache_dir=str(_cache_dir))
            if _r.get("ok"):
                ark_records = _r.get("records") or []
                _src = "缓存" if _r.get("_from_cache") else f"联网(第{_r.get('attempts',1)}次)"
                print(f"      百炼 结构化伤停: {len(ark_records)} 条 [{_src}]", file=sys.stderr)
            else:
                _err = _r.get('error', {}).get('message', '?')
                _att = _r.get('attempts', 1)
                print(f"      百炼 提取失败(尝试{_att}次): {_err}", file=sys.stderr)
        except Exception as e:
            print(f"      联网情报提取异常: {e}", file=sys.stderr)
    else:
        print("[5/5] 跳过联网情报", file=sys.stderr)

    full = render_full_report(report, rules, market_odds=market_odds, with_intel=with_intel)

    # 联赛白名单/黑名单提醒 (基于walk-forward大小球回测胜率, 样本量<30场不做极端判断)
    _league_tier = {
        # 白名单: 回测胜率>60% 且 样本量≥30场, 置信度提升
        "N1": ("白名单", "荷甲 73%(15场)", "✅"), "T1": ("白名单", "土超 73%(11场)", "✅"),
        "ARG": ("白名单", "阿甲 71%(17场)", "✅"), "F2": ("白名单", "法乙 71%(17场)", "✅"),
        "MLS": ("白名单", "美职 63%(24场)", "✅"), "E3": ("白名单", "英乙 61%(36场)", "✅"),
        "B1": ("白名单", "比甲 60%(10场)", "✅"),
        # 五大联赛: 主流联赛但回测样本量不足(9-12场), 不做极端判断, 标注观察中
        "E0": ("主流联赛", "英超 50%(12场) 样本不足", "🔵"),
        "SP1": ("主流联赛", "西甲 20%(10场) 样本不足", "🔵"),
        "D1": ("主流联赛", "德甲 样本不足", "🔵"),
        "I1": ("主流联赛", "意甲 44%(9场) 样本不足", "🔵"),
        "F1": ("主流联赛", "法甲 50%(12场) 样本不足", "🔵"),
        # 黑名单: 回测胜率<45% 且 样本量≥20场, 置信度降低
        "P1": ("黑名单", "葡超 18%(11场)", "⚠️"),
        "E2": ("黑名单", "英甲 33%(33场)", "⚠️"),
        "JP1": ("黑名单", "J1 38%(21场)", "⚠️"),
        # 中超: 总数据充足(899场), 回测推荐场次少不代表模型差, 标注数据充足正常参考
        "CSL": ("主流联赛", "中超 数据充足", "🔵"),
    }
    _tier = _league_tier.get(args.league)
    if _tier:
        _tier_name, _tier_note, _tier_icon = _tier
        if _tier_name == "白名单":
            _tier_msg = f"{_tier_icon} **联赛评级: {_tier_name}({_tier_note})** — 回测表现优异, 模型置信度提升, 可重点参考"
        elif _tier_name == "主流联赛":
            _tier_msg = f"{_tier_icon} **联赛评级: {_tier_name}({_tier_note})** — 主流联赛数据充足但回测样本不足, 评级观察中, 正常参考"
        elif _tier_name == "观察中":
            _tier_msg = f"{_tier_icon} **联赛评级: {_tier_name}({_tier_note})** — 回测样本不足, 评级观察中, 正常参考"
        else:
            _tier_msg = f"{_tier_icon} **联赛评级: {_tier_name}({_tier_note})** — 回测表现较差, 模型置信度降低, 建议谨慎参考或跳过"
        # 在报告标题后插入评级提醒
        _lines = full.split("\n", 2)
        if len(_lines) >= 3:
            full = _lines[0] + "\n" + _lines[1] + "\n\n" + _tier_msg + "\n\n" + _lines[2]
        else:
            full = _tier_msg + "\n\n" + full

    # 联赛专属调校参数 (第2层+第4层: 置信度阈值+Elo K值)
    _league_tuning = {
        # 英甲: 队伍杂实力近, 高阈值过滤噪声, 低K值适应慢变化
        "E2": {"ou_threshold": 0.65, "ou_fuzzy_low": 0.45, "ou_fuzzy_high": 0.65,
               "elo_k": 24, "note": "英甲专属: 大小球阈值65%(默认55%), 模糊区45-65%, Elo K=24"},
        # 葡超/J1: 黑名单联赛, 更高阈值
        "P1": {"ou_threshold": 0.70, "ou_fuzzy_low": 0.45, "ou_fuzzy_high": 0.70,
               "elo_k": 28, "note": "葡超专属: 大小球阈值70%, 谨慎推荐"},
        "JP1": {"ou_threshold": 0.70, "ou_fuzzy_low": 0.45, "ou_fuzzy_high": 0.70,
                "elo_k": 28, "note": "J1专属: 大小球阈值70%, 谨慎推荐"},
    }
    _tuning = _league_tuning.get(args.league)
    if _tuning:
        _ou_pct = report.get("over_2_5", 0) or 0
        if _ou_pct >= _tuning["ou_threshold"]:
            _ou_status = f"✅ 达到推荐阈值({_tuning['ou_threshold']*100:.0f}%)"
        elif _tuning["ou_fuzzy_low"] <= _ou_pct < _tuning["ou_fuzzy_high"]:
            _ou_status = f"⚠️ 模糊区({_tuning['ou_fuzzy_low']*100:.0f}-{_tuning['ou_fuzzy_high']*100:.0f}%), 不推荐"
        else:
            _ou_status = f"❌ 低于阈值, 小球方向"
        _tune_msg = (f"🔧 **联赛调校**: {_tuning['note']} | 当前大2.5={_ou_pct*100:.1f}% → {_ou_status}")
        _lines = full.split("\n", 2)
        if len(_lines) >= 3:
            full = _lines[0] + "\n" + _lines[1] + "\n\n" + _tune_msg + "\n\n" + _lines[2]
        else:
            full = _tune_msg + "\n\n" + full

    if lineup:
        try:
            from lineup_intel import render_lineup_block, injury_coefs_merged
            if ark_records:
                injury_coef = injury_coefs_merged(lineup, ark_records)
            full += render_lineup_block(lineup, injury_coef, ark_records=ark_records)
        except Exception:
            pass

    # 临场伤停最终调整 (2026-09-01): 贝叶斯 n_eff 管历史数据, 伤停管本场阵容
    if ark_records:
        try:
            from strategy import injury_confidence_discount
            _disc, _veto = injury_confidence_discount(ark_records)
            if _veto:
                full += "\n\n**⛔ 临场伤停最终调整: 残阵禁出**(缺阵过多/关键位置崩, 本场不建议出单)\n"
            elif _disc < 1.0:
                full += "\n\n**⚠️ 临场伤停最终调整: 仓位×%.2f**(缺阵影响, 降仓处理)\n" % _disc
        except Exception:
            pass

    # 实盘追踪闭环 (2026-09-03): --track 且 有实时1X2赔率 且 主推1X2正EV -> 落 live_tracker
    if args.track and market_odds and report:
        try:
            _ens = report.get("ensemble") or {}
            _ph, _pd, _pa = _ens.get("home"), _ens.get("draw"), _ens.get("away")
            if all(isinstance(x, (int, float)) for x in (_ph, _pd, _pa)):
                def _devig3(h, d, a):
                    """Shin 法去水(2026-09-03 P1). 保留 _devig3 名兼容."""
                    from shin_devig import devig_shin
                    return devig_shin(h, d, a)
                fh, fd, fa = _devig3(*market_odds)
                _legs = [
                    ("主胜", _ph, market_odds[0], fh),
                    ("平局", _pd, market_odds[1], fd),
                    ("客胜", _pa, market_odds[2], fa),
                ]
                _best = None
                for _nm, _p, _pr, _fr in _legs:
                    if not (isinstance(_pr, (int, float)) and _pr > 1):
                        continue
                    _ev = _p * _pr - 1.0
                    if _ev <= 0:
                        continue
                    _st = 3 if _ev >= 0.15 else (2 if _ev >= 0.10 else 1)
                    if _best is None or _ev > _best["ev_unit"]:
                        _best = {"best_pick": _nm, "ev_unit": _ev, "stars": _st,
                                 "edge": max(0.0, (_p - _fr) * 100.0),
                                 "model_prob": [_ph, _pd, _pa],
                                 "market_prob": [fh, fd, fa],
                                 "market_odds": list(market_odds),
                                 "odds_estimated": False}
                if _best and _best["stars"] >= 1:
                    _res = {"home": args.home, "away": args.away,
                            "league": args.league, "date": match_date, **_best}
                    from tracker import record, report as _t_report
                    _rec = record(_res)
                    _rep = _t_report()
                    _settled = _rep.get("settled", 0)
                    print("\n[追踪] 已记录 %s -> %s (stars=%d)"
                          % (_rec["id"], _rec["pick"], _rec["stars"]), file=sys.stderr)
                    print("[追踪] 累计已结算 %d 条" % _settled, file=sys.stderr)
        except Exception as _te:
            print("追踪落账失败(不影响报告): %s" % repr(_te)[:150], file=sys.stderr)

    print(full)

    if args.save:
        out_dir = Path(__file__).resolve().parent.parent / "analysis_records"
        out_dir.mkdir(exist_ok=True)
        fname = out_dir / f"{match_date.date()}_{args.league}_{args.home}_vs_{args.away}.md"
        fname.write_text(full, encoding="utf-8")
        print(f"\n报告已保存: {fname}", file=sys.stderr)


if __name__ == "__main__":
    main()
