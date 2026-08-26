# -*- coding: utf-8 -*-
"""API-Football 亚盘(Asian Handicap)拉取 -> 追加到 snapshots.csv.
数据源: https://v3.football.api-sports.io (免费档 100次/天)
用法: python fetch_apifb_ah.py
"""
import os, sys, json, io, csv, time, datetime, re, unicodedata, urllib.request

ROOT = r'D:\足球分析'
HERE = os.path.join(ROOT, 'prediction_v2')
SNAP = os.path.join(HERE, 'output', 'odds_snapshots', 'snapshots.csv')
MAP = os.path.join(ROOT, 'analysis_records', 'apifb_fixture_map_20260821.json')
KEY = 'FOOTBALL_API_KEY_FROM_ENV'

def get(url):
    req = urllib.request.Request(url, headers={'x-apisports-key': KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

def parse_ah_value(v):
    """'Home -0.5' -> ('home', -0.5); 'Away +0.25' -> ('away', 0.25).
    注意: API-Football的Asian Handicap数值恒为主队视角(Home -0.5 = 主让0.5;
    Away -0.5 = 该线客队价 = 客受0.5), 两侧 point 均为同一线值, 严禁翻转away侧符号!
    2026-08-21曾误翻导致同线主客拆分、配出1.91/3.49错盘, 已修复."""
    m = re.match(r'^\s*(Home|Away)\s*([+-]?\d+(?:\.\d+)?)\s*$', v, re.I)
    if not m:
        return None, None
    side = 'home' if m.group(1).lower() == 'home' else 'away'
    return side, float(m.group(2))

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='', help='comma-separated fixture ids to retry')
    ap.add_argument('--delay', type=float, default=4.0)
    args = ap.parse_args()
    only = {int(x) for x in args.only.split(',') if x.strip()}
    d = json.load(io.open(MAP, encoding='utf-8'))
    ms = [m for m in d['matches'] if (not only) or int(m['fixture_id']) in only]
    # canonical names + commence_time per the-odds event_id
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
    n_ah = 0
    for m in ms:
        fid = m['fixture_id']
        try:
            od = get('https://v3.football.api-sports.io/odds?fixture=%d' % fid)
        except Exception as e:
            print('ERR fixture %s %s: %r' % (fid, m['target_home'] + ' vs ' + m['target_away'], e))
            time.sleep(args.delay)
            continue
        resp = od.get('response') or []
        if not resp:
            print('NO ODDS: %s | %s vs %s' % (m['target_ko'], m['target_home'], m['target_away']))
            time.sleep(args.delay)
            continue
        eid = m.get('odds_event_id') or ('apifb' + str(fid))
        if m.get('odds_event_id') and m['odds_event_id'] in canon:
            h, a, ct = canon[m['odds_event_id']]
        else:
            h, a = m['target_home'], m['target_away']
            ct = m.get('date') or m['target_ko']
        cnt = 0
        for r0 in resp:
            for bk in r0.get('bookmakers') or []:
                bname = bk.get('name') or str(bk.get('id'))
                for b in bk.get('bets') or []:
                    if b.get('name') != 'Asian Handicap':
                        continue
                    for v in b.get('values') or []:
                        side, pt = parse_ah_value(v.get('value', ''))
                        if side is None:
                            continue
                        try:
                            price = float(v.get('odd'))
                        except Exception:
                            continue
                        if price <= 1.01:
                            continue
                        cnt += 1
                        out_rows.append({
                            'snapshot_ts': ts, 'event_id': eid, 'league': m['target_league'],
                            'commence_time': ct, 'home_team': h, 'away_team': a,
                            'bookmaker': 'apifb:' + bname, 'market': 'asian_handicap',
                            'outcome': v.get('value'), 'side': side,
                            'side_key': '%s@%+.2f' % (side, pt), 'point': pt, 'price': price,
                            'last_update': ts,
                        })
        n_ah += cnt
        print('AH %-4d | %s | %s vs %s | books=%d rows=%d' % (
            fid, m['target_ko'], m['target_home'], m['target_away'], len(resp[0].get('bookmakers') or []), cnt))
        time.sleep(args.delay)
    print('total AH rows:', len(out_rows), 'matches with AH:', n_ah and 1)
    if not out_rows:
        print('nothing to append')
        return
    sys.path.insert(0, os.path.join(HERE, 'src'))
    from live_odds import append_snapshots
    append_snapshots(SNAP, out_rows)
    print('appended ->', SNAP)

if __name__ == '__main__':
    main()
