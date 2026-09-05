# -*- coding: utf-8 -*-
"""profile poisson_fit 各阶段耗时, 定位 batch 慢的根因."""
import io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd
import model
from data_loader import load_data

_t = {}
def _w(name, fn):
    def _wr(*a, **k):
        t0 = time.perf_counter()
        r = fn(*a, **k)
        dt = time.perf_counter() - t0
        _t.setdefault(name, [0, 0.0])
        _t[name][0] += 1
        _t[name][1] += dt
        return r
    return _wr

t0 = time.perf_counter()
df = load_data()
t_load = time.perf_counter() - t0
print("load_data: %.1fs rows=%d" % (t_load, len(df)), flush=True)

model.poisson_predict = _w("poisson_predict", model.poisson_predict)
model.compute_ou_calibration = _w("ou_calib", model.compute_ou_calibration)
model.compute_1x2_calibration = _w("1x2_calib", model.compute_1x2_calibration)
model._apply_opp_strength = _w("strength_v2", model._apply_opp_strength)

match_date = pd.Timestamp.now().normalize()
train = df[df["date"] < match_date]
print("train rows:", len(train), flush=True)

t0 = time.perf_counter()
fit = model.poisson_fit(train)
t_fit = time.perf_counter() - t0
print("poisson_fit 总耗时: %.1fs" % t_fit, flush=True)
print("=== 各阶段耗时 ===", flush=True)
for name in ("ou_calib", "1x2_calib", "strength_v2", "poisson_predict"):
    if name in _t:
        n, s = _t[name]
        print("  %-16s 调用%d次  累计%6.1fs (占fit %.0f%%)" % (name, n, s, s / t_fit * 100), flush=True)
wrapped = sum(_t.get(n, [0, 0.0])[1] for n in _t)
print("  剩余(fit内其它: 主循环/rho/league_era): %6.1fs (占fit %.0f%%)"
      % (t_fit - wrapped, (t_fit - wrapped) / t_fit * 100), flush=True)

# 逐场 match_model_report 计时
from match_report import match_model_report
import random
rows = train.sample(5, random_state=42)
t0 = time.perf_counter()
for _, r in rows.iterrows():
    _ = match_model_report(fit, train, {"league": r["league"], "home": r["home"],
                                        "away": r["away"], "date": r["date"]})
t_per = (time.perf_counter() - t0) / 5
print("逐场 match_model_report: 平均 %.2fs/场" % t_per, flush=True)
