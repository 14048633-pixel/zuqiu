"""
Team name translation map (English -> Chinese)
"""
TEAM_CN = {
    # UCL / European
    "Sutjeska": "苏捷斯卡",
    "Kairat Almaty": "海拉提",
    "Universitatea Craiova": "克拉约瓦大学",
    "Maxline Vitebsk": "维捷布斯克",
    "Atert Bissen": "阿泰尔特比森",
    "KI Klaksvik": "KI克拉克斯维克",
    "Bregenz": "布雷根茨",
    "Austria Lustenau": "奥地利卢斯特瑙",
    "La Louviere": "拉卢维耶尔",
    "Virton": "维尔通",
    "AGF Aarhus": "奥胡斯",
    "Horsens": "霍森斯",
    "Genk(R)": "根克预备队",
    "RWDM Brussels": "RWDM布鲁塞尔",
    "Leones FC": "莱昂内斯",
    "Cuenca": "昆卡",

    # Australia
    "FK Beograd": "贝尔格莱德FK",
    "North Sunshine Eagles": "北阳光老鹰",
    "Kahibah": "卡希巴",
    "Maitland": "梅特兰",
    "Charlestown azzurri": "查尔斯顿蓝军",
    "Weston Workers Bears": "韦斯顿工人熊",
    "Marlin Coast Rangers": "马林海岸巡游者",
    "Brunswick Juventus": "不伦瑞克尤文图斯",

    # USA
    "Lexington": "列克星敦",
    "New Mexico Utd": "新墨西哥联",
    "Miami FC": "迈阿密FC",
    "Indy eleven": "印地十一人",

    # Korea
    "Cheongju FC": "清州FC",
    "Gyeongju Khnp": "庆州水利核电",
    "Jeonnam dragons": "全南天龙",
    "Chungnam asan": "忠南牙山",
    "Daegu": "大邱",
    "Siheung citizen": "始兴市民",
    "Busan Transport": "釜山交通",
    "Suwon Samsung.B": "水原三星B队",
    "Namyangju Cit": "南阳州市民",
    "Gimpo Citizen": "金浦市民",
    "Ulsan Citizen": "蔚山市民",
    "Seoul E-Land": "首尔衣恋",
    "Changwon City": "昌原市",
    "Gimhae City": "金海市",
    "Seongnam FC": "城南FC",
    "Pocheon citizen": "抱川市民",
    "Paju Frontier": "坡州 frontiers",
    "Gangneung": "江陵",
    "Yongin FC": "龙仁FC",
    "Dangjin Citizen": "唐津市民",
    "Hwaseong FC": "华城FC",
    "Yangpyeong": "杨平",
    "Ansan Greeners": "安山绿人",
    "Jinju citizen": "晋州市民",
    "B.I Park": "BI公园",
    "Geoje Citizen": "巨济市民",
    "Suwon FC": "水原FC",
    "Pyeongchang United": "平昌联",
    "Cheonan City": "天安市",
    "Mokpo": "木浦",
    "Gyeongnam FC": "庆南FC",
    "Yeoju": "骊州",
}

def to_cn(name):
    """Translate team name to Chinese, fallback to original"""
    return TEAM_CN.get(name, name)

def match_to_cn(match_text):
    """Translate 'TeamA vs TeamB' to Chinese"""
    parts = match_text.split(" vs ")
    if len(parts) == 2:
        return f"{to_cn(parts[0])} vs {to_cn(parts[1])}"
    return match_text
