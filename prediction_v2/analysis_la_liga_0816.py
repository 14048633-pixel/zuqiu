import math, sys
sys.stdout.reconfigure(encoding='utf-8')

def poisson_pmf(lam, k):
    return math.exp(-lam) * lam**k / math.factorial(k)

def score_matrix(lam_h, lam_a, maxg=10):
    P = [[poisson_pmf(lam_h, i)*poisson_pmf(lam_a, j) for j in range(maxg)] for i in range(maxg)]
    return P

def calc(lam_h, lam_a):
    P = score_matrix(lam_h, lam_a)
    ph = sum(P[i][j] for i in range(10) for j in range(10) if i>j)
    pd = sum(P[i][i] for i in range(10))
    pa = sum(P[i][j] for i in range(10) for j in range(10) if i<j)
    # over/under for various lines
    def over(line):
        tot = 0.0
        for i in range(10):
            for j in range(10):
                if i+j > line: tot += P[i][j]
        return tot
    # top scores
    scores = [(i,j,P[i][j]) for i in range(7) for j in range(7)]
    scores.sort(key=lambda x:-x[2])
    return ph, pd, pa, over, scores[:6]

def devig(o_h, o_d, o_a):
    ih, id_, ia = 1/o_h, 1/o_d, 1/o_a
    s = ih+id_+ia
    return ih/s*100, id_/s*100, ia/s*100

print("="*70)
print("LA LIGA 2026-27 R1  -  3 matches")
print("SP1 2025/26 league avg: home %.3f away %.3f total %.3f" % (1.574, 1.121, 2.695))
print("="*70)

# (name, lam_h, lam_a, odds_home, odds_draw, odds_away, spread_line(home), spread_odds_home, spread_odds_away, ou_line, ou_over_odds, ou_under_odds)
matches = [
    ("M1 Alaves vs Getafe", 0.968, 0.865, 2.37, 2.83, 3.88, -0.25, 1.97, 1.93, 1.75, 1.97, 1.92),
    ("M2 Sevilla vs Rayo Vallecano", 1.225, 1.050, 2.35, 3.25, 3.34, -0.25, 2.01, 1.90, 2.25, 2.02, 1.87),
    ("M3 Santander vs Villarreal (promoted adj)", 1.53, 1.84, 3.30, 3.64, 2.19, 0.25, 1.99, 1.91, 2.75, 1.99, 1.89),
]

for name, lh, la, oh, od, oa, sline, soh, soa, oul, oo, ouu in matches:
    ph, pd, pa, over, top = calc(lh, la)
    mh, md, ma = devig(oh, od, oa)
    print()
    print("### %s" % name)
    print("lambda: home=%.3f away=%.3f total=%.3f" % (lh, la, lh+la))
    print("WDL model: H %.1f%% D %.1f%% A %.1f%%" % (ph*100, pd*100, pa*100))
    print("WDL market(devig): H %.1f%% D %.1f%% A %.1f%%" % (mh, md, ma))
    print("TOP scores: " + ", ".join("%d-%d %.1f%%" % (i,j,p*100) for i,j,p in top))
    for line in [1.5, 1.75, 2.25, 2.5, 2.75, 3.5]:
        ov = over(line)
        print("  over%.2f=%.1f%% under%.2f=%.1f%%" % (line, ov*100, line, (1-ov)*100))
    # handicap prob: home covers spread
    if sline == -0.25:
        # home -0.25: home win -> full win; draw -> half loss
        cover_home = ph + pd*0.5
        cover_away = pa + pd*0.5
    elif sline == 0.25:
        cover_home = ph + pd*0.5
        cover_away = pa + pd*0.5
    else:
        cover_home = ph
        cover_away = pa
    ev_home = cover_home*soh - 1
    ev_away = cover_away*soa - 1
    print("spread %.2f: home_cover=%.1f%% (odds %.2f EV %+.3f) away_cover=%.1f%% (odds %.2f EV %+.3f)" % (sline, cover_home*100, soh, ev_home, cover_away*100, soa, ev_away))
    for line, oo_ in [(oul, oo)]:
        ov = over(line)
        ev_over = ov*oo_ - 1
        ev_under = (1-ov)*ouu - 1
        print("OU line %.2f: over=%.1f%% (odds %.2f EV %+.3f) under=%.1f%% (odds %.2f EV %+.3f)" % (line, ov*100, oo_, ev_over, (1-ov)*100, ouu, ev_under))
    # EV for 1x2
    for label, p, o in [("home", ph, oh), ("draw", pd, od), ("away", pa, oa)]:
        print("  EV 1X2 %s: p=%.1f%% odds=%.2f EV=%+.3f" % (label, p*100, o, p*o-1))
