"""多源赔率快照抓取 CLI (多key容灾 + 配额硬阻断 v2)
========================================================
用法:
  python fetch_live_odds.py                    # 抓全部9联赛(主链key, 失败自动切换备用key)
  python fetch_live_odds.py --league 中超      # 亚洲联赛 -> 优先 ODDS_API_KEY_AS
  python fetch_live_odds.py --test             # 验证 key + 配额(只请求1个联赛)
  python fetch_live_odds.py --sports           # 列出/缓存支持的运动(校验 key)

多key规范 (.env):
  ODDS_API_KEY_1=主源(the-odds-api)
  ODDS_API_KEY_2=二号备用(Odds-API.io, https://api.odds-api.io/v3, 走 src/oddsapi_io.py 适配器)
  ODDS_API_KEY_3=三号备用(OddsPapi, 需适配器)
  ODDS_API_KEY_AS=亚洲赛事专用(iSports/纳米, J1/K2/中超/中乙优先)
  ODDS_BASE_URL_2=https://备用网关          # base url 不同时填写
  ODDS_MIN_QUOTA=50                        # 剩余配额低于此值硬阻断, 不产残缺盘口文件

配额硬阻断: 开抓前预检(1请求), 剩余<阈值 -> 直接终止(exit 3), 不写快照;
           中途配额耗尽 -> 丢弃本轮已抓数据, 不产残缺盘口文件, 写告警日志。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.live_odds import (LEAGUE_SPORT_KEYS, DEFAULT_MARKETS, DEFAULT_REGIONS,
                           fetch_sports_list, fetch_league_odds,
                           flatten_events, append_snapshots)
from src import oddsapi_io

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
ALERT_LOG = os.path.join(HERE, "output", "odds_snapshots", "quota_alerts.log")


def _alert(msg):
    os.makedirs(os.path.dirname(ALERT_LOG), exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(ALERT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"⚠️ 告警已写入 {ALERT_LOG}")


def _save_sports_cache(sports, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sports, f, ensure_ascii=False, indent=1)


def _is_oddsapi(sel):
    """判断当前选择是否 Odds-API.io 备用源 (v3, 需适配器, 不能只换 base_url)。"""
    return oddsapi_io.is_oddsapi_source(sel)


def _fetch_oddsapi_rows(sel, lg, ts):
    """Odds-API.io: events(联赛级) + odds/multi(每10场1请求) -> 统一快照行。"""
    slug = oddsapi_io.LEAGUE_SLUGS.get(lg)
    if not slug:
        raise ValueError(f"Odds-API.io 未配置联赛映射: {lg}")
    events, quota = oddsapi_io.fetch_events(sel["key"], slug, base_url=sel["base_url"])
    ids = [e.get("id") for e in events or [] if e.get("id") is not None]
    bookmakers = os.environ.get("ODDS_BOOKMAKERS", "").strip() or oddsapi_io.DEFAULT_BOOKMAKERS
    odds_list = []
    for chunk in oddsapi_io.chunk_ids(ids):
        part, _ = oddsapi_io.fetch_odds_multi(sel["key"], chunk, bookmakers=bookmakers,
                                              base_url=sel["base_url"])
        odds_list.extend(part or [])
    rows = oddsapi_io.flatten_rows(events, odds_list, lg, ts)
    return rows, quota



# ===== 交叉验证: Odds-API.io 补抓同联赛让球/大小球, 归并到主源 event_id =====
_CROSS_GENERIC = {"fc", "afc", "cf", "sc", "ac", "as", "us", "cd", "de", "sd", "ud", "ssc"}


def _cross_norm(s):
    """跨源队名归一化: 小写去标点 + 去通用后缀(FC/AFC/CF 等), 用于主客双向匹配。"""
    s = str(s or "")
    s = "".join(c for c in s if c.isalnum() or c.isspace())
    s = s.lower()
    words = [w for w in s.split() if w not in _CROSS_GENERIC]
    return " ".join(words)


def _cross_match_event(anchor_events, lg, ct, home, away):
    """在主源事件里找同一场 (队名词集双向子集 + 开球时间±30min) -> (event_id, home, away)。"""
    import datetime as _dt
    try:
        ct_dt = _dt.datetime.fromisoformat(str(ct).replace("Z", "+00:00"))
    except Exception:
        ct_dt = None
    nh, na = _cross_norm(home), _cross_norm(away)
    wh, wa = set(nh.split()), set(na.split())
    if not wh or not wa:
        return None
    for ev in anchor_events:
        if ev.get("league") != lg:
            continue
        if ct_dt is not None:
            try:
                ev_dt = _dt.datetime.fromisoformat(str(ev.get("commence_time", "")).replace("Z", "+00:00"))
            except Exception:
                ev_dt = None
            if ev_dt is not None and abs((ct_dt - ev_dt).total_seconds()) > 1800:
                continue
        eh, ea = _cross_norm(ev.get("home_team")), _cross_norm(ev.get("away_team"))
        weh, wea = set(eh.split()), set(ea.split())
        if not weh or not wea:
            continue
        h_ok = (nh == eh) or (wh <= weh) or (weh <= wh)
        a_ok = (na == ea) or (wa <= wea) or (wea <= wa)
        if h_ok and a_ok:
            return (ev.get("event_id"), ev.get("home_team"), ev.get("away_team"))
    return None


def _merge_cross_rows(anchor_rows, cross_rows):
    """把 Odds-API.io 行归并到主源事件: 重写 event_id + 队名为主源版本。

    未匹配到主源事件的行丢弃(避免孤盘污染同一场次), 返回 (merged_rows, matched, total)。
    """
    seen = set()
    anchor_events = []
    for r in anchor_rows or []:
        k = (r.get("event_id"), r.get("home_team"), r.get("away_team"))
        if k in seen:
            continue
        seen.add(k)
        anchor_events.append(r)
    merged = []
    matched = 0
    for r in cross_rows or []:
        m = _cross_match_event(anchor_events, r.get("league"), r.get("commence_time"),
                               r.get("home_team"), r.get("away_team"))
        if not m:
            continue
        eid, eh, ea = m
        r = dict(r)
        r["event_id"], r["home_team"], r["away_team"] = eid, eh, ea
        merged.append(r)
        matched += 1
    return merged, matched, len(cross_rows or [])


def _fetch_cross_oddsapi(router, lg, ts, anchor_rows):
    """交叉模式: Odds-API.io 补抓同一联赛(仅让球/大小球), 归并后返回行。

    只在主源成功后调用; 失败仅告警不阻断主链快照。
    """
    sel2 = None
    for k, s in router.keys:
        if s == "ODDS_API_KEY_2":
            sel2 = {"key": k, "source": s, "base_url": router.meta.get(s)}
            break
    if not sel2:
        return [], {}, "未配置 ODDS_API_KEY_2"
    slug = oddsapi_io.LEAGUE_SLUGS.get(lg)
    if not slug:
        return [], {}, "Odds-API.io 无该联赛映射"
    try:
        events, quota = oddsapi_io.fetch_events(sel2["key"], slug, base_url=sel2["base_url"])
        ids = [e.get("id") for e in events or [] if e.get("id") is not None]
        bookmakers = os.environ.get("ODDS_BOOKMAKERS", "").strip() or oddsapi_io.DEFAULT_BOOKMAKERS
        odds_list = []
        for chunk in oddsapi_io.chunk_ids(ids):
            part, _ = oddsapi_io.fetch_odds_multi(sel2["key"], chunk, bookmakers=bookmakers,
                                                  base_url=sel2["base_url"])
            odds_list.extend(part or [])
        cross_rows = oddsapi_io.flatten_rows(events, odds_list, lg, ts)
        merged, matched, total = _merge_cross_rows(anchor_rows, cross_rows)
        return merged, quota, f"Odds-API.io归并{matched}/{total}行"
    except Exception as e:
        return [], {}, f"Odds-API.io交叉抓取失败: {e}"



def _fetch_with_failover(router, lg, sport, markets, regions):
    """按联赛选 key+base, 失败自动切换(AS失败回主链, 主链失败轮询下一key)。
    两种源统一产出快照行: the-odds-api 直接展平; Odds-API.io 走适配器。"""
    sel = router.key_for_league(lg)
    tried = set()
    last_err = None
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    while sel and sel["source"] not in tried:
        tried.add(sel["source"])
        try:
            if _is_oddsapi(sel):
                rows, quota = _fetch_oddsapi_rows(sel, lg, ts)
            else:
                events, quota = fetch_league_odds(sel["key"], sport, markets=markets, regions=regions,
                                                  base_url=sel["base_url"])
                rows = flatten_events(events, lg, ts)
            router.mark_success(sel["key"])
            return rows, quota, sel, None
        except Exception as e:
            router.mark_failure(sel["key"])
            last_err = e
            print(f"⚠️ {lg} 用 {sel['source']} 失败: {e}")
            sel = router.rotate_sel(lg)
    return None, {}, None, last_err


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description="多源赔率抓取(多key容灾+配额硬阻断)")
    ap.add_argument("--league", help="单联赛(中文名, 如 英超/中超); 缺省=全部9联赛")
    ap.add_argument("--test", action="store_true", help="只请求1个联赛验证 key/配额")
    ap.add_argument("--sports", action="store_true", help="列出并缓存支持的运动(校验 key)")
    ap.add_argument("--cross", action="store_true",
                    help="交叉验证: 主源成功后用 Odds-API.io 补抓同联赛让球/大小球并归并同一场次")
    ap.add_argument("--markets", default=DEFAULT_MARKETS)
    ap.add_argument("--regions", default=DEFAULT_REGIONS)
    ap.add_argument("--out", default=os.path.join(HERE, "output", "odds_snapshots", "snapshots.csv"))
    ap.add_argument("--sports-cache", default=os.path.join(HERE, "output", "odds_snapshots", "sports.json"))
    ap.add_argument("--min-remaining", type=int, default=None,
                    help="剩余配额硬阻断阈值(默认读 .env ODDS_MIN_QUOTA=50)")
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "odds"))
    from api_router import OddsApiRouter
    router = OddsApiRouter(base_dir=HERE, project_root=PROJECT_ROOT)
    if not router.available():
        print("❌ 未找到赔率 API key。")
        print("   1) 设置环境变量 ODDS_API_KEY_1..N / ODDS_API_KEY / ODDS_API_KEY_AS")
        print("   2) 或创建 config.json: {\"odds_api_key\": \"你的key\"}")
        print("   3) 或把 key 写入项目根 .env")
        sys.exit(2)
    min_quota = args.min_remaining if args.min_remaining is not None else router.min_quota
    as_tag = "有" if router.asian else "无"
    print(f"✔ key 来源: 主链{len(router.keys)}组 亚洲专用[{as_tag}] 配额硬阻断阈值={min_quota}")

    if args.sports:
        sel = router.key_for_league(None)
        if _is_oddsapi(sel):
            leagues, quota = oddsapi_io.fetch_leagues(sel["key"], base_url=sel["base_url"])
            print(f"✔ Odds-API.io 足球联赛 {len(leagues)} 项:")
            for l in sorted(leagues or [], key=lambda x: x.get("slug", "")):
                print(f"   {l.get('slug'):<38} {l.get('name')}  events={l.get('eventsCount')}")
            print(f"配额: used={quota.get('used')} remaining={quota.get('remaining')}")
            return
        try:
            sports, quota = fetch_sports_list(sel["key"], base_url=sel["base_url"])
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            sys.exit(1)
        _save_sports_cache(sports, args.sports_cache)
        soccer = [s for s in sports if s.get("group") == "Soccer"]
        print(f"✔ sports 缓存已保存: {args.sports_cache} (Soccer {len(soccer)} 项)")
        for s in sorted(soccer, key=lambda x: x.get("key", "")):
            print(f"   {s.get('key'):<36} {s.get('title')}  active={s.get('active')}")
        print(f"配额: used={quota.get('used')} remaining={quota.get('remaining')}")
        return

    if args.test:
        lg = args.league or list(LEAGUE_SPORT_KEYS.keys())[0]
        sport = LEAGUE_SPORT_KEYS.get(lg)
        sel = router.key_for_league(lg)
        print(f"✔ 测试联赛: {lg} -> key来源 {sel['source']} ({sel['base_url']})")
        rows, quota, _, err = _fetch_with_failover(router, lg, sport, args.markets, args.regions)
        if rows is None:
            print(f"⚠️ {lg}({sport}) 抓取失败: {err}")
            sys.exit(1)
        print(f"✔ key 有效: {lg} 行={len(rows)}")
        print(f"配额: used={quota.get('used')} remaining={quota.get('remaining')}")
        return

    leagues = [args.league] if args.league else list(LEAGUE_SPORT_KEYS.keys())

    # ===== 配额预检: 当前 key 不足(含本轮消耗余量)自动轮换下一 key, 全部不足才终止 =====
    # the-odds-api 按 market x region 计费: 每联赛约 3 请求(3市场x1地区) + 预检1请求
    _est_cost = len(leagues) * 3 + 1 if len(leagues) <= 3 else len(leagues) + 2
    probe = router.key_for_league(None)
    probed = set()
    ok_sel = None
    ok_q = {}
    while probe and probe["source"] not in probed:
        probed.add(probe["source"])
        try:
            if _is_oddsapi(probe):
                _, q0 = oddsapi_io.fetch_sports_list(probe["key"], base_url=probe["base_url"])
            else:
                _, q0 = fetch_sports_list(probe["key"], base_url=probe["base_url"])
            rem0 = int(q0.get("remaining") or 0)
            if rem0 >= min_quota + _est_cost:
                router.mark_success(probe["key"])
                ok_sel, ok_q = probe, q0
                break
            # 静默跳过配额不足的 key, 不逐 key 告警
        except Exception as e:
            router.mark_failure(probe["key"])
            # 静默跳过失败 key
        probe = router.rotate_sel(None)
    if ok_sel is None:
        _alert("配额预检: 所有 key 均不足/失败, 终止本轮抓取(未写快照)")
        print("❌ 所有 key 配额不足或失败, 终止本轮(不产残缺盘口文件)。")
        sys.exit(3)
    _is_last = ok_sel["source"] == (router.keys[-1][1] if router.keys else ok_sel["source"])
    if _is_last:
        _alert(f"配额预检: 已用到最后一个备用key {ok_sel['source']}, 剩余={ok_q.get('remaining')}, 请准备充值/新增key")
        print(f"⚠️ 已用到最后一个备用key {ok_sel['source']}, 剩余配额 {ok_q.get('remaining')}, 请准备充值/新增key。")
    print(f"✔ 配额预检通过: key来源={ok_sel['source']} used={ok_q.get('used')} remaining={ok_q.get('remaining')} (阈值={min_quota})")

    print(f"本轮将消耗 {len(leagues)} 请求; 免费档 500/月≈16请求/天, 建议 1 轮/天(9请求), 赛日补抓重点联赛。")
    all_rows = []
    total_events = 0
    last_quota = {}
    for lg in leagues:
        sport = LEAGUE_SPORT_KEYS.get(lg)
        if not sport:
            print(f"⚠️ 未知联赛: {lg}")
            continue
        rows, quota, sel, err = _fetch_with_failover(router, lg, sport, args.markets, args.regions)
        if rows is None:
            print(f"⚠️ {lg}({sport}) 抓取失败且无可用备用key: {err}")
            last_quota = {}
            continue
        total_events += len(rows)
        print(f"✔ {lg:<4} {sport:<34} 行={len(rows):<3} key={sel['source']}")
        # ===== 配额硬阻断: 低于阈值 -> 终止本轮, 丢弃已抓数据, 不产残缺盘口文件 =====
        try:
            rem = int(quota.get("remaining"))
            if rem < min_quota:
                _alert(f"剩余配额={rem} < 硬阻断阈值={min_quota}: 已抓 {total_events} 场次数据全部丢弃(不产残缺快照)")
                print(f"❌ 剩余配额 {rem} < {min_quota}, 终止本轮; 已抓 {total_events} 场次不写入快照。")
                sys.exit(3)
        except (TypeError, ValueError):
            pass
        all_rows.extend(rows)
        # ===== 交叉验证: 主源成功后用 Odds-API.io 补抓让球/大小球, 归并同一场次 =====
        if args.cross and not _is_oddsapi(sel):
            _cross_ts = rows[0]["snapshot_ts"] if rows else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            cross_rows, cq, cmsg = _fetch_cross_oddsapi(router, lg, _cross_ts, rows)
            if cross_rows:
                all_rows.extend(cross_rows)
                print(f"  └ 交叉: {cmsg} 追加{len(cross_rows)}行(Odds-API.io让球/大小球)")
            else:
                print(f"  └ 交叉跳过: {cmsg}")
            if cq:
                last_quota = cq
        last_quota = quota

    if all_rows:
        append_snapshots(args.out, all_rows)
    print(f"\n✔ 已追加 {len(all_rows)} 行快照 -> {args.out}")
    if last_quota:
        print(f"配额: used={last_quota.get('used')} remaining={last_quota.get('remaining')}")
    print("\n提示: 抓取后运行 python build_odds_movement.py 生成 初盘->临场 变化表。")
    print("配额安排(按天): 500/月≈16请求/天 → 9联赛1轮/天(9请求)+预检1请求+赛日补抓重点; 剩余<阈值自动硬阻断。")


if __name__ == "__main__":
    main()