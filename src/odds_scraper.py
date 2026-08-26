"""赔率抓取：从多个来源爬市场赔率"""
import re
import json
from curl_cffi import requests


def fetch_odds_oddsportal():
    """从 oddsportal 抓赔率（curl_cffi 模拟浏览器）"""
    try:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.oddsportal.com/",
        }
        r = requests.get(
            "https://www.oddsportal.com/matches/soccer/",
            headers=headers,
            impersonate="chrome110",
            timeout=20,
        )
        if r.status_code != 200:
            return []

        # 尝试从 HTML 中提取赔率数据
        # oddsportal 把数据放在 script 标签的 JSON 中
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", r.text, re.DOTALL)
        odds_data = []

        # 查找包含比赛数据的 JSON
        for script in scripts:
            # 寻找类似 footballData 或 oddsData 的 JSON
            for match in re.finditer(r'"events"\s*:\s*(\[[\s\S]*?\])\s*[,;]', script):
                try:
                    events = json.loads(match.group(1))
                    for ev in events:
                        home = ev.get("homeTeam", ev.get("home", {}))
                        away = ev.get("awayTeam", ev.get("away", {}))
                        ht = home.get("name", "") if isinstance(home, dict) else home
                        at = away.get("name", "") if isinstance(away, dict) else away
                        odds = ev.get("odds", {})
                        odds_data.append({
                            "home_team": ht,
                            "away_team": at,
                            "home_odds": odds.get("home", odds.get("1")),
                            "draw_odds": odds.get("draw", odds.get("X")),
                            "away_odds": odds.get("away", odds.get("2")),
                        })
                except (json.JSONDecodeError, AttributeError):
                    pass

        # fallback: 直接查找表格中的赔率数字
        if not odds_data:
            odds_nums = re.findall(r">(\d+\.\d{2})<", r.text)
            teams = re.findall(r'<a[^>]*href="/[^"]+/"[^>]*>([^<]+)</a>', r.text)
            if odds_nums and teams:
                for i in range(0, min(len(teams) - 1, len(odds_nums) // 3 * 3), 3):
                    if i + 2 < len(odds_nums):
                        odds_data.append({
                            "home_team": teams[i] if i < len(teams) else "",
                            "away_team": teams[i + 1] if i + 1 < len(teams) else "",
                            "home_odds": float(odds_nums[i]),
                            "draw_odds": float(odds_nums[i + 1]),
                            "away_odds": float(odds_nums[i + 2]),
                        })
        return odds_data

    except Exception as e:
        print(f"[oddsportal] 抓取失败: {e}")
        return []


def match_odds(predictions_df, odds_data):
    """将预测与赔率匹配"""
    import pandas as pd
    preds = predictions_df.copy()
    for _, row in preds.iterrows():
        ht = row["home_team"].lower()
        at = row["away_team"].lower()
        for o in odds_data:
            oht = o["home_team"].lower()
            oat = o["away_team"].lower()
            if (oht in ht or ht in oht) and (oat in at or at in oat):
                row["home_odds"] = o["home_odds"]
                row["draw_odds"] = o["draw_odds"]
                row["away_odds"] = o["away_odds"]
                break
    return preds
