import os
"""
阵容数据抓取 — API-Football
开赛前约1小时可获取首发阵容
"""
import requests
from datetime import datetime

API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
BASE = "https://v3.football.api-sports.io"


def get_live_fixtures():
    """获取所有正在进行的比赛"""
    r = requests.get(f"{BASE}/fixtures?live=all", headers={"x-apisports-key": API_KEY})
    data = r.json()
    return data.get("response", [])


def get_today_fixtures(league_ids=None):
    """获取今日赛程"""
    from datetime import date
    today = date.today().isoformat()
    r = requests.get(f"{BASE}/fixtures?date={today}",
                     headers={"x-apisports-key": API_KEY})
    data = r.json()
    fixtures = data.get("response", [])
    if league_ids:
        fixtures = [f for f in fixtures if f.get("league", {}).get("id") in league_ids]
    return fixtures


def get_lineups(fixture_id):
    """获取指定比赛的首发阵容"""
    r = requests.get(f"{BASE}/fixtures/lineups?fixture={fixture_id}",
                     headers={"x-apisports-key": API_KEY})
    data = r.json()
    return data.get("response", [])


def get_events(fixture_id):
    """获取比赛事件（进球、换人、红黄牌）"""
    r = requests.get(f"{BASE}/fixtures/events?fixture={fixture_id}",
                     headers={"x-apisports-key": API_KEY})
    data = r.json()
    return data.get("response", [])


def get_fixture_odds(fixture_id):
    """获取比赛的赔率数据"""
    r = requests.get(f"{BASE}/odds?fixture={fixture_id}",
                     headers={"x-apisports-key": API_KEY})
    data = r.json()
    return data.get("response", [])


def format_lineup(fixture_id):
    """返回格式化的阵容文本"""
    lineups = get_lineups(fixture_id)
    if not lineups:
        return None

    lines = []
    for team in lineups:
        name = team.get("team", {}).get("name", "?")
        formation = team.get("formation", "?")
        lines.append(f"\n{name} ({formation}):")
        for p in team.get("startXI", []):
            player = p.get("player", {})
            lines.append(f"  {player.get('number', '')}. {player.get('name', '?')}")
    return "\n".join(lines)


def find_fixture_by_teams(home_team, away_team, fixtures):
    """在赛程列表中按队名查找比赛"""
    for f in fixtures:
        ht = f["teams"]["home"]["name"].lower()
        at = f["teams"]["away"]["name"].lower()
        if home_team.lower() in ht and away_team.lower() in at:
            return f
        if away_team.lower() in ht and home_team.lower() in at:
            return f
    return None
