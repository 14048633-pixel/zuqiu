# -*- coding: utf-8 -*-
"""API-Football 窗口全盘口拉取: Match Winner(h2h) + Goals Over/Under(totals) + Asian Handicap
用法: python fetch_apifb_window_odds.py [--only f1,f2] [--delay 3]
注意: Asian Handicap point 恒为主队视角线值(Home -0.5=主让0.5, Away -0.5=客受0.5=同线客价), 严禁翻转away符号
"""
import os, sys, json, io, csv, time, datetime, re, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SNAP = os.path.join(HERE, 'output', 'odds_snapshots', 'snapshots.csv')
MAP = os.path.join(ROOT, 'analysis_records', 'apifb_fixture_map_20260821.json')
KEY = os.environ.get("FOOTBALL_API_KEY", "")
BASE = 'https://v3.football.api-sports.io'

def get(url):
    req = urllib.request.Request(url, headers={'x-apisports-key': KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        rem = r.headers.get('x-ratelimit-remaining', '?')
        body = json.loads(r.read().decode('utf-8', 'replace'))
        return body, rem

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--delay', type=float, default=3.0)
    args = ap.parse_args()
    only = {int(x) for x in args.only.split(',') if x.strip()}
    d = json.load(io.open(MAP, encoding='utf-8'))
    ms = [m for m in d['matches'] if (not only) or int(m['fixture_id']) in only]
    # 已知事件: event_id -> (home, away, commence) 用于归并
    canon = {}
    rows = list(csv.reader(io.open(SNAP, encoding='utf-8')))
    hdr = rows[0]
    for r in rows[1:]:
        dd = dict(zip(hdr, r))
        if dd.get('bookmaker') == 'bsd' or dd.get('market') != 'h2h':
            continue
        canon.setdefault(dd.get('event_id'), (dd.get('home_team'), dd.get('away_team'), dd.get('commence_time')))
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out_rows = []
    total_ah = total_h2h = total_tt = 0
    for m in ms:
        fid = m['fixture_id']
        try:
            od, rem = get('%s/odds?fixture=%d' % (BASE, fid))
        except Exception as e:
            print('ERR fixture %s %s: %r (quota_rem=%s)' % (fid, m['target_home'] + ' vs ' + m['target_away'], e, rem))
            time.sleep(args.delay)
            continue
        try:
            rem_i = int(rem)
            if rem_i <= 5:
                print('!! 配额剩余%d, 硬停' % rem_i)
                break
        except Exception:
            pass
        resp = od.get('response') or []
        if not resp:
            print('NO ODDS | %s | %s vs %s (quota_rem=%s)' % (m['target_ko'], m['target_home'], m['target_away'], rem))
            time.sleep(args.delay)
            continue
        eid = m.get('odds_event_id') or ('apifb' + str(fid))
        if m.get('odds_event_id') and m['odds_event_id'] in canon:
            h, a, ct = canon[m['odds_event_id']]
        else:
            h, a = m['target_home'], m['target_away']
            ct = m.get('date') or m['target_ko']
        cnt_ah = cnt_h2h = cnt_tt = 0
        for r0 in resp:
            for bk in r0.get('bookmakers') or []:
                bname = bk.get('name') or str(bk.get('id'))
                for b in bk.get('bets') or []:
                    nm = b.get('name')
                    vals = b.get('values') or []
                    if nm == 'Match Winner':
                        for v in vals:
                            try:
                                price = float(v.get('odd'))
                            except Exception:
                                continue
                            val = v.get('value', '')
                            side = val.lower() if val in ('Home', 'Draw', 'Away') else None
                            if not side or price <= 1.01:
                                continue
                            out_rows.append({'snapshot_ts': ts, 'event_id': eid, 'league': m['target_league'],
                                             'commence_time': ct, 'home_team': h, 'away_team': a,
                                             'bookmaker': 'apifb:' + bname, 'market': 'h2h',
                                             'outcome': (h if side == 'home' else a if side == 'away' else 'Draw'),
                                             'side': side, 'side_key': side, 'point': '', 'price': price,
                                             'last_update': ts})
                            cnt_h2h += 1
                    elif nm == 'Goals Over/Under':
                        for v in vals:
                            mm = re.match(r'^\s*(Over|Under)\s+(\d+(?:\.\d+)?)\s*$', v.get('value', ''), re.I)
                            if not mm:
                                continue
                            try:
                                price = float(v.get('odd'))
                            except Exception:
                                continue
                            side = mm.group(1).lower()
                            pt = float(mm.group(2))
                            if price <= 1.01:
                                continue
                            out_rows.append({'snapshot_ts': ts, 'event_id': eid, 'league': m['target_league'],
                                             'commence_time': ct, 'home_team': h, 'away_team': a,
                                             'bookmaker': 'apifb:' + bname, 'market': 'totals',
                                             'outcome': mm.group(1), 'side': side,
                                             'side_key': '%s@%s' % (side, pt), 'point': pt, 'price': price,
                                             'last_update': ts})
                            cnt_tt += 1
                    elif nm == 'Asian Handicap':
                        for v in vals:
                            mm = re.match(r'^\s*(Home|Away)\s*([+-]?\d+(?:\.\d+)?)\s*$', v.get('value', ''), re.I)
                            if not mm:
                                continue
                            side = mm.group(1).lower()
                            pt = float(mm.group(2))
                            try:
                                price = float(v.get('odd'))
                            except Exception:
                                continue
                            if price <= 1.01:
                                continue
                            out_rows.append({'snapshot_ts': ts, 'event_id': eid, 'league': m['target_league'],
                                             'commence_time': ct, 'home_team': h, 'away_team': a,
                                             'bookmaker': 'apifb:' + bname, 'market': 'asian_handicap',
                                             'outcome': v.get('value'), 'side': side,
                                             'side_key': '%s@%+.2f' % (side, pt), 'point': pt, 'price': price,
                                             'last_update': ts})
                            cnt_ah += 1
        total_ah += cnt_ah; total_h2h += cnt_h2h; total_tt += cnt_tt
        print('OK %-4d | %s | %s vs %s | h2h=%d tt=%d ah=%d quota_rem=%s' % (
            fid, m['target_ko'], m['target_home'], m['target_away'], cnt_h2h, cnt_tt, cnt_ah, rem))
        time.sleep(args.delay)
    print('TOTAL: h2h=%d totals=%d ah=%d' % (total_h2h, total_tt, total_ah))
    if not out_rows:
        print('nothing to append')
        return
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, 'src'))
    from live_odds import append_snapshots
    append_snapshots(SNAP, out_rows)
    print('appended %d -> %s' % (len(out_rows), SNAP))

if __name__ == '__main__':
    main()
