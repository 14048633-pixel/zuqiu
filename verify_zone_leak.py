"""联赛真值区间防时间穿越校验 (SOP 校准生成规则落地)
================================================================
规则:
  1. 滚动时间窗口: 区间文件必须声明 data_window {start, end},
     end 必须 < 当前比赛日期(或 --match-date), 禁止使用未来赛果校准赛前判断。
  2. 样本校验: 单联赛 sample_n < 300 时, 不建立独立区间,
     应合并同级别联赛共用基准 -> 标记 WARN。
  3. 修改任何 *_odds_zones.json 后必须运行本脚本 + 回归测试。

用法:
  python verify_zone_leak.py                          # 校验所有区间文件 vs 今天
  python verify_zone_leak.py --match-date 2026-08-16  # 校验 vs 指定比赛日
  python verify_zone_leak.py --strict                 # WARN 也按失败退出
退出码: 0=通过  1=有ERROR  2=有WARN(非strict)
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, date

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
STRATEGY_DIR = os.path.join(HERE, "strategy_data")
MIN_SAMPLES = 300  # 与 strategy_data/system_config.json zone_calibration.min_samples 一致


def check_zone_file(path, match_date, strict=False):
    """校验单个区间文件, 返回 (errors, warns)。"""
    errors, warns = [], []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return ["无法解析 %s: %s" % (os.path.basename(path), e)], []

    league = data.get("league", os.path.basename(path))
    meta = data.get("metadata", {})

    # 1) 元数据必须存在
    window = meta.get("data_window")
    sample_n = meta.get("sample_n")
    if not window or not window.get("start") or not window.get("end"):
        errors.append("%s: 缺少 metadata.data_window{start,end}, 无法校验时间穿越" % league)
    else:
        try:
            w_end = datetime.strptime(window["end"], "%Y-%m-%d").date()
        except ValueError:
            errors.append("%s: data_window.end 格式错误(应为YYYY-MM-DD): %s" % (league, window["end"]))
            w_end = None
        if w_end and w_end > match_date:
            errors.append("%s: data_window.end=%s 晚于比赛日%s → 用未来赛果校准, 时间穿越!" %
                          (league, w_end, match_date))
        elif w_end and w_end == match_date:
            warns.append("%s: data_window.end=%s 与比赛日同日, 边界样本慎用" % (league, w_end))

    # 2) 样本量校验
    if sample_n is None:
        errors.append("%s: 缺少 metadata.sample_n, 无法校验样本量" % league)
    elif sample_n < MIN_SAMPLES:
        warns.append("%s: sample_n=%d < %d → 样本不足, 禁用独立区间, 合并同级别联赛基准" %
                     (league, sample_n, MIN_SAMPLES))

    # 3) 生成规则标注
    if meta.get("generation") != "rolling_window":
        warns.append("%s: metadata.generation 未标注 rolling_window, 无法确认滚动窗口训练" % league)

    return errors, warns


def main():
    ap = argparse.ArgumentParser(description="联赛真值区间防时间穿越校验")
    ap.add_argument("--match-date", default=None, help="比赛日 YYYY-MM-DD, 缺省=今天")
    ap.add_argument("--strict", action="store_true", help="WARN 也按失败退出")
    args = ap.parse_args()

    match_date = args.match_date
    if match_date:
        try:
            match_date = datetime.strptime(match_date, "%Y-%m-%d").date()
        except ValueError:
            print("❌ --match-date 格式错误: 应为 YYYY-MM-DD")
            sys.exit(1)
    else:
        match_date = date.today()
    print("比赛日: %s" % match_date)

    files = sorted(glob.glob(os.path.join(STRATEGY_DIR, "*_odds_zones.json")))
    if not files:
        print("❌ 未找到任何 *_odds_zones.json")
        sys.exit(1)

    all_errors, all_warns = [], []
    for f in files:
        name = os.path.basename(f)
        errors, warns = check_zone_file(f, match_date, args.strict)
        status = "✅" if not errors and not warns else ("⚠️" if errors else "❗")
        print("%s %-24s errors=%d warns=%d" % (status, name, len(errors), len(warns)))
        for e in errors:
            print("    ❌ " + e)
        for w in warns:
            print("    ⚠️  " + w)
        all_errors.extend(errors)
        all_warns.extend(warns)

    print("-" * 60)
    if all_errors:
        print("结果: %d ERROR" % len(all_errors))
        sys.exit(1)
    if all_warns and args.strict:
        print("结果: %d WARN (strict 模式按失败)" % len(all_warns))
        sys.exit(2)
    if all_warns:
        print("结果: %d WARN (不阻塞, 但需人工确认)" % len(all_warns))
        sys.exit(2)
    print("结果: ✅ 全部通过, 无时间穿越, 样本充足")
    sys.exit(0)


if __name__ == "__main__":
    main()