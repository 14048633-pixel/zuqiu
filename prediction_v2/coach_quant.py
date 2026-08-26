# -*- coding: utf-8 -*-
"""教练量化修正 (BSD 教练历史统计 -> 同联赛 Min-Max 归一 0.85~1.15 -> 样本衰减 -> λ 修正)
================================================================
数据源: BSD /api/v2/managers/?league_id=X (免费档实测可用)
  - Manager 有 avg_goals_scored / avg_goals_conceded / matches_total / over_25_pct
    / win_pct / tactical_profile / preferred_formation / stats_updated_at
  - BSD OpenAPI 的 Manager schema 虽声明 avg_xg_for/avg_xg_against, 但实测所有教练(含瓜迪奥拉)
    都不返回 xG 字段 -> 用实际进球 gf/ga 替代(诚实标注, 数据能拉就拉/拉不到注明)
归一逻辑(纯数值统计, 无 AI 主观判断):
  atk_mod = 0.85 + (gf-min_gf)/(max_gf-min_gf)*0.30     高进攻教练 -> 1.15 拉高 λ
  def_mod = 0.85 + (ga-min_ga)/(max_ga-min_ga)*0.30     强防守教练(低ga) -> 0.85 压低对手 λ
  样本衰减: sample_w = min(matches_total/80, 1.0) -> 新帅几乎不修正
  profile 仅二次微调: attack*1.02 / defend*0.98 (不做主判)
用法:
  python prediction_v2/coach_quant.py --fetch            # 拉全联赛教练缓存(可 --leagues 荷甲,西甲)
  python prediction_v2/coach_quant.py --status           # 查看缓存覆盖
缓存: analysis_records/coach_cache.json
"""
import argparse, io, json, os, sys, time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "analysis_records", "coach_cache.json")

# 修正区间(可配置, 对应 league_calib global_settings 语义)
COACH_ATK_MIN, COACH_ATK_MAX = 0.85, 1.15
COACH_DEF_MIN, COACH_DEF_MAX = 0.85, 1.15
COACH_SAMPLE_CAP = 80          # 执教场次满额样本(>=80 修正全额生效)
COACH_MIN_POOL = 3             # 联赛教练池少于 3 人 -> 归一不可信, 返回中性
COACH_MIN_MATCHES = 5          # 教练个人样本 < 5 场不进联赛池(防偶然战绩污染极值)
COACH_CLAMP = (0.80, 1.20)     # 最终系数安全包络
PROFILE_TWEAK_ATK = {"attacking": 1.02, "defensive": 0.98}  # BSD profile: attacking/defensive/balanced
PROFILE_TWEAK_ATK_FALLBACK = {"attack": 1.02, "defend": 0.98}  # 兼容 attack/defend 变体


def _apply_global_settings():
    """读取 strategy_data/league_calib.json 的 global_settings 覆盖全局常量(全部可配置不改代码)."""
    try:
        _p = os.path.join(ROOT, "strategy_data", "league_calib.json")
        if not os.path.exists(_p):
            return
        _gs = json.load(io.open(_p, encoding="utf-8")).get("global_settings") or {}
        global COACH_ATK_MIN, COACH_ATK_MAX, COACH_DEF_MIN, COACH_DEF_MAX
        global COACH_SAMPLE_CAP, COACH_MIN_POOL, COACH_MIN_MATCHES, PROFILE_TWEAK_ATK
        for _k, _v in (("coach_atk_range_min", "COACH_ATK_MIN"), ("coach_atk_range_max", "COACH_ATK_MAX"),
                       ("coach_def_range_min", "COACH_DEF_MIN"), ("coach_def_range_max", "COACH_DEF_MAX"),
                       ("coach_sample_cap", "COACH_SAMPLE_CAP"), ("coach_min_pool", "COACH_MIN_POOL"),
                       ("coach_min_matches", "COACH_MIN_MATCHES")):
            if _k in _gs:
                globals()[_v] = float(_gs[_k])
        if "coach_profile_tweak_attack" in _gs:
            PROFILE_TWEAK_ATK["attacking"] = float(_gs["coach_profile_tweak_attack"])
            PROFILE_TWEAK_ATK_FALLBACK["attack"] = float(_gs["coach_profile_tweak_attack"])
        if "coach_profile_tweak_defend" in _gs:
            PROFILE_TWEAK_ATK["defensive"] = float(_gs["coach_profile_tweak_defend"])
            PROFILE_TWEAK_ATK_FALLBACK["defend"] = float(_gs["coach_profile_tweak_defend"])
    except Exception:
        pass


_apply_global_settings()

# 我们联赛名 -> BSD league id (BSD 无该联赛则 None, 诚实标注未提取)
# 2026-08-16 从 /api/v2/leagues/ 实测核对
BSD_LEAGUE_IDS = {
    "荷甲": 10, "德甲": 5, "比甲": 14, "瑞超": 26, "丹超": 84,
    "英冠": 12, "英甲": 86, "英乙": 87, "英超": 1, "挪超": 54,
    "巴甲": 9, "巴乙": 34, "葡超": 2, "葡乙": 88,
    "西甲": 3, "西乙": 38, "土超": 11,
    "阿甲": 85, "墨超": 19, "美职": 18,
    "中超": 52, "J1": 49,
    "意甲": 4, "法甲": 6, "法乙": 89, "苏超": 13,
    "希腊超": 24, "波兰甲": 25, "罗甲": 23, "瑞士超": 15,
    "韩K": 50, "韩K联": 50, "沙特": 17, "哥甲": 80, "保甲": 22, "芬超": 55,
    "欧冠": 7, "欧联": 8, "欧协": 83, "欧协联": 83,
    "天皇杯": 51, "英足总杯": 39, "英联杯": 40, "德国杯": 43, "意杯": 42,
    "国王杯": 41, "法杯": 44, "巴西杯": 35, "哥杯": 81, "芬杯": 56,
    "解放者杯": 32, "南球杯": 33,
    # BSD 无覆盖联赛(拉取时标注, 扫描显示 教练数据未提取)
    "德乙": None, "智利甲": None, "荷乙": None, "奥甲": None,
    "中乙": None, "K2": None, "日乙": None, "墨西乙": None,
}

def _get(path, token, tries=2, timeout=25):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
               "Authorization": "Token " + token}
    for i in range(1, tries + 1):
        try:
            r = requests.get("https://sports.bzzoiro.com" + path, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            print("  HTTP %s: %s" % (r.status_code, (r.text or "")[:160]))
            if r.status_code < 500:
                return None
        except Exception as e:
            print("  第%d/%d次失败: %s" % (i, tries, type(e).__name__))
        if i < tries:
            time.sleep(3)
    return None


def _load_token():
    env = os.path.join(ROOT, ".env")
    if not os.path.exists(env):
        return ""
    for line in io.open(env, encoding="utf-8"):
        s = line.strip()
        if s.startswith("BZZOIRO_API_KEY="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _num(v):
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def fetch_cache(leagues=None, out_path=None):
    """按联赛拉 BSD 教练统计 -> coach_cache.json. leagues 为我们的联赛名列表; None=BSD_LEAGUE_IDS 全部."""
    token = _load_token()
    if not token:
        print("  ⚠️ 无 BZZOIRO_API_KEY(.env), 跳过拉取")
        return None
    out_path = out_path or CACHE_PATH
    if leagues is None:
        leagues = sorted(k for k, v in BSD_LEAGUE_IDS.items() if v)
    elif isinstance(leagues, str):
        leagues = [x.strip() for x in leagues.split(",") if x.strip()]
    cache = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
             "leagues": {}, "coaches": {}, "by_name": {}, "skipped": {}}
    for lg in leagues:
        lid = BSD_LEAGUE_IDS.get(lg)
        if not lid:
            cache["skipped"][lg] = "BSD无该联赛"
            print("  %-4s -> BSD无该联赛, 跳过" % lg)
            continue
        print("  拉取 %-4s (BSD league_id=%s)..." % (lg, lid), flush=True)
        recs, off = [], 0
        while True:
            j = _get("/api/v2/managers/?league_id=%d&limit=200&offset=%d" % (lid, off), token)
            if j is None:
                break
            batch = j.get("results") or []
            recs += batch
            nxt = j.get("next")
            if not nxt or not batch:
                break
            off += len(batch)
        # 联赛池: 有统计且样本>=5 的教练
        pool = [r for r in recs if _num(r.get("avg_goals_scored")) is not None
                and _num(r.get("avg_goals_conceded")) is not None
                and (_num(r.get("matches_total")) or 0) >= COACH_MIN_MATCHES]
        gfs = sorted(_num(r["avg_goals_scored"]) for r in pool)
        gas = sorted(_num(r["avg_goals_conceded"]) for r in pool)
        # P5/P95 截尾边界: 池>=10 用截尾(防少数场次离群教练污染极值, 如瓜迪奥拉gf2.0被归为低于英超平均);
        # 池<10 回落原始 min/max(小池分位不稳定)
        def _bounds(vals):
            if not vals:
                return None, None
            if len(vals) >= 10:
                lo = vals[max(0, int(len(vals) * 0.05))]
                hi = vals[min(len(vals) - 1, int(len(vals) * 0.95))]
                if hi > lo:
                    return lo, hi
            return vals[0], vals[-1]
        bgf = _bounds(gfs)
        bga = _bounds(gas)
        cache["leagues"][lg] = {
            "bsd_id": lid, "n_pool": len(recs), "n": len(pool),
            "min_gf": bgf[0], "max_gf": bgf[1],
            "min_ga": bga[0], "max_ga": bga[1],
            "raw_min_gf": gfs[0] if gfs else None, "raw_max_gf": gfs[-1] if gfs else None,
            "raw_min_ga": gas[0] if gas else None, "raw_max_ga": gas[-1] if gas else None,
        }
        for r in pool:
            cid = str(r.get("id"))
            rec = cache["coaches"].setdefault(cid, {
                "id": r.get("id"), "name": r.get("name") or "", "short_name": r.get("short_name") or "",
                "matches_total": _num(r.get("matches_total")) or 0,
                "avg_goals_scored": _num(r.get("avg_goals_scored")),
                "avg_goals_conceded": _num(r.get("avg_goals_conceded")),
                "over_25_pct": _num(r.get("over_25_pct")), "win_pct": _num(r.get("win_pct")),
                "clean_sheet_pct": _num(r.get("clean_sheet_pct")), "btts_pct": _num(r.get("btts_pct")),
                "tactical_profile": r.get("tactical_profile") or "",
                "preferred_formation": r.get("preferred_formation") or "",
                "leagues": []})
            if lg not in rec["leagues"]:
                rec["leagues"].append(lg)
            nm = (r.get("name") or "").strip().lower()
            if nm and nm not in cache["by_name"]:
                cache["by_name"][nm] = cid
        print("    教练池 %d 人 (gf %.2f~%.2f, ga %.2f~%.2f)" % (
            len(pool), cache["leagues"][lg]["min_gf"] or 0, cache["leagues"][lg]["max_gf"] or 0,
            cache["leagues"][lg]["min_ga"] or 0, cache["leagues"][lg]["max_ga"] or 0))
        time.sleep(0.2)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    print("教练缓存已写入: %s (联赛 %d, 教练 %d, 跳过 %s)" % (
        out_path, len(cache["leagues"]), len(cache["coaches"]),
        ",".join(cache["skipped"]) or "-"))
    return cache


def load_cache(path=None):
    path = path or CACHE_PATH
    if not os.path.exists(path):
        return None
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return None


def _norm01(v, lo, hi):
    if hi is None or lo is None or hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def coach_mods(cache, coach_id, league):
    """教练 id -> (atk_mod, def_mod, sample_w, meta) 或 None(无缓存/联赛池退化/无该教练)."""
    if not cache:
        return None
    lg = cache.get("leagues") or {}
    bounds = lg.get(league)
    if not bounds or (bounds.get("n") or 0) < COACH_MIN_POOL:
        return None
    if bounds.get("min_gf") is None or bounds.get("max_gf") is None:
        return None
    rec = (cache.get("coaches") or {}).get(str(coach_id))
    if not rec:
        return None
    gf = _num(rec.get("avg_goals_scored"))
    ga = _num(rec.get("avg_goals_conceded"))
    n = rec.get("matches_total") or 0
    if gf is None or ga is None or n <= 0:
        return None
    atk_raw = COACH_ATK_MIN + _norm01(gf, bounds["min_gf"], bounds["max_gf"]) * (COACH_ATK_MAX - COACH_ATK_MIN)
    def_raw = COACH_DEF_MIN + _norm01(ga, bounds["min_ga"], bounds["max_ga"]) * (COACH_DEF_MAX - COACH_DEF_MIN)
    sw = min(n / float(COACH_SAMPLE_CAP), 1.0)
    atk = 1.0 + (atk_raw - 1.0) * sw
    defe = 1.0 + (def_raw - 1.0) * sw
    prof = (rec.get("tactical_profile") or "").strip().lower()
    _tw = PROFILE_TWEAK_ATK.get(prof)
    if _tw is None:
        for _k, _v in PROFILE_TWEAK_ATK_FALLBACK.items():
            if prof.startswith(_k):
                _tw = _v
                break
    atk *= (_tw or 1.0)
    atk = max(COACH_CLAMP[0], min(COACH_CLAMP[1], atk))
    defe = max(COACH_CLAMP[0], min(COACH_CLAMP[1], defe))
    return {"atk": round(atk, 4), "def": round(defe, 4), "sample": int(n),
            "gf": round(gf, 3), "ga": round(ga, 3),
            "name": rec.get("name") or "", "profile": prof}


def match_mods(cache, info, league):
    """matches_info 的 bsd_coaches -> 主客教练修正 dict(供 λ 折叠).
    返回 {h_atk,h_def,a_atk,a_def, h_name,h_sample, a_name,a_sample} 或 {}."""
    coaches = (info or {}).get("bsd_coaches") or {}
    out = {}
    for side, key in (("home", "h"), ("away", "a")):
        rec = coaches.get(side) or {}
        cid = rec.get("id")
        mod = coach_mods(cache, cid, league) if cid is not None else None
        if mod:
            out[key + "_atk"] = mod["atk"]
            out[key + "_def"] = mod["def"]
            out[key + "_sample"] = mod["sample"]
            out[key + "_name"] = mod["name"]
            out[key + "_gf"] = mod["gf"]
            out[key + "_ga"] = mod["ga"]
    return out


def mod_text(mods):
    """教练修正摘要(主客各一段), 空则空串."""
    if not mods:
        return ""
    parts = []
    for side, key in (("主", "h"), ("客", "a")):
        if key + "_atk" not in mods:
            continue
        nm = mods.get(key + "_name") or "?"
        parts.append("%s%s(攻%+.1f%% 防%+.1f%% n%d)" % (
            side, nm[:14],
            (mods[key + "_atk"] - 1) * 100, (mods.get(key + "_def", 1.0) - 1.0) * 100,
            mods.get(key + "_sample", 0)))
    return " 教练量化:" + " ".join(parts) if parts else ""


def cmd_status(path=None):
    cache = load_cache(path)
    if not cache:
        print("教练缓存不存在: %s" % (path or CACHE_PATH))
        return
    print("教练缓存 %s" % (cache.get("updated_at") or "?"))
    print("  联赛覆盖: %d | 教练: %d" % (len(cache.get("leagues") or {}), len(cache.get("coaches") or {})))
    for lg, b in (cache.get("leagues") or {}).items():
        print("  %-4s n=%d/%d gf %.2f~%.2f ga %.2f~%.2f" % (
            lg, b.get("n", 0), b.get("n_pool", 0), b.get("min_gf") or 0, b.get("max_gf") or 0,
            b.get("min_ga") or 0, b.get("max_ga") or 0))
    for lg in (cache.get("skipped") or {}):
        print("  跳过 %s: %s" % (lg, cache["skipped"][lg]))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="拉取 BSD 教练统计缓存")
    ap.add_argument("--leagues", default="", help="逗号分隔联赛名(默认全部有映射的联赛)")
    ap.add_argument("--status", action="store_true", help="查看缓存覆盖")
    ap.add_argument("--out", default="", help="输出路径(默认 analysis_records/coach_cache.json)")
    args = ap.parse_args()
    if args.fetch:
        fetch_cache(args.leagues or None, args.out or None)
    elif args.status:
        cmd_status(args.out or None)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
