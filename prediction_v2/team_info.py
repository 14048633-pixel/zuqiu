"""队伍赛前信息查询 —— 基于 football-data 数据集（严格只用开赛前数据，无泄漏）
================================================
用法:
  python team_info.py "西甲" "Sevilla" "Vallecano" 2026-08-15
输出: 联赛基准 / 两队近10&近5场(总/主场或客场) / 攻防强度 / Elo / 交锋历史
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.predict_api import feature_row_from_dataset

HERE = os.path.dirname(os.path.abspath(__file__))


def fnum(v, nd=2):
    try:
        v = float(v)
        return round(v, nd) if v == v else None
    except (TypeError, ValueError):
        return None


def pct(v):
    v = fnum(v, 3)
    return f"{v:.1%}" if v is not None else "?"


def fmt(v, suffix=""):
    return f"{v}{suffix}" if v is not None else "无"


def show_team(tag, row, home):
    p = "主队" if home else "客队"
    elo = fnum(row.get("elo_home")) if home else fnum(row.get("elo_away"))
    att = fnum(row.get("att_home")) if home else fnum(row.get("att_away"))
    deff = fnum(row.get("def_home")) if home else fnum(row.get("def_away"))
    if home:
        g10 = ("gf_h10", "ga_h10", "pts_h10")
        g5 = ("gf_h5", "ga_h5", "pts_h5")
        l10 = ("gf_home_h10", "ga_home_h10")
        l5 = ("gf_home_h5", "ga_home_h5")
        loc = "主场"
    else:
        g10 = ("gf_a10", "ga_a10", "pts_a10")
        g5 = ("gf_a5", "ga_a5", "pts_a5")
        l10 = ("gf_away_a10", "ga_away_a10")
        l5 = ("gf_away_a5", "ga_away_a5")
        loc = "客场"
    print(f"\n[{p} {tag}]  Elo {fmt(elo):<8} 攻{fmt(att):<6} 防{fmt(deff)}")
    print(f"  近10场: 进{fmt(fnum(row.get(g10[0])))} 失{fmt(fnum(row.get(g10[1])))} 积分{fmt(fnum(row.get(g10[2]), 0))}")
    print(f"  近5场 : 进{fmt(fnum(row.get(g5[0])))} 失{fmt(fnum(row.get(g5[1])))} 积分{fmt(fnum(row.get(g5[2]), 0))}")
    print(f"  {loc}近10: 进{fmt(fnum(row.get(l10[0])))} 失{fmt(fnum(row.get(l10[1])))}   "
          f"{loc}近5: 进{fmt(fnum(row.get(l5[0])))} 失{fmt(fnum(row.get(l5[1])))}")


def main():
    ap = argparse.ArgumentParser(description="队伍赛前信息")
    ap.add_argument("league")
    ap.add_argument("home")
    ap.add_argument("away")
    ap.add_argument("date")
    ap.add_argument("--config", default=os.path.join(HERE, "config.yaml"))
    args = ap.parse_args()

    row = feature_row_from_dataset(args.league, args.home, args.away, args.date)

    print("=" * 60)
    print(f"  队伍赛前信息  ({args.league}, {args.date})")
    print("=" * 60)
    lh = fnum(row.get("league_avg_home"))
    la = fnum(row.get("league_avg_away"))
    lt = fnum(row.get("league_avg_total"))
    sidx = fnum(row.get("league_scoring_idx"))
    ls = fnum(row.get("league_strength"), 0)
    print(f"[联赛基准] 场均主{fmt(lh)}/客{fmt(la)} 总{fmt(lt)} | 进球强弱系数{fmt(sidx)} | 联赛Elo{fmt(ls)}")

    show_team(args.home, row, True)
    show_team(args.away, row, False)

    n5 = int(row.get("h2h_n5") or 0)
    n3 = int(row.get("h2h_n3") or 0)
    if n5:
        print(f"\n[交锋 近{n5}场] 场均总{fmt(fnum(row.get('h2h_total5')))} "
              f"主胜{pct(row.get('h2h_h_win5'))} 客胜{pct(row.get('h2h_a_win5'))} 平{pct(row.get('h2h_draw5'))}"
              + (f"  | 近{n3}场: 总{fmt(fnum(row.get('h2h_total3')))} "
                 f"主胜{pct(row.get('h2h_h_win3'))} 客胜{pct(row.get('h2h_a_win3'))} 平{pct(row.get('h2h_draw3'))}" if n3 else ""))
    else:
        print("\n[交锋] 两队近期无交手记录")

    print("\n提示: 想看两队交锋后的完整预测(含赔率/EV/凯利), 用 run_predict.py 加赔率参数。")


if __name__ == "__main__":
    main()
