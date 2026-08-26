"""the-odds-api 队名 -> 中文名 映射（9 联赛，覆盖 2026 赛季当前市场）。

匹配策略: 先精确匹配 -> 归一化匹配(去重音/小写/去FC等前后缀) -> 原样返回。
"""
import unicodedata

TEAM_CN_ODDS = {
    # ---- 英超 ----
    "Arsenal": "阿森纳", "Aston Villa": "阿斯顿维拉", "Bournemouth": "伯恩茅斯",
    "Brentford": "布伦特福德", "Brighton and Hove Albion": "布莱顿",
    "Burnley": "伯恩利", "Chelsea": "切尔西", "Crystal Palace": "水晶宫",
    "Everton": "埃弗顿", "Fulham": "富勒姆", "Ipswich Town": "伊普斯维奇",
    "Leeds United": "利兹联", "Liverpool": "利物浦", "Manchester City": "曼城",
    "Manchester United": "曼联", "Newcastle United": "纽卡斯尔联",
    "Nottingham Forest": "诺丁汉森林", "Sheffield United": "谢菲尔德联",
    "Southampton": "南安普顿", "Tottenham Hotspur": "热刺",
    "West Ham United": "西汉姆联", "Wolverhampton Wanderers": "狼队",
    "Wolves": "狼队",
    # ---- 英冠 ----
    "Birmingham City": "伯明翰", "Blackburn Rovers": "布莱克本",
    "Bolton Wanderers": "博尔顿", "Bristol City": "布里斯托尔城",
    "Cardiff City": "加的夫城", "Charlton Athletic": "查尔顿",
    "Coventry City": "考文垂", "Derby County": "德比郡", "Hull City": "赫尔城",
    "Lincoln City": "林肯城", "Middlesbrough": "米德尔斯堡", "Millwall": "米尔沃尔",
    "Norwich City": "诺维奇", "Portsmouth": "朴茨茅斯", "Preston North End": "普雷斯顿",
    "Queens Park Rangers": "女王公园巡游者", "Stoke City": "斯托克城",
    "Sunderland": "桑德兰", "Swansea City": "斯旺西", "Watford": "沃特福德",
    "West Bromwich Albion": "西布罗姆维奇", "Wrexham AFC": "雷克瑟姆",
    # ---- 西甲 ----
    "Alavés": "阿拉维斯", "Almería": "阿尔梅里亚", "Athletic Bilbao": "毕尔巴鄂竞技",
    "Atlético Madrid": "马德里竞技", "Barcelona": "巴塞罗那", "Cádiz CF": "加的斯",
    "CA Osasuna": "奥萨苏纳", "Celta Vigo": "塞尔塔", "Deportivo La Coruña": "拉科鲁尼亚",
    "Elche CF": "埃尔切", "Espanyol": "西班牙人", "Getafe": "赫塔费",
    "Girona FC": "赫罗纳", "Granada CF": "格拉纳达", "Las Palmas": "拉斯帕尔马斯",
    "Leganés": "莱加内斯", "Levante": "莱万特", "Mallorca": "马洛卡",
    "Málaga": "马拉加", "Oviedo": "奥维耶多", "Rayo Vallecano": "巴列卡诺",
    "Real Betis": "皇家贝蒂斯", "Real Madrid": "皇家马德里",
    "Real Racing Club de Santander": "桑坦德竞技", "Real Sociedad": "皇家社会",
    "Real Sociedad B": "皇家社会B队", "Real Valladolid CF": "巴拉多利德",
    "Sevilla": "塞维利亚", "Sporting Gijón": "希洪竞技", "Tenerife": "特内里费",
    "Valencia": "瓦伦西亚", "Villarreal": "比利亚雷亚尔",
    # ---- 西乙 ----
    "Albacete": "阿尔瓦塞特", "Andorra CF": "安道尔", "AD Ceuta FC": "休达",
    "Burgos CF": "布尔戈斯", "CD Castellón": "卡斯特利翁", "CD Eldense": "埃尔登塞",
    "Córdoba": "科尔多瓦", "Sabadell FC": "萨瓦德尔", "SD Eibar": "埃瓦尔",
    # ---- 意甲 ----
    "AC Milan": "AC米兰", "AS Roma": "罗马", "Atalanta BC": "亚特兰大",
    "Bologna": "博洛尼亚", "Cagliari": "卡利亚里", "Como": "科莫",
    "Fiorentina": "佛罗伦萨", "Frosinone": "弗罗西诺内", "Genoa": "热那亚",
    "Inter Milan": "国际米兰", "Juventus": "尤文图斯", "Lazio": "拉齐奥",
    "Lecce": "莱切", "Monza": "蒙扎", "Napoli": "那不勒斯", "Parma": "帕尔马",
    "Sassuolo": "萨索洛", "Torino": "都灵", "Udinese": "乌迪内斯", "Venezia": "威尼斯",
    # ---- 德甲 ----
    "Augsburg": "奥格斯堡", "Bayer Leverkusen": "勒沃库森", "Bayern Munich": "拜仁慕尼黑",
    "Borussia Dortmund": "多特蒙德", "Borussia Monchengladbach": "门兴格拉德巴赫",
    "Eintracht Frankfurt": "法兰克福", "FC Schalke 04": "沙尔克04",
    "FSV Mainz 05": "美因茨", "SC Freiburg": "弗赖堡", "Hamburger SV": "汉堡",
    "Hannover 96": "汉诺威96", "Hertha Berlin": "柏林赫塔", "Holstein Kiel": "基尔",
    "RB Leipzig": "莱比锡", "FC St. Pauli": "圣保利", "SV Darmstadt 98": "达姆施塔特",
    "TSG Hoffenheim": "霍芬海姆", "Union Berlin": "柏林联合", "VfB Stuttgart": "斯图加特",
    "VfL Bochum": "波鸿", "VfL Wolfsburg": "沃尔夫斯堡", "Werder Bremen": "云达不莱梅",
    "1. FC Köln": "科隆", "1. FC Heidenheim": "海登海姆", "Elversberg": "埃尔弗斯贝格",
    "Eintracht Braunschweig": "布伦瑞克",
    # ---- 德乙 ----
    "1. FC Kaiserslautern": "凯泽斯劳滕", "1. FC Magdeburg": "马格德堡",
    "1. FC Nürnberg": "纽伦堡", "Arminia Bielefeld": "比勒费尔德",
    "Dynamo Dresden": "德累斯顿迪纳摩", "FC Energie Cottbus": "科特布斯",
    "Greuther Fürth": "菲尔特", "Karlsruher SC": "卡尔斯鲁厄",
    "SC Paderborn": "帕德博恩", "VfL Osnabrück": "奥斯纳布吕克",
    # ---- 法甲 ----
    "Angers": "昂热", "AS Monaco": "摩纳哥", "Auxerre": "欧塞尔", "Brest": "布雷斯特",
    "Le Havre": "勒阿弗尔", "Le Mans FC": "勒芒", "Lille": "里尔", "Lorient": "洛里昂",
    "Lyon": "里昂", "Marseille": "马赛", "Nice": "尼斯",
    "Paris Saint Germain": "巴黎圣日耳曼", "Paris FC": "巴黎FC", "RC Lens": "朗斯",
    "Rennes": "雷恩", "Strasbourg": "斯特拉斯堡", "Toulouse": "图卢兹", "Troyes": "特鲁瓦",
    # ---- 荷甲 ----
    "ADO Den Haag": "海牙", "Ajax": "阿贾克斯", "AZ Alkmaar": "阿尔克马尔",
    "Excelsior": "埃克塞尔西奥", "FC Twente Enschede": "特温特", "FC Utrecht": "乌得勒支",
    "FC Zwolle": "兹沃勒", "Feyenoord": "费耶诺德", "Fortuna Sittard": "锡塔德幸运",
    "Go Ahead Eagles": "前进之鹰", "Groningen": "格罗宁根", "Heerenveen": "海伦芬",
    "NEC Nijmegen": "奈梅亨", "PSV Eindhoven": "埃因霍温", "SC Cambuur": "坎布尔",
    "SC Telstar": "特尔斯达", "Sparta Rotterdam": "鹿特丹斯巴达", "Willem II": "威廉二世",
}

_NORM_CACHE = {}


def _norm(name):
    if name in _NORM_CACHE:
        return _NORM_CACHE[name]
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace(".", "").replace("&", "and")
    for pre in ("1. fc ", "fc ", "cf ", "cd ", "sc ", "vfl ", "sv ", "bv ", "ss ",
                "as ", "ac ", "ud ", "ca ", "tsg "):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    _NORM_CACHE[name] = s
    return s


def to_cn(name):
    """the-odds-api 队名 -> 中文; 无映射时返回原名。"""
    if name in TEAM_CN_ODDS:
        return TEAM_CN_ODDS[name]
    n = _norm(name)
    for k, v in TEAM_CN_ODDS.items():
        if _norm(k) == n:
            return v
    return name


def display(name):
    """显示用: 英文(中文)"""
    cn = to_cn(name)
    if cn == name:
        return name
    return f"{name}({cn})"