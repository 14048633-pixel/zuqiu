"""
临场盘口对比工具 - 判断"方向还是陷阱"
============================================
用法:
  1. 分析时输入初盘(已存)
  2. 开赛前30分钟输入临场最新赔率
  3. 程序自动对比初盘vs临场, 判断方向/陷阱

判断依据: J1/K2临场盘口变化规律(真实资金流向)
  - 升盘+降水 = 可信方向
  - 升盘+升水 = 诱上陷阱
  - 深盘升盘 = 诱热难穿盘
  - 急速跳水降水 = 大热必死
  - 无利空退盘+升水 = 阻上洗筹
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')


def parse_odds(s):
    """解析赔率 '主1.77 平3.29 客4.50' → (1.77, 3.29, 4.50)"""
    import re
    nums = re.findall(r'(\d+\.\d+)', s)
    return [float(x) for x in nums]


def parse_hdp(s):
    """解析让球 '-0.5/1 @2.03/1.85' → (盘口值, 上盘水位)"""
    import re
    # 盘口
    m = re.search(r'([+-]?\d+\.?\d*(?:/\d+\.?\d*)?)', s)
    hdp = m.group(1) if m else '0'
    # 水位
    waters = re.findall(r'(\d+\.\d+)', s)
    return hdp, waters


def hdp_to_val(hdp):
    """盘口字符串转数值"""
    hdp = hdp.strip()
    if hdp == '0' or hdp == '':
        return 0.0
    if '/' in hdp:
        parts = hdp.split('/')
        sign1 = -1 if parts[0].startswith('-') else 1
        v1 = float(parts[0].replace('+','').replace('-',''))
        v2 = float(parts[1].replace('+','').replace('-',''))
        return sign1 * (v1 + v2) / 2
    return float(hdp)


def judge(hdp_ini, water_ini, hdp_now, water_now, hot_side='home', hours_to_kickoff=None):
    """判断方向/陷阱 (v2: 含时间衰减权重 + 风险等级量化)
    hdp_ini/now: 盘口值(负=主让, 正值=主受让)
    water_ini/now: 上盘水位
    hours_to_kickoff: 距开赛小时数(>=0); 提供则叠加时间权重与风险等级
    """
    import os
    abs_ini = abs(hdp_ini)
    abs_now = abs(hdp_now)
    hdp_change = abs_now - abs_ini  # 正=升盘(让更多), 负=降盘
    water_change = water_now - water_ini  # 正=升水, 负=降水

    print()
    print(f"初盘: 让{hdp_ini} 水位{water_ini}")
    print(f"临场: 让{hdp_now} 水位{water_now}")
    print(f"变化: 盘口{'+' if hdp_change>=0 else ''}{hdp_change:.2f} "
          f"水位{'+' if water_change>=0 else ''}{water_change:.3f}")
    print("-" * 50)

    abs_hdp = abs_now

    if hdp_change > 0.05 and water_change < -0.02:
        if abs_hdp >= 1.0:
            verdict = "升盘+降水 但深盘 → ⚠️ 诱热(深盘难穿盘), 方向存疑"
        else:
            verdict = "升盘+降水 → ✅ 真实方向(资金看好上盘), 可信"
    elif hdp_change > 0.05 and water_change > 0.02:
        verdict = "升盘+升水 → ❌ 诱上陷阱(强造热, 极易赢球输盘)"
    elif hdp_change > 0.05:
        verdict = "升盘+水位不变 → ⚠️ 浅盘升盘倾向主队, 深盘需谨慎"
    elif abs(hdp_change) <= 0.05 and water_change < -0.05:
        verdict = "盘口不变+急速降水 → ❌ 大热必死陷阱(最常见诱盘)"
    elif abs(hdp_change) <= 0.05 and -0.05 <= water_change < -0.02:
        verdict = "盘口不变+小幅降水 → ✅ 资金自然涌入, 上盘不败概率高"
    elif abs(hdp_change) <= 0.05 and water_change > 0.05:
        verdict = "盘口不变+升水 → ⚠️ 资金流出, 上盘谨慎"
    elif hdp_change < -0.05 and water_change > 0.05:
        verdict = "降盘+升水 → ✅ 阻上洗筹(吓走上盘, 上盘大概率稳赢)"
    elif hdp_change < -0.05 and water_change < -0.02:
        verdict = "降盘+降水 → ❌ 真实看衰上盘, 下盘更容易打出"
    elif hdp_change < -0.05:
        verdict = "降盘 → ⚠️ 规避穿盘赔付, 上盘1球小胜居多"
    else:
        verdict = "盘口水位基本不变 → 🟡 无明显信号, 维持赛前判断"

    # 时间衰减权重 + 风险等级量化 (v2)
    if hours_to_kickoff is not None:
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "odds"))
            from line_movement import time_weight, risk_level, weighted_change
            tw = time_weight(hours_to_kickoff)
            wh = weighted_change(abs(hdp_change), hours_to_kickoff)
            ww = weighted_change(abs(water_change), hours_to_kickoff)
            wmax = max(wh, ww)
            rk = risk_level(wmax)
            verdict += (f"\n  [时间权重] 距开赛{hours_to_kickoff}h → 权重{tw:.2f}"
                        f"\n  [加权异动] 盘口{wh:.3f} / 水位{ww:.3f}"
                        f"\n  [风险等级] {rk['level']}级({rk['label']}) → {rk['advice']}")
        except Exception as e:
            verdict += f"\n  [时间权重] 计算失败: {e}"

    return verdict

def main():
    print("=" * 50)
    print("临场盘口对比工具 - 方向/陷阱判断")
    print("=" * 50)
    print()

    # 初盘
    hdp_ini_str = input("初盘让球 (如 -0.5/1): ").strip()
    water_ini_str = input("初盘上盘水位 (如 2.03): ").strip()
    # 临场
    hdp_now_str = input("临场让球 (如 -0.5/1): ").strip()
    water_now_str = input("临场上盘水位 (如 1.95): ").strip()

    try:
        hdp_ini = hdp_to_val(hdp_ini_str)
        water_ini = float(water_ini_str)
        hdp_now = hdp_to_val(hdp_now_str)
        water_now = float(water_now_str)
    except Exception as e:
        print(f"输入错误: {e}")
        return

    result = judge(hdp_ini, water_ini, hdp_now, water_now)
    print()
    print("=" * 50)
    print(f"  判断: {result}")
    print("=" * 50)


if __name__ == '__main__':
    main()
