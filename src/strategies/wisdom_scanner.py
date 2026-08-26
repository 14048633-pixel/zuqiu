"""
Wisdom of Crowd strategy scanner.
Usage: python wisdom_scanner.py [--threshold 0.05] [--live]

Uses historical Pinnacle odds data to find value bets.
If --live, also calls InferSports scan.sh for today's matches.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import subprocess, json, sys

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "raw" / "football_data" / "matches_2015_2025.csv"
INFERSPORTS_DIR = Path.home() / ".config" / "opencode" / "skills" / "infersports"

# Load and build the strategy database
def load_strategy_db():
    df = pd.read_csv(DATA_FILE, low_memory=False)
    top = ["英超", "西甲", "意甲", "德甲", "法甲"]
    df = df[df["league"].isin(top)].copy()
    
    # Need both opening and closing odds
    has_odds = df[["PSH", "PSD", "PSA", "PSCH", "PSCD", "PSCA"]].notna().all(axis=1)
    df = df[has_odds].copy()
    
    # Compute EV per match (best outcome only)
    results = []
    for _, row in df.iterrows():
        imp_h, imp_d, imp_a = 1/row["PSCH"], 1/row["PSCD"], 1/row["PSCA"]
        total_imp = imp_h + imp_d + imp_a
        # Fair closing probs (de-vig)
        fair_probs = {2: imp_h/total_imp, 1: imp_d/total_imp, 0: imp_a/total_imp}
        
        best_ev, best_label, best_odds = -999, None, 0
        for outcome, label, col_open in [(2, "Home", "PSH"), (1, "Draw", "PSD"), (0, "Away", "PSA")]:
            open_odds = row[col_open]
            fair_close = 1 / fair_probs[outcome]
            ev = open_odds / fair_close - 1
            if ev > best_ev:
                best_ev, best_label, best_odds = ev, label, open_odds
        
        results.append({
            "league": row["Div"], "date": row["Date"], "season": row["season"],
            "home": row["HomeTeam"], "away": row["AwayTeam"],
            "outcome": best_label, "open": best_odds, "ev": round(best_ev, 4),
        })
    
    return pd.DataFrame(results)

# Get recent league stats for baseline comparison
def get_league_baselines(db):
    """Get average EV by league for reference"""
    return db.groupby("league").agg(
        avg_ev=("ev", "mean"),
        count=("ev", "count"),
        pct_positive=("ev", lambda x: (x > 0).mean()),
    ).sort_values("count", ascending=False)

def scan_historical(threshold=0.05, min_bets=100):
    """Run the strategy on all historical data"""
    db = load_strategy_db()
    baselines = get_league_baselines(db)
    
    print("=" * 60)
    print("WISDOM OF THE CROWD — Historical Performance")
    print("=" * 60)
    print(f"\nTotal outcomes scanned: {len(db):,}")
    print(f"Threshold: EV >= {threshold:.0%}")
    
    for ev_min in [0, 0.03, 0.05, 0.08, 0.10, 0.15]:
        sub = db[(db["ev"] >= ev_min)]
        if len(sub) == 0:
            continue
        print(f"\n  EV >= {ev_min:.0%}: {len(sub):>6,d} outcomes, avg EV {sub['ev'].mean():+.2%}")
    
    print(f"\n\nLeague baselines (avg EV when opening > closing):")
    print(f"  {'League':>6s} {'Count':>8s} {'Avg EV':>8s} {'% Positive':>10s}")
    print(f"  {'-'*35}")
    for league, row in baselines.head(10).iterrows():
        print(f"  {league:>6s} {int(row['count']):>8,d} {row['avg_ev']:>+7.2%} {row['pct_positive']:>9.1%}")
    
    return db

def scan_live():
    """Call InferSports scan.sh for today's value"""
    scan_script = INFERSPORTS_DIR / "scripts" / "scan.sh"
    if not scan_script.exists():
        print("InferSports scan.sh not found")
        return
    
    print("\n" + "=" * 60)
    print("INFERSPORTS — Today's Value Scan")
    print("=" * 60)
    result = subprocess.run(
        ["bash", str(scan_script), "--sport", "football", "--market", "1x2", "--min-edge", "3", "--limit", "15"],
        capture_output=True, text=True, timeout=30
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:500])

def scan_steamers(min_steam=0.10):
    """Steamer strategy: bet on odds that shorten significantly from opening to closing"""
    df = pd.read_csv(DATA_FILE, low_memory=False)
    top = ["英超", "西甲", "意甲", "德甲", "法甲"]
    df = df[df["league"].isin(top)].copy()
    has_odds = df[["PSH", "PSD", "PSA", "PSCH", "PSCD", "PSCA"]].notna().all(axis=1)
    df = df[has_odds].copy()
    
    print("=" * 60)
    print(f"STEAMER STRATEGY (odds shorten ≥ {min_steam:.0%})")
    print("=" * 60)
    
    results = []
    for _, row in df.iterrows():
        outcomes = []
        for outcome, label, col_open, col_close in [
            (2, "Home", "PSH", "PSCH"),
            (1, "Draw", "PSD", "PSCD"),
            (0, "Away", "PSA", "PSCA"),
        ]:
            open_odds, close_odds = row[col_open], row[col_close]
            if pd.isna(open_odds) or pd.isna(close_odds) or open_odds <= 0:
                continue
            steam = (open_odds - close_odds) / open_odds
            outcomes.append((outcome, label, open_odds, close_odds, steam))
        
        if not outcomes:
            continue
        best = max(outcomes, key=lambda x: x[4])
        actual = row["FTR"]
        won = (best[0] == 2 and actual == "H") or (best[0] == 1 and actual == "D") or (best[0] == 0 and actual == "A")
        results.append({
            "date": row["Date"],
            "home": row["HomeTeam"],
            "away": row["AwayTeam"],
            "outcome": best[1], "open": best[2], "close": best[3],
            "steam": best[4], "won": won,
        })
    
    df_r = pd.DataFrame(results)
    for steam_min in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
        sub = df_r[df_r["steam"] >= steam_min]
        if len(sub) == 0:
            continue
        n = len(sub)
        profit = sub.apply(lambda r: r["open"] - 1 if r["won"] else -1, axis=1).sum()
        print(f"  Steam ≥ {steam_min:.0%}: {n:>5d} bets, {sub['won'].mean():.1%} hit, ROI {profit/n:+.2%}")
    
    # Show top recent steamers (2024-2025)
    recent = df_r[(df_r["date"].str.contains("2024|2025", na=False)) & (df_r["steam"] >= min_steam)]
    recent = recent.sort_values("steam", ascending=False).head(20)
    if len(recent) > 0:
        print(f"\n  Top recent steamers (≥{min_steam:.0%}):")
        for _, r in recent.iterrows():
            sign = "W" if r["won"] else "L"
            print(f"  [{sign}] {r['date']} {r['home']:25s} vs {r['away']:25s} {r['outcome']:5s} {r['open']:.2f}→{r['close']:.2f} ({r['steam']:.0%})")
    
    return df_r


if __name__ == "__main__":
    threshold = 0.05
    do_live = "--live" in sys.argv
    do_steamer = "--steamer" in sys.argv or "--all" in sys.argv
    
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--threshold"):
            threshold = float(sys.argv[i+1])
    
    if do_steamer or "--all" in sys.argv:
        scan_steamers()
        print()
    else:
        scan_historical(threshold)
    
    if do_live:
        scan_live()
