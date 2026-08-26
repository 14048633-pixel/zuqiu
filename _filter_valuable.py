# -*- coding: utf-8 -*-
"""按已校准联赛(league_calib.json)过滤 scan24h/48h -> 有价值比赛清单
用法: python _filter_valuable.py [--hours 24] [--title 标题]
输出: analysis_records/scan{hours}h_valuable_{ts}.json (同格式 + excluded 统计)
"""
import sys, io, json, os, glob, collections, argparse
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"

ap = argparse.ArgumentParser()
ap.add_argument("--hours", type=int, default=24)
args = ap.parse_args()
hours = args.hours

# 已校准联赛白名单
cal = json.load(io.open(ROOT + r"\strategy_data\league_calib.json", encoding="utf-8-sig"))
wl = set((cal.get("leagues") or {}).keys())

# 最新 scan 文件
fs = sorted(glob.glob(ROOT + r"\analysis_records\scan%dh_*.json" % hours), key=os.path.getmtime)
src = None
for f in reversed(fs):
    try:
        d = json.load(io.open(f, encoding="utf-8"))
        if d.get("matches"):
            src = (f, d)
            break
    except Exception:
        continue
if src is None:
    print("无 scan%dh 文件" % hours)
    sys.exit(1)
f, d = src
ms = d.get("matches") or []
valuable = [m for m in ms if m.get("league") in wl]
excluded = collections.Counter(m.get("league") for m in ms if m.get("league") not in wl)

out = dict(d)
out["title"] = "%s | 有价值过滤(%d/%d 场)" % (d.get("title", ""), len(valuable), len(ms))
out["n_matches"] = len(valuable)
out["source_file"] = os.path.basename(f)
out["filter"] = {"rule": "league_calib.json 已校准联赛白名单", "whitelist": sorted(wl & {m.get("league") for m in ms}),
                 "excluded": dict(excluded.most_common())}
out["matches"] = valuable
fn = "scan%dh_valuable_%s.json" % (hours, datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M"))
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("来源: %s | 全部 %d -> 有价值 %d 场" % (os.path.basename(f), len(ms), len(valuable)))
print("白名单命中联赛: %s" % ", ".join(sorted(wl & {m.get("league") for m in ms})))
print("排除: %s" % ", ".join("%s×%d" % (k, v) for k, v in excluded.most_common()))
print("saved -> analysis_records/%s" % fn)
