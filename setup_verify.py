"""
目标机一键部署 + 验证脚本
===========================
在另一台电脑上运行本脚本, 自动完成:
  1. 检查 Python 版本
  2. 检查并安装全部依赖 (pip install)
  3. 验证所有核心模块可导入
  4. 运行回归测试 (regression_test.py) 确认全绿
  5. 验证数据文件完整性

用法: python setup_verify.py
"""
import sys
import os
import subprocess
import json

sys.stdout.reconfigure(encoding='utf-8')

FAILURES = []


def step(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def check(name, cond, detail=""):
    if cond:
        print(f"  ✅ {name} {detail}")
    else:
        FAILURES.append(name)
        print(f"  ❌ {name} {detail}")


def main():
    print("足球预测系统 - 一键部署验证")
    print("=" * 70)

    # 1. Python版本
    step("1. Python 环境检查")
    v = sys.version_info
    check("Python版本 >= 3.10", v >= (3, 10), f"当前 {v.major}.{v.minor}.{v.micro}")
    check("运行目录正确(应有auto_sop.py)", os.path.exists("auto_sop.py"))

    # 2. 依赖安装
    step("2. 依赖检查与安装")
    # (pip包名, 导入模块名)  — 包名≠模块名: scikit-learn->sklearn, python-dotenv->dotenv, imbalanced-learn->imblearn
    required = [
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("scikit-learn", "sklearn"),
        ("xgboost", "xgboost"),
        ("requests", "requests"),
        ("python-dotenv", "dotenv"),
        ("matplotlib", "matplotlib"),
        ("seaborn", "seaborn"),
        ("imbalanced-learn", "imblearn"),
        ("joblib", "joblib"),
    ]
    to_install = []
    for pkg, mod in required:
        try:
            __import__(mod)
            print(f"  ✅ {pkg} 已安装")
        except ImportError:
            to_install.append(pkg)
            print(f"  ⚠️ {pkg} 未安装, 需要安装")

    if to_install:
        print(f"\n  安装缺失依赖: {', '.join(to_install)} ...")
        r = subprocess.run([sys.executable, "-m", "pip", "install"] + to_install,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            print("  ✅ 依赖安装成功")
        else:
            print(f"  ❌ 依赖安装失败: {r.stderr[-300:]}")
            FAILURES.append("依赖安装")
    else:
        print("  ✅ 所有依赖已就绪")

    # 3. 核心模块导入
    step("3. 核心模块导入验证")
    sys.path.insert(0, 'src')
    sys.path.insert(0, 'src/strategy')
    sys.path.insert(0, 'src/rules')
    sys.path.insert(0, 'src/features')
    modules = [
        "over_under_ml_advanced", "betting_strategy", "bet_validator",
        "rule_engine_v2", "handicap_rules", "feature_extractor",
        "football_agent", "upset_engine", "upset_engine_v2",
        "collect_strategy_data",
    ]
    for m in modules:
        try:
            __import__(m)
            print(f"  ✅ {m}")
        except Exception as e:
            FAILURES.append(m)
            print(f"  ❌ {m}: {e}")

    # 4. 数据文件完整性
    step("4. 数据文件完整性")
    data_files = [
        "strategy_data/strong_team_deep_handicap.json",
        "strategy_data/normal_handicap.json",
        "strategy_data/bets_20260805_cl2.json",
        "strategy_data/denmark_cup_8matches_20260805.json",
        "strategy_data/winrate_stats.json",
        "strategy_data/bet_execution_review.json",
        "strategy_data/ucl_qualifier_settlement_20260806.json",
        "data/raw/mls_matches.csv",
        "SOP_30STEP.md",
        "SESSION_STATE.md",
        "AGENTS.md",
    ]
    for f in data_files:
        check(f, os.path.exists(f))
        if os.path.exists(f) and f.endswith('.json'):
            try:
                json.load(open(f, encoding='utf-8'))
            except Exception as e:
                FAILURES.append(f)
                print(f"     ❌ JSON解析失败: {e}")

    # 5. 回归测试
    step("5. 回归测试 (历史正确结论完整性)")
    if os.path.exists("regression_test.py"):
        r = subprocess.run([sys.executable, "regression_test.py"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout)
        if r.returncode != 0:
            FAILURES.append("回归测试")
            print(r.stderr[-500:])
    else:
        check("regression_test.py 存在", False)
        FAILURES.append("regression_test.py")

    # 6. 冷门引擎迁移包验证
    step("6. 冷门引擎迁移包验证")
    if os.path.exists("upset_engine_migration/validate.py"):
        r = subprocess.run([sys.executable, "validate.py"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd="upset_engine_migration")
        ok = r.returncode == 0 and '全部验证通过' in r.stdout
        last_line = r.stdout.strip().split('\n')[-1] if r.stdout else ''
        check("冷门引擎验证通过", ok, f"| {last_line}")
    else:
        check("冷门引擎迁移包存在", False)

    # 结果
    step("部署结果")
    if FAILURES:
        print(f"  ❌ {len(FAILURES)} 项未通过: {', '.join(FAILURES)}")
        sys.exit(1)
    else:
        print("  🎉 全部通过! 系统部署成功, 可正常运行")
        print()
        print("  下一步:")
        print("    1. 检查 .env 中的 API keys (DEEPSEEK/DOUBAO等)")
        print("    2. 运行 python auto_sop.py 开始分析")
        sys.exit(0)


if __name__ == '__main__':
    main()
