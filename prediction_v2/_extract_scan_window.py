# -*- coding: utf-8 -*-
import json, io, os, sys, datetime, unicodedata, re

ROOT = os.getcwd()

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

def utc(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None

def main():
    clean_path = sys.argv[1] if len(sys.argv) > 1 else 'analysis_records/scan48h_20260821_0048_clean.json'
    scan_path  = sys.argv[2] if len(sys.argv) > 2 else 'analysis_records/20260821_scan_upcoming.json'
    tag        = sys.argv[3] if len(sys.argv) > 3 else '20260821_0031'
    clean = json.load(io.open(os.path.join(ROOT, clean_path), encoding='utf-8'))
    scan  = json.load(io.open(os.path.join(ROOT, scan_path), encoding='utf-8'))
    ms = scan['matches']
    bypair = {}
    for m in ms:
        bypair.setdefault((norm(m['home']), norm(m['away'])), []).append(m)
    def score(x):
        r = x.get('result') or {}
        rk = r.get('risk_tags') or []
        s = 0
        if not any('\u76d8\u53e3\u8fc7\u671f' in t for t in rk): s += 100
        if r.get('best_bet'): s += 30
        if r.get('direction'): s += 10
        return s
    out = []
    missing = []
    for cm in clean['matches']:
        k = (norm(cm['home']), norm(cm['away']))
        cands = [m for m in bypair.get(k, []) if utc(m.get('ct')) == utc(cm['kickoff_iso'])]
        if not cands:
            cands = bypair.get(k, [])
        if not cands:
            missing.append(cm['home'] + ' vs ' + cm['away'])
            continue
        cands.sort(key=score, reverse=True)
        m = cands[0]
        r = m.get('result') or {}
        out.append({
            'ct': cm['kickoff'], 'league': cm['league'], 'home': cm['home'], 'away': cm['away'],
            'scan_league': m['league'], 'scan_home': m['home'], 'scan_away': m['away'],
            'lam': r.get('lambda'), 'wdl': r.get('wdl'), 'market_fair': r.get('market_fair'),
            'dir': r.get('direction'), 'best': r.get('best_bet'), 'risk': r.get('risk_tags') or [],
            'draw_warn': r.get('draw_warn'), 'star': r.get('star'), 'ev_tier': r.get('ev_tier'),
            'upset': r.get('upset'), 'notes': r.get('notes') or [],
            'snap': m.get('snap'), 'bets': r.get('bets'),
        })
    out.sort(key=lambda x: x['ct'])
    arch = {'ts': datetime.datetime.now().strftime('%Y%m%d_%H%M'),
            'window': clean.get('window_start') + ' ~ ' + clean.get('window_end'),
            'n': len(out), 'n_missing': len(missing), 'missing': missing, 'matches': out}
    os.makedirs(os.path.join(ROOT, 'analysis_records', 'scans'), exist_ok=True)
    ap = os.path.join(ROOT, 'analysis_records', 'scans', 'scan_window_%s.json' % tag)
    io.open(ap, 'w', encoding='utf-8').write(json.dumps(arch, ensure_ascii=False, indent=1))
    lines = []
    for x in out:
        lam = x['lam'] or {}
        bets = x.get('bets') or []
        def pick(prefixes):
            cand = [b for b in bets if b.get('name','').startswith(prefixes) and not b.get('_pband_banned')]
            if not cand: return '-'
            cand = [b for b in cand if b.get('ev') is not None]
            if not cand: return '-'
            cand.sort(key=lambda b: b.get('ev', -9), reverse=True)
            b = cand[0]
            return '%s %.0f%% EV%+.0f%%' % (b['name'], b.get('prob',0)*100, b.get('ev',0)*100)
        best = x['best']
        bb = '%s EV%+.1f%%' % (best['name'], best.get('ev_pct', best.get('ev',0))*100) if best else '\u65e0'
        rk = ';'.join(x['risk'])[:70] if x['risk'] else '-'
        lines.append('%s | %s | %s vs %s | \u03bb%.2f/%.2f | OU:%s | HC:%s | 1X2:%s | %s\u2605%s[%s] | %s' % (
            x['ct'], x['league'], x['home'], x['away'], lam.get('home',0), lam.get('away',0),
            pick(('\u5927','\u5c0f')), pick(('\u8ba9\u7403',)), pick(('1X2',)), bb, x['star'], x['ev_tier'], rk))
    tp = os.path.join(ROOT, 'analysis_records', 'scan_window_%s_directions.txt' % tag)
    io.open(tp, 'w', encoding='utf-8').write('\n'.join(lines))
    print('ARCHIVED:', ap)
    print('TXT:', tp)
    print('n=%d missing=%d' % (len(out), len(missing)))
    for ml in missing:
        print('  MISS:', ml)

if __name__ == '__main__':
    main()


