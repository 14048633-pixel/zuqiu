import io, sys, csv, math, collections, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "prediction_v2")
import scan_upcoming as su
ts, lavg, index = su.load_team_stats()
FILES = [
 "data/raw/football_data/football_data_recent.csv",
 "data/raw/football_data/matches_2015_2025.csv",
 "data/raw/football_data/matches_2023_2024.csv",
 "data/raw/football_data/api_supplement_2024_2025.csv",
 "data/raw/football_data/api_supplement_2025_2026.csv",
 "data/raw/football_data/supplement_P1_B1.csv",
 "data/raw/football_data/supplement_bsd_2026_2027_b1n1p1.csv",
 "data/raw/football_data/bsd_batch_20260821.csv",
 "data/raw/football_data/footballdata_results.csv",
 "data/raw/football_data/j1_2026_results.csv",
 "data/raw/football_data/csl_2026_results.csv",
]
LEAGUES = {"英超":"E0","西甲":"SP1","德甲":"D1","意甲":"I1","法甲":"F1","英冠":"E1","德乙":"D2",
           "荷甲":"N1","葡超":"P1","比甲":"B1","J1":"JP1","中超":"C1"}
cal = json.load(io.open("strategy_data/league_calib.json", encoding="utf-8"))
def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
def over25(lamh,lama):
    return 1-sum(pois(lamh,i)*pois(lama,j) for i in range(3) for j in range(3) if i+j<=2)
rows_by = {k:[] for k in LEAGUES}
for fp in FILES:
    try: f=io.open(fp,encoding="utf-8",errors="replace")
    except: continue
    for row in csv.DictReader(f):
        div=(row.get("Div") or "").strip()
        if div not in LEAGUES.values(): continue
        try: hg,ag=int(float(row["FTHG"])),int(float(row["FTAG"]))
        except: continue
        s=(row.get("season") or row.get("Season") or "").strip()
        if s in ("2026/2027","2026","2025/2026"):
            rows_by[[k for k,v in LEAGUES.items() if v==div][0]].append((row["HomeTeam"].strip(),row["AwayTeam"].strip(),hg,ag))
print(f"{'联赛':<5}|{'场次':>5}|{'真实大':>6}|{'模型大':>6}|{'总偏移':>7}| 强强(场/偏移) | 混合(场/偏移) | 弱弱(场/偏移)")
for lg, div in LEAGUES.items():
    rows = rows_by[lg]
    if len(rows) < 20: continue
    avg = cal["leagues"].get(lg,{}).get("league_avg", 2.6)/2.0
    buckets = collections.defaultdict(lambda: [0,0,0.0])
    n_ok=0; tot_real=0; tot_pred=0.0
    for h,a,hg,ag in rows:
        hm=su._match_team(h,index); am=su._match_team(a,index)
        hs=ts.get(hm[0],{}).get(div); as_=ts.get(am[0],{}).get(div)
        if not hs or not as_: continue
        hgf=hs["home_gf"]; aga=as_["away_ga"]; agf=as_["away_gf"]; hga=hs["home_ga"]
        if min(hgf,aga,agf,hga)<=0: continue
        lamh=hgf*aga/avg; lama=agf*hga/avg
        hi=hgf/avg; ai=agf/avg
        if hi>=1.05 and ai>=1.05: bk="强强"
        elif hi<=0.95 and ai<=0.95: bk="弱弱"
        else: bk="混合"
        b=buckets[bk]; b[0]+=1; b[1]+=(1 if hg+ag>2.5 else 0); b[2]+=over25(lamh,lama)
        n_ok+=1; tot_real+=(1 if hg+ag>2.5 else 0); tot_pred+=over25(lamh,lama)
    if n_ok < 20: continue
    def fmt(bk):
        n,real,pred = buckets[bk]
        if n<5: return f"{n}场/-"
        return f"{n}场/{(real-pred)/n*100:+.1f}pp"
    print(f"{lg:<5}|{n_ok:>5}|{tot_real/n_ok*100:>5.1f}|{tot_pred/n_ok*100:>5.1f}|{(tot_real-tot_pred)/n_ok*100:>+6.1f}pp| {fmt('强强')} | {fmt('混合')} | {fmt('弱弱')}")
