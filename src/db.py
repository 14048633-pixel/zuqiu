"""
投注追踪 + 自动结算
"""
import sqlite3, re, json
from pathlib import Path
from datetime import datetime

DB_DIR = Path(__file__).resolve().parents[1] / "data" / "db"
DB_PATH = DB_DIR / "tracking.db"


class BetTracker:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # migrations
            for col in ['kickoff_time', 'result_mult']:
                try:
                    conn.execute(f"ALTER TABLE bets ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fixture_id INTEGER, date TEXT, league TEXT,
                    home_team TEXT, away_team TEXT,
                    pred_label TEXT, prob_home REAL, prob_draw REAL, prob_away REAL,
                    confidence REAL, model_version TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fixture_id INTEGER UNIQUE,
                    home_goals INTEGER, away_goals INTEGER,
                    actual_label TEXT, resolved INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fixture_id INTEGER, match_text TEXT,
                    bet_type TEXT, odds REAL, stake REAL DEFAULT 1.0,
                    prob REAL, edge REAL,
                    won INTEGER, profit REAL,
                    parlay_id TEXT,
                    kickoff_time TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS parlays (
                    id TEXT PRIMARY KEY, matches TEXT,
                    total_odds REAL, total_prob REAL, expected_value REAL,
                    won INTEGER, profit REAL,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)

    def save_predictions(self, predictions_df, model_version="v1"):
        with sqlite3.connect(self.db_path) as conn:
            for _, r in predictions_df.iterrows():
                conn.execute("""
                    INSERT INTO predictions
                    (fixture_id, date, league, home_team, away_team,
                     pred_label, prob_home, prob_draw, prob_away, confidence, model_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (r.get("fixture_id"), str(r.get("date")), r.get("league", ""),
                      r.get("home_team"), r.get("away_team"),
                      r.get("pred_label"), r.get("prob_home_win", 0),
                      r.get("prob_draw", 0), r.get("prob_away_win", 0),
                      r.get("confidence", 0), model_version))

    def record_bet(self, fixture_id, match_text, bet_type, odds, prob, edge,
                   stake=1.0, parlay_id=None, kickoff_time=None):
        # sanitize Chinese 大/小 -> o/u (over/under)
        bet_type = bet_type.replace('\u5927','o').replace('\u5c0f','u')
        # 自动生成 parlay_id: 格式 P_YYYYMMDD_随机3位
        if parlay_id is None:
            parlay_id = f"P_{datetime.now().strftime('%Y%m%d')}_{str(hash(match_text + bet_type))[-3:]}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO bets
                (fixture_id, match_text, bet_type, odds, stake, prob, edge, parlay_id, kickoff_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fixture_id, match_text, bet_type, odds, stake, prob, edge, parlay_id, kickoff_time))

    def record_result(self, fixture_id, home_goals, away_goals):
        """记录赛果 (独立连接)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM results WHERE fixture_id=?", (fixture_id,))
            if home_goals > away_goals:
                label = "home"
            elif home_goals < away_goals:
                label = "away"
            else:
                label = "draw"
            conn.execute("""INSERT INTO results (fixture_id, home_goals, away_goals, actual_label, resolved)
                VALUES (?, ?, ?, ?, 1)""", (fixture_id, home_goals, away_goals, label))

    @staticmethod
    def _judge_bet(bet_type, home_goals, away_goals):
        """
        判断单注结果。
        返回 multiplier: 1(赢) 0.5(半赢) 0(走水) -0.5(半输) -1(输)
        """
        total = home_goals + away_goals
        margin = home_goals - away_goals
        bt = bet_type

        # === 亚洲让球盘: 让球主胜(-2.5) / 让球客胜(+0.75) ===
        m = re.search(r'(主胜|客胜)\(([+-]?\d+\.?\d*)\)', bt)
        if m:
            side = m.group(1)
            line = float(m.group(2))
            return BetTracker._judge_asian(side, line, margin)

        # === 1x2 类型 ===
        if "主胜" in bt or "home" in bt.lower():
            return 1.0 if margin > 0 else -1.0
        if "客胜" in bt or "away" in bt.lower():
            return 1.0 if margin < 0 else -1.0
        if "平局" in bt or "draw" in bt.lower():
            return 1.0 if margin == 0 else -1.0

        # === 大小球 ===
        m = re.search(r'[大小oOuU](\d+\.?\d*)', bt)
        if m:
            line = float(m.group(1))
            if "o" in bt.lower().replace('over','o') or "大" in bt:
                return 1.0 if total > line else (-1.0 if total < line else 0.0)
            else:
                return 1.0 if total < line else (-1.0 if total > line else 0.0)

        # === 双方进球 ===
        if "btts" in bt.lower() or "both" in bt.lower() or "双方" in bt:
            return 1.0 if (home_goals > 0 and away_goals > 0) else -1.0

        return -1.0

    @staticmethod
    def _judge_asian(side, line, margin):
        """
        结算亚洲让球盘。
        side: '主胜'|'客胜'
        line: 让球数 (e.g. -2.5, -0.75, +0.25)
        margin: home_goals - away_goals
        returns: 1, 0.5, 0, -0.5, -1
        """
        def _comp(line):
            """单个component结算: (margin + line) > 0 ?"""
            if side == '主胜':
                eff = margin + line
            else:
                eff = -margin + line
            if eff > 0.001:
                return 1.0
            elif eff < -0.001:
                return -1.0
            else:
                return 0.0

        # 判断是否是 quarter line (0.25 或 0.75)
        frac = abs(line - round(line))
        if abs(frac - 0.25) < 0.01 or abs(frac - 0.75) < 0.01:
            # 拆成两个 component
            r1 = _comp(line - 0.25)
            r2 = _comp(line + 0.25)
            return (r1 + r2) / 2.0
        else:
            return _comp(line)

    def settle_bets(self, fixture_id, home_goals, away_goals):
        """结算指定比赛的投注 (支持让球盘半赢/走水/半输)"""
        with sqlite3.connect(self.db_path) as conn:
            bets = conn.execute(
                "SELECT id, odds, stake, bet_type, parlay_id FROM bets WHERE fixture_id=? AND won IS NULL",
                (fixture_id,)
            ).fetchall()
            for bid, odds, stake, bet_type, pid in bets:
                mult = float(self._judge_bet(bet_type, home_goals, away_goals))
                # multiplier → 盈亏
                if mult >= 1.0:       # 全赢
                    won, profit = 1, round((odds - 1) * stake, 2)
                elif mult == 0.5:     # 半赢
                    won, profit = 1, round((odds - 1) * stake * 0.5, 2)
                elif mult == 0.0:     # 走水
                    won, profit = 1, 0.0
                elif mult == -0.5:    # 半输
                    won, profit = 0, round(-stake * 0.5, 2)
                else:                 # 全输
                    won, profit = 0, round(-stake, 2)
                conn.execute("UPDATE bets SET won=?, profit=?, result_mult=? WHERE id=?",
                             (won, profit, mult, bid))
            # 记录赛果
            if home_goals > away_goals:
                actual_label = "home"
            elif home_goals < away_goals:
                actual_label = "away"
            else:
                actual_label = "draw"
            conn.execute("DELETE FROM results WHERE fixture_id=?", (fixture_id,))
            conn.execute("""INSERT INTO results (fixture_id, home_goals, away_goals, actual_label, resolved)
                VALUES (?, ?, ?, ?, 1)""", (fixture_id, home_goals, away_goals, actual_label))

            # 如果有 parlay，顺便结算
            parlay_ids = set(b[4] for b in bets if b[4])
            for pid in parlay_ids:
                self._settle_parlay(conn, pid)
            return len(bets)

    def _settle_parlay(self, conn, parlay_id):
        """结算一个串关的所有注单，写入 parlays 表"""
        legs = conn.execute(
            "SELECT id, odds, stake, won, profit, result_mult FROM bets WHERE parlay_id=?",
            (parlay_id,)
        ).fetchall()
        if not legs:
            return
        adj_odds = 1.0
        any_loss = False
        for bid, odds, stake, won, profit, mult_str in legs:
            mult = float(mult_str) if mult_str is not None else None
            if mult is None:
                return
            if mult <= -0.5:
                any_loss = True
                break
            elif mult == 0.0:
                adj_odds *= 1.0
            elif mult == 0.5:
                adj_odds *= (1 + (odds - 1) * 0.5)
            elif mult >= 1.0:
                adj_odds *= odds

        total_stake = legs[0][3]  # 取第一注的 stake
        if any_loss:
            parlay_won, parlay_profit = 0, round(-total_stake, 2)
        else:
            parlay_won = 1
            parlay_profit = round(adj_odds * total_stake - total_stake, 2)

        conn.execute("""INSERT OR REPLACE INTO parlays (id, matches, total_odds, won, profit, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (parlay_id, json.dumps([l[1] for l in legs]), round(adj_odds, 4),
             parlay_won, parlay_profit))

    def settle_all_pending(self, results_dict):
        """批量结算: {fixture_id: (home_goals, away_goals)}"""
        total = 0
        for fid, (hg, ag) in results_dict.items():
            total += self.settle_bets(fid, hg, ag)
        return total

    def summary(self):
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
            wins = conn.execute("SELECT COUNT(*) FROM bets WHERE won=1").fetchone()[0]
            profit = conn.execute("SELECT COALESCE(SUM(profit), 0) FROM bets").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM bets WHERE won IS NULL").fetchone()[0]
            half_wins = conn.execute("SELECT COUNT(*) FROM bets WHERE CAST(COALESCE(result_mult,0) AS REAL)=0.5").fetchone()[0]
            pushes = conn.execute("SELECT COUNT(*) FROM bets WHERE CAST(COALESCE(result_mult,0) AS REAL)=0.0 AND won IS NOT NULL").fetchone()[0]
            half_losses = conn.execute("SELECT COUNT(*) FROM bets WHERE CAST(COALESCE(result_mult,0) AS REAL)=-0.5").fetchone()[0]
            full_losses = conn.execute("SELECT COUNT(*) FROM bets WHERE won=0 AND CAST(COALESCE(result_mult,0) AS REAL)=-1").fetchone()[0]
            parlay_wins = conn.execute("SELECT COUNT(*) FROM parlays WHERE won=1").fetchone()[0]
            parlay_losses = conn.execute("SELECT COUNT(*) FROM parlays WHERE won=0").fetchone()[0]
            parlay_profit = conn.execute("SELECT COALESCE(SUM(profit), 0) FROM parlays").fetchone()[0]
        roi = round(profit / total * 100, 2) if total > 0 else 0
        return {"total_bets": total, "全赢": wins, "半赢": half_wins, "走水": pushes,
                "半输": half_losses, "全输": full_losses,
                "profit": round(profit, 2), "roi": roi, "pending": pending,
                "parlays": {"wins": parlay_wins, "losses": parlay_losses,
                           "profit": round(parlay_profit, 2)}}

    def pending_bets(self):
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, fixture_id, match_text, bet_type, odds, stake, edge, parlay_id FROM bets WHERE won IS NULL"
            ).fetchall()
        return rows

    def pending_parlays(self):
        """返回尚未完全结算的串关列表"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT p.parlay_id, COUNT(b.id) as legs,
                       SUM(CASE WHEN b.won IS NULL THEN 1 ELSE 0 END) as unsettled
                FROM (SELECT DISTINCT parlay_id FROM bets WHERE parlay_id IS NOT NULL) p
                LEFT JOIN bets b ON b.parlay_id = p.parlay_id
                GROUP BY p.parlay_id
                HAVING unsettled > 0
            """).fetchall()
        return rows

    def parlay_bets(self, parlay_id):
        """返回指定串关的所有注单"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, fixture_id, match_text, bet_type, odds, stake, won, profit, result_mult FROM bets WHERE parlay_id=? ORDER BY id",
                (parlay_id,)
            ).fetchall()
        return rows

    def clear_bets(self, confirm=False):
        """清空投注记录（开发用）"""
        if not confirm:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM bets")
            conn.execute("DELETE FROM parlays")
            conn.execute("DELETE FROM results")
