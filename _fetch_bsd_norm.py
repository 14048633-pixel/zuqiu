# -*- coding: utf-8 -*-
"""92队BSD历史赛果 -> 对手强度归一攻防stats
公式: norm_gf = Σ(进球 × 对手强度coef × 时间权重) / Σ(coef × 时间权重)
      norm_ga = Σ(失球 × 对手强度coef × 时间权重) / Σ(coef × 时间权重)
意义: 刷弱队的进球被折扣, 打强队的进球被放大; 防守同理
排除: 友谊赛(79)/女足(36,72)/U19(71)
"""
import sys, io, os, json, urllib.request, time
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"D:\足球分析"
tok = ""
for line in io.open(ROOT + r"\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        tok = line.split("=", 1)[1].strip().strip('"').strip("'")

def get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request("https://sports.bzzoiro.com/api/v2" + path,
                                         headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
            return json.load(urllib.request.urlopen(req, timeout=40))
        except Exception as e:
            if i == tries - 1:
                return {"__err__": "%s" % str(e)[:80]}
            time.sleep(2)

# ---- 联赛强度系数 (league_id -> coef, 1.0=顶级) ----
LEAGUE_COEF = {
    1: 1.00, 3: 1.00, 5: 1.00, 4: 1.00, 6: 1.00,   # 英超/西甲/德甲/意甲/法甲
    7: 1.00, 8: 1.00, 83: 1.00, 90: 1.00,           # 欧冠/欧联/欧协联/超级杯
    10: 0.92, 2: 0.92, 14: 0.92, 11: 0.92, 13: 0.92, 15: 0.92, 24: 0.92, 9: 0.92,  # 荷甲/葡超/比甲/土超/苏超/瑞士/希腊/巴甲
    12: 0.85, 38: 0.85, 89: 0.85, 25: 0.85, 17: 0.85, 19: 0.85, 20: 0.85, 18: 0.85,  # 英冠/西乙/法乙/波甲/沙超/墨超/美职
    85: 0.85, 34: 0.85, 84: 0.85, 54: 0.85, 26: 0.85, 32: 0.85, 33: 0.85, 49: 0.85,  # 阿甲/巴乙/丹超/挪超/瑞超/解放者杯/南美杯/J1
    52: 0.80, 50: 0.80, 80: 0.75, 86: 0.80, 87: 0.75, 55: 0.70, 23: 0.72, 22: 0.70,  # 中超/K1/哥甲/英甲/英乙/芬超/罗甲/保甲
    88: 0.70, 82: 0.60, 47: 0.60, 53: 0.60, 28: 0.55, 70: 0.50,                     # 葡乙/葡丙/突尼斯/摩洛哥/尼日利亚/澳NPL
    42: 0.95, 41: 0.95, 39: 0.95, 43: 0.95, 44: 0.95, 40: 0.95,                      # 意杯/西杯/足总杯/德杯/法杯/联赛杯
    35: 0.90, 81: 0.75, 56: 0.70, 46: 0.80, 51: 0.80,                                # 巴西杯/哥伦杯/芬兰杯/波兰杯/天皇杯
    27: 0.85, 58: 0.85, 60: 0.85, 61: 0.85, 62: 0.85, 63: 0.85, 64: 0.85, 65: 0.85, 66: 0.85, 67: 0.85, 68: 0.85, 69: 0.85,  # 国家队/预选赛
    29: 0.80, 30: 0.80,                                                              # 非洲冠军/非洲杯
}
EXCLUDE = {79, 36, 72, 71}  # 友谊赛/女足西甲/女足NWSL/U19

def w_of(idx):
    if idx < 5: return 1.0
    if idx < 10: return 0.7
    if idx < 20: return 0.4
    return 0.2

scan = json.load(io.open(ROOT + r"\analysis_records\scan48h_20260818_2300.json", encoding="utf-8"))
KEY_LG = {"欧冠", "欧联", "欧协联", "中超", "西甲"}
targets = [m for m in scan["matches"] if m["league"] in KEY_LG]
team_ids = {}
for t in targets:
    if t.get("home_id"): team_ids[t["home_id"]] = (t["home"], t["league"])
    if t.get("away_id"): team_ids[t["away_id"]] = (t["away"], t["league"])
print("目标队伍数:", len(team_ids))

stats = {}
excl_cnt = 0
errs = []
for i, (tid, (tname, tlg)) in enumerate(sorted(team_ids.items(), key=lambda x: x[1][0])):
    j = get("/events/?team_id=%d&status=finished&limit=80" % tid)
    if "__err__" in j:
        errs.append((tname, j["__err__"])); continue
    res = j.get("results") or []
    scored = []
    for e in res:
        if e.get("league_id") in EXCLUDE:
            excl_cnt += 1; continue
        hs, as_ = e.get("home_score"), e.get("away_score")
        if hs is None or as_ is None:
            continue
        scored.append((e.get("event_date") or "", e.get("home_team"), e.get("home_team_id"),
                       hs, as_, e.get("away_team"), e.get("away_team_id"), e.get("league_id")))
    scored.sort(key=lambda x: x[0], reverse=True)
    raw = {"home_gf": [0.0, 0.0], "home_ga": [0.0, 0.0], "away_gf": [0.0, 0.0], "away_ga": [0.0, 0.0]}
    norm = {"home_gf": [0.0, 0.0], "home_ga": [0.0, 0.0], "away_gf": [0.0, 0.0], "away_ga": [0.0, 0.0]}
    n = 0
    for idx, (dt, h, hid, hs, as_, a, aid, lid) in enumerate(scored[:40]):
        w = w_of(idx)
        coef = LEAGUE_COEF.get(lid, 0.50)
        is_home = str(hid) == str(tid)
        if is_home:
            raw["home_gf"][0] += float(hs) * w; raw["home_gf"][1] += w
            raw["home_ga"][0] += float(as_) * w; raw["home_ga"][1] += w
            norm["home_gf"][0] += float(hs) * coef * w; norm["home_gf"][1] += coef * w
            norm["home_ga"][0] += float(as_) * coef * w; norm["home_ga"][1] += coef * w
        else:
            raw["away_gf"][0] += float(as_) * w; raw["away_gf"][1] += w
            raw["away_ga"][0] += float(hs) * w; raw["away_ga"][1] += w
            norm["away_gf"][0] += float(as_) * coef * w; norm["away_gf"][1] += coef * w
            norm["away_ga"][0] += float(hs) * coef * w; norm["away_ga"][1] += coef * w
        n += 1
    def avg(v):
        return round(v[0] / v[1], 3) if v[1] > 0 else 0.0
    stats[tname] = {
        "raw_home_gf": avg(raw["home_gf"]), "raw_home_ga": avg(raw["home_ga"]),
        "raw_away_gf": avg(raw["away_gf"]), "raw_away_ga": avg(raw["away_ga"]),
        "norm_home_gf": avg(norm["home_gf"]), "norm_home_ga": avg(norm["home_ga"]),
        "norm_away_gf": avg(norm["away_gf"]), "norm_away_ga": avg(norm["away_ga"]),
        "n_home": round(raw["home_gf"][1], 1), "n_away": round(raw["away_gf"][1], 1),
        "n_scored": n, "src_tag": "bsd_norm", "league": tlg, "team_id": tid,
    }
    if (i + 1) % 15 == 0:
        print("  ... %d/%d" % (i + 1, len(team_ids)), flush=True)
    time.sleep(0.3)

out = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "n_teams": len(stats), "excluded_events": excl_cnt, "coef_note": "league-tier coef, exclude friendlies/women/u19", "stats": stats}
fp = ROOT + r"\data\raw\football_data\bsd_team_stats_norm_20260818.json"
io.open(fp, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved", fp, "| teams:", len(stats), "| errs:", len(errs), "| excl:", excl_cnt)
for t, e in errs[:8]:
    print("  ERR", t, e)

print("\n== 归一前后对比 (raw -> norm) ==")
for name in ("Levski Sofia", "AEK Athens", "AS Monaco", "Górnik Zabrze", "Red Bull Salzburg", "Mjällby AIF", "Benfica", "Celtic", "Atalanta", "Brighton & Hove Albion"):
    r = stats.get(name)
    if r:
        print("%-24s 主: %s/%s -> %s/%s | 客: %s/%s -> %s/%s" % (
            name, r["raw_home_gf"], r["raw_home_ga"], r["norm_home_gf"], r["norm_home_ga"],
            r["raw_away_gf"], r["raw_away_ga"], r["norm_away_gf"], r["norm_away_ga"]))
