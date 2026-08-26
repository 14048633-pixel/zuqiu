# -*- coding: utf-8 -*-
"""账本球队 -> HF队名(可多个变体) 人工映射 + 联赛ID->Div 映射"""
import json, io

# 账本队名 -> HF 队名列表(含重复ID变体)
HF_MAP = {
    # J1
    'Avispa Fukuoka': ['Avispa Fukuoka'], 'Cerezo Osaka': ['Cerezo Osaka'],
    'FC Machida Zelvia': ['Machida Zelvia', 'Machida'], 'FC Tokyo': ['FC Tokyo'],
    'Fagiano Okayama': ['Fagiano Okayama', 'Okayama'], 'Gamba Osaka': ['Gamba Osaka'],
    'JEF United Chiba': ['JEF United Chiba'], 'Kashima Antlers': ['Kashima Antlers'],
    'Mito HollyHock': ['Mito Hollyhock'], 'Nagoya Grampus': ['Nagoya Grampus'],
    'Sanfrecce Hiroshima': ['Sanfrecce Hiroshima'], 'Shimizu S-Pulse': ['Shimizu S-pulse'],
    'Urawa Red Diamonds': ['Urawa Reds'], 'V-Varen Nagasaki': ['V-varen Nagasaki'],
    'Vissel Kobe': ['Vissel Kobe'], 'Yokohama F Marinos': ['Yokohama F. Marinos'],
    # 中超
    'Beijing FC': ['Beijing Guoan'], 'Chengdu Rongcheng FC': ['Chengdu Rongcheng'],
    'Dalian Yingbo': ['Dalian Yingbo'], 'Henan FC': ['Henan Songshan Longmen'],
    'Liaoning Tieren FC': ['Liaoning Tieren'], 'Shanghai Shenhua FC': ['Shanghai Shenhua'],
    'Shenzhen Peng City FC': ['Shenzhen Xinpengcheng'], 'Tianjin Jinmen Tiger FC': ['Tianjin Jinmen Tiger'],
    'Yunnan Yukun': ['Yunnan Yukun'], 'Zhejiang': ['Zhejiang Professional'],
    # 丹超
    'AC Horsens': ['AC Horsens'], 'FC Copenhagen': ['FC Copenhagen'],
    'OB Odense BK': ['Odense'], 'Randers FC': ['Randers FC'],
    # 土超
    'Alanyaspor': ['Alanyaspor'], 'Fenerbahce': ['Fenerbahce'],
    'Gazişehir Gaziantep': ['Gaziantep'], 'Genclerbirligi SK': ['Genclerbirligi'],
    # 墨超
    'América': ['Club America'], 'Atlas': ['Atlas'], 'Atlético San Luis': ['Atl. San Luis'],
    'FC Juárez': ['Juarez'], 'Monterrey': ['Monterrey'], 'Tigres': ['Tigres UANL'],
    # 巴甲
    'Atletico Mineiro': ['Atletico-MG'], 'Atletico Paranaense': ['Atletico Paranaense', 'Athletico-PR'],
    'Bahia': ['Bahia'], 'Botafogo': ['Botafogo RJ'], 'Bragantino-SP': ['Bragantino'],
    'Chapecoense': ['Chapecoense-sc'], 'Corinthians': ['Corinthians'], 'Coritiba': ['Coritiba'],
    'Cruzeiro': ['Cruzeiro'], 'Fluminense': ['Fluminense'], 'Grêmio': ['Gremio'],
    'Palmeiras': ['Palmeiras'], 'Santos': ['Santos'], 'Sao Paulo': ['Sao Paulo'],
    'Vasco da Gama': ['Vasco'], 'Vitoria': ['Vitoria'],
    # 德乙
    '1. FC Heidenheim': ['Heidenheim'], '1. FC Kaiserslautern': ['Kaiserslautern'],
    '1. FC Nürnberg': ['Nurnberg'], 'Dynamo Dresden': ['Dynamo Dresden', 'Dresden'],
    'Greuther Fürth': ['Greuther Furth'], 'Hertha Berlin': ['Hertha'],
    'Karlsruher SC': ['Karlsruhe'], 'SV Darmstadt 98': ['Darmstadt'],
    # 挪超
    'Molde': ['Molde'], 'Sandefjord': ['Sandefjord'], 'Sarpsborg FK': ['Sarpsborg 08'], 'Tromso': ['Tromso'],
    # 智利甲
    'Cobresal': ['Cobresal'], 'Colo Colo': ['Colo Colo'], 'Deportes Concepción': ['Concepción'],
    'Deportes Limache': ['Deportes Limache'], "O'Higgins": ["O'Higgins"],
    'Union La Calera': ['Union La Calera'], 'Universidad de Chile': ['Universidad de Chile'],
    'Ñublense': ['Nublense'],
    # 比甲
    'Club Brugge': ['Club Brugge'], 'Genk': ['Genk'], 'Gent': ['Gent'],
    'KV Kortrijk': ['Kortrijk'], 'Leuven': ['Oud-Heverlee Leuven'],
    'RAAL La Louvière': ['RAAL La Louvière'], 'Royal Antwerp': ['Antwerp'], 'Westerlo': ['Westerlo'],
    # 瑞超
    'AIK': ['AIK'], 'Degerfors IF': ['Degerfors'], 'Djurgardens IF': ['Djurgarden'],
    'GAIS': ['Gais'], 'Hammarby IF': ['Hammarby IF'], 'IF Brommapojkarna': ['IF Brommapojkarna'],
    'IFK Goteborg': ['IFK Goteborg'], 'IK Sirius': ['IK Sirius'], 'Kalmar FF': ['Kalmar FF'],
    'Malmo FF': ['Malmo FF'], 'Mjällby AIF': ['Mjällby AIF'], 'Örgryte IS': ['Örgryte IS'],
    # 美职
    'Atlanta United FC': ['Atlanta Utd'], 'CF Montreal': ['CF Montreal'], 'Charlotte FC': ['Charlotte'],
    'Chicago Fire': ['Chicago Fire'], 'Colorado Rapids': ['Colorado Rapids'],
    'Columbus Crew SC': ['Columbus Crew'], 'D.C. United': ['DC United'],
    'FC Cincinnati': ['FC Cincinnati'], 'Houston Dynamo': ['Houston Dynamo'],
    'Inter Miami CF': ['Inter Miami'], 'LA Galaxy': ['Los Angeles Galaxy'],
    'Los Angeles FC': ['Los Angeles FC'], 'Minnesota United FC': ['Minnesota United'],
    'Nashville SC': ['Nashville SC'], 'New England Revolution': ['New England Revolution'],
    'New York City FC': ['New York City'], 'New York Red Bulls': ['New York Red Bulls'],
    'Orlando City SC': ['Orlando City'], 'Philadelphia Union': ['Philadelphia Union'],
    'Portland Timbers': ['Portland Timbers'], 'Real Salt Lake': ['Real Salt Lake'],
    'San Diego FC': ['San Diego FC', 'San Diego'], 'San Jose Earthquakes': ['San Jose Earthquakes'],
    'Sporting Kansas City': ['Sporting Kansas City'], 'St. Louis City SC': ['St. Louis City'],
    'Toronto FC': ['Toronto FC'],
    # 英乙
    'Accrington Stanley': ['Accrington'], 'Barnet': ['Barnet'], 'Cheltenham Town': ['Cheltenham'],
    'Chesterfield FC': ['Chesterfield'], 'Colchester United': ['Colchester'],
    'Crawley Town': ['Crawley Town'], 'Crewe Alexandra': ['Crewe'],
    'Exeter City': ['Exeter City'], 'Fleetwood Town': ['Fleetwood Town'],
    'Gillingham': ['Gillingham'], 'Grimsby Town': ['Grimsby'], 'Oldham Athletic': ['Oldham'],
    'Port Vale': ['Port Vale'], 'Rotherham United': ['Rotherham United'],
    'Salford City': ['Salford'], 'Shrewsbury Town': ['Shrewsbury'],
    'Tranmere Rovers': ['Tranmere'], 'Walsall': ['Walsall'],
    # 英冠
    'Birmingham City': ['Birmingham'], 'Bolton Wanderers': ['Bolton Wanderers'],
    'Bristol City': ['Bristol City'], 'Burnley': ['Burnley'], 'Charlton Athletic': ['Charlton'],
    'Derby County': ['Derby'], 'Lincoln City': ['Lincoln City'], 'Middlesbrough': ['Middlesbrough'],
    'Millwall': ['Millwall'], 'Norwich City': ['Norwich'], 'Portsmouth': ['Portsmouth'],
    'Preston North End': ['Preston'], 'Queens Park Rangers': ['QPR'],
    'Sheffield United': ['Sheffield United'], 'Southampton': ['Southampton'], 'Stoke City': ['Stoke'],
    'Swansea City': ['Swansea'], 'Watford': ['Watford'], 'West Bromwich Albion': ['West Brom'],
    'West Ham United': ['West Ham'],
    # 荷甲
    'ADO Den Haag': ['ADO Den Haag'], 'AZ Alkmaar': ['AZ Alkmaar'], 'Ajax': ['Ajax'],
    'Excelsior': ['Excelsior'], 'FC Utrecht': ['Utrecht'], 'Feyenoord': ['Feyenoord'],
    'Fortuna Sittard': ['For Sittard'], 'Go Ahead Eagles': ['Go Ahead Eagles'],
    'Groningen': ['Groningen'], 'Heerenveen': ['Heerenveen'], 'NEC Nijmegen': ['Nijmegen'],
    'PSV': ['PSV Eindhoven'], 'PSV Eindhoven': ['PSV Eindhoven'], 'SC Cambuur': ['Cambuur'],
    'Willem II': ['Willem II'],
    # 葡超
    'Alverca': ['Alverca'], 'CF Estrela': ['Estrela'], 'Estoril': ['Estoril'],
    'FC Porto': ['Porto'], 'Nacional': ['Nacional'], 'Rio Ave FC': ['Rio Ave'],
    # 西乙
    'AD Ceuta FC': ['AD Ceuta FC', 'Ceuta'], 'Albacete': ['Albacete'], 'Andorra CF': ['Andorra'],
    'Burgos CF': ['Burgos'], 'Celta Vigo': ['Celta'], 'Cádiz CF': ['Cadiz'],
    'Córdoba': ['Cordoba'], 'Granada CF': ['Granada'], 'Las Palmas': ['Las Palmas'],
    'Mallorca': ['Mallorca'], 'Oviedo': ['Oviedo'], 'Real Valladolid CF': ['Valladolid'],
    'SD Eibar': ['Eibar'], 'Tenerife': ['Tenerife'],
    # 西甲
    'CA Osasuna': ['Osasuna'], 'Espanyol': ['Espanol'], 'Levante': ['Levante'],
    'Real Racing Club de Santander': ['Santander'], 'Villarreal': ['Villarreal'],
    # 阿甲
    'Aldosivi Mar del Plata': ['Aldosivi'], 'Barracas Central': ['Barracas Central'],
    'Belgrano de Cordoba': ['Belgrano'], 'Boca Juniors': ['Boca Juniors'],
    'CA Tigre BA': ['Tigre'], 'Deportivo Riestra': ['Deportivo Riestra', 'Dep. Riestra'],
    'Estudiantes': ['Estudiantes L.P.'], 'Gimnasia La Plata': ['Gimnasia L.P.'],
    'Independiente Rivadavia': ['Independ. Rivadavia', 'Ind. Rivadavia'],
    'Newells Old Boys': ['Newells Old Boys'], 'Platense': ['Platense'],
    'Rosario Central': ['Rosario Central'], 'San Lorenzo': ['San Lorenzo'],
    'Union Santa Fe': ['Union de Santa Fe'],
}

# 联赛ID -> Div 代码 (football-data 风格; 新联赛沿用 ESPN 风格)
LEAGUE_DIV = {
    1.0: 'E0', 2.0: 'E1', 3.0: 'E2', 4.0: 'E3',
    5.0: 'SP1', 6.0: 'SP2',
    7.0: 'I1', 8.0: 'I2',
    9.0: 'F1', 10.0: 'F2',
    11.0: 'D1', 12.0: 'D2', 13.0: 'N1',
    14.0: 'PO', 15.0: 'BE', 16.0: 'TK',
    19.0: 'BR', 20.0: 'ML', 21.0: 'JP1', 22.0: 'MX',
    23.0: 'NO', 28.0: 'AR', 29.0: 'SW', 30.0: 'DK', 31.0: 'C1',
    53.0: 'CH',
    # 次级/杯赛
    70.0: 'BE2', 73.0: 'NL2', 75.0: 'CUP', 89.0: 'CUP', 90.0: 'CUP', 91.0: 'CUP',
    95.0: 'CUP', 96.0: 'CUP', 97.0: 'CUP', 98.0: 'CUP', 102.0: 'CUP',
    120.0: 'DK2', 100000171.0: 'CUP', 100000073.0: 'CUP', 100000102.0: 'CUP',
    100000629.0: 'CUP', 57.0: 'CUP', 93.0: 'CUP',
}

json.dump({'hf_map': HF_MAP, 'league_div': {str(k): v for k, v in LEAGUE_DIV.items()}},
          io.open('form_phase0/hf_backfill_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('mapping saved:', len(HF_MAP), 'teams')
