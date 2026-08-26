# -*- coding: utf-8 -*-
"""联网情报 -> 规则字段 解析器 v2 (仅赛前信息, 不进回测特征)

把 web_search 返回的伤停/首发/临场新闻文本, 转成规则引擎可读字段:
  伤停:     key_injuries / injuries (R10/R125)
  裁判:     referee_style (R124)
  赛事:     is_host_opener (R98) / is_farewell (R25) / group_md+md1_result (R136)
  动机:     home_motivation / away_motivation (R147/R27)
  情绪:     home_psychology / away_psychology (R133)
  额外动力: home_extra_motivation / away_extra_motivation + low_efficiency (R61/R83)
  战术:     home_style / away_style (R88): press/possession/counter/low_block
  环境:     weather / weather_hot_humid / heat / altitude_m / lowland_team / european_team (R85/R86/R87/R135)
  适应:     away_acclimatize_days (R134)
  赛程:     home_rest_days / away_rest_days (R127/R145) / kickoff_clock (R141)

解析原则: 只做保守关键词匹配, 匹配不到不设字段 -> 规则不触发, 避免误判。
主客归属: 按句子归属, 先剥离 "主队 vs 客队" 对阵表述, 同句混提双方时跳过。
"""
import re

_INJURY_PATTERNS = [
    re.compile(r'([\u4e00-\u9fa5]{2,4})(?:因|由于|因為)?(?:伤缺|伤停|缺席|缺阵|无法出战|无缘|停赛|伤疑)'),
    re.compile(r'([\u4e00-\u9fa5]{2,4})伤(?:缺|停|疑)'),
    re.compile(r'([A-Za-z][A-Za-z\-\. ]{1,30}?)\s+(?:is\s+|has been\s+)?(?:ruled out|injured|suspended|out|doubtful)\b', re.IGNORECASE),
]

_POS_KW = [
    ('门将', ['门将', '守门员', 'goalkeeper', 'keeper']),
    ('中卫', ['中卫', '中后卫', 'center.back', 'centre.back', 'centre-back']),
    ('后卫', ['后卫', 'defender', 'defense']),
    ('后腰', ['后腰', 'defensive.mid', 'holding.mid']),
    ('边后卫', ['边后卫', 'full.back', 'full-back', 'wing.back']),
    ('组织核心', ['组织核心', 'playmaker', 'attacking.mid']),
    ('中场', ['中场', 'midfielder', 'central.mid', 'midfield']),
    ('边锋', ['边锋', 'winger']),
    ('攻击手', ['攻击手', '攻击型中场', 'attacking.mid']),
    ('前锋', ['前锋', 'striker', 'forward']),
]
# 位置词 -> 规范名
_KW_TO_POS = {kw.lower(): pn for pn, kws in _POS_KW for kw in kws}


def _norm_pos(kw):
    return _KW_TO_POS.get(str(kw or '').lower(), str(kw or ''))


# 伤停关键词 / 位置词+名字+伤停词 强模式 / 伤停列表条目
_INJ_KW = r'(?:伤缺|伤停|缺席|缺阵|无法出战|无缘|停赛|伤疑|因伤)'
_POS_WORDS = '|'.join('(?:' + '|'.join(kws) + ')' for _, kws in _POS_KW)
_INJ_POS_PAT = re.compile(r'(?P<pos>' + _POS_WORDS + r')(?P<name>[一-龥·]{2,8})(?:因|由于|因為|因伤|长期)?' + _INJ_KW)
_LIST_HEAD = re.compile(r'(确定缺阵|缺阵球员|伤病名单|伤停名单|伤病情况|伤停情况|伤缺|无法出战|ruled out|injured|suspended|out|injury)', re.IGNORECASE)
_INJ_ITEM = re.compile(r'(?:^|\n|[、，,;；])\s*(?:[-*•]\s*)?(?:(?P<pos>' + _POS_WORDS + r'))?(?P<name>[一-龥·]{2,8})(?:（[^）]*?）)?')

# 名字质量过滤(黑名单字): 排除虚词/标题词/语境词凑出来的垃圾名
_NON_NAME_CHARS = set('的将均若继轮月旧名单公告信息披露比赛出战恢复归训练暂确定大概可能场严重已过时长队有无赛季曾季伤因')
_BAD_NAME_WORDS = ('新援', '老伤号', '确定缺阵', '伤病信息有限', '伤停名单', '伤病名单', '伤停信息', '伤病信息', '大名单')
_POS_WORD_SET = set(kw.lower() for _, kws in _POS_KW for kw in kws)
_INJ_BOLD = re.compile(r'\*\*(?P<name>[\u4e00-\u9fa5·]{2,8})(?:（[^）]*?）)?\*\*[^\n]{0,90}?(?:伤缺|伤停|缺席|缺阵|无法出战|无缘|停赛|伤疑|受伤|因伤|ruled out|injured|suspended|doubtful)', re.IGNORECASE)
# 负向语境: 中性词(名单/公告/信息) 与 否定词(暂无/尚未) 与 过时/旧信息
_INJ_NEG_CTX = re.compile(r'大名单|公告|报告|披露|暂无|未公布|尚未|暂未|无伤停|无缺阵|无缺席|无停赛|已过时|过时|旧伤停|旧伤病|伤停信息|伤病信息|无伤病|没有伤|无确定|未记录|未确认|信息')
# 已恢复/复出 语境: 该伤停已解除
_INJ_RECOVERED = re.compile(r'已恢复|已复出|已回归|复出|回归|恢复训练|可出战|能出战|无碍|无大碍|伤愈')

_CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4}
_ROUND_RE = re.compile(r'小组赛[^。；;.!?\n]{0,12}第(\d|[一二三四])轮')

# 战意/心理/战术关键词 (主客按句归属)
_EXTRA_MOTIVATION = [r'回归', r'复出', r'首秀', r'百场', r'里程碑', r'debut', r'return', r'comeback', r'revenge']
_LOW_EFFICIENCY = [r'进球效率低', r'攻击乏力', r'进攻乏力', r'破门乏术', r'难以破门', r'得分能力差',
                   r'poor finishing', r'struggling to score', r'can.t score']
_PSYCH_ORDER = [
    ('换帅', r'换帅|新帅|新教练|new manager|new coach'),
    ('反弹', r'触底反弹|强势反弹|反弹'),
    ('松懈', r'松懈|骄傲自满|精神松懈|轻敌'),
    ('赛季末', r'赛季末|收官阶段|联赛尾声'),
]
_STYLE_ORDER = [
    ('press', r'高位逼抢|高压逼抢|高位压迫|高位防线|pressing|gegenpress'),
    ('possession', r'传控|控球|控球率|tiki.taka|possession'),
    ('counter', r'防反|反击|快速反击|counter'),
    ('low_block', r'铁桶|摆大巴|低位防守|密集防守|龟缩|low block|park the bus'),
]


def _strip_duel(text, team, other):
    """剥离 "主队 vs 客队" 对阵表述, 避免双方同句误判。"""
    if not team or not other:
        return text
    t = re.sub(re.escape(team) + r'\s*(?:vs\.?|VS|versus|对)\s*' + re.escape(other), ' ', text)
    t = re.sub(re.escape(other) + r'\s*(?:vs\.?|VS|versus|对)\s*' + re.escape(team), ' ', t)
    return t


def _mentions(s, team):
    """句子是否提到该队: 全名 / 中文队名前2字或后2字。"""
    if not team:
        return False
    if team in s:
        return True
    if len(team) >= 3:
        return team[:2] in s or team[-2:] in s
    return False


def _team_sentences(text, team, other, role):
    """该队相关句子列表(不含对方队)。支持: 全名/前2后2字缩写/主队/客队/双方。"""
    t = _strip_duel(text, team, other)
    out = []
    for s in re.split(r'[。；;.!?\n，,]', t):
        s = s.strip()
        if not s:
            continue
        if '双方' in s or 'both' in s.lower():
            out.append(s)
            continue
        me = _mentions(s, team) or (role == 'home' and '主队' in s) or (role == 'away' and '客队' in s)
        om = _mentions(s, other) or (role == 'home' and '客队' in s) or (role == 'away' and '主队' in s)
        if me and not om:
            out.append(s)
    return out


def _bad_name(name):
    """名字质量过滤: 排除虚词/标题词凑出的垃圾名(如 确定/大概率/轮比赛的/首轮长期)。"""
    if any(ch in _NON_NAME_CHARS for ch in name):
        return True
    if any(w in name for w in _BAD_NAME_WORDS):
        return True
    if name.lower() in _POS_WORD_SET:
        return True
    return False


def _bad_ctx(text, start):
    """语境过滤: 中性词(名单/公告/信息)、否定词(暂无/尚未)、过时/已恢复信息。"""
    s = max(0, start - 20)
    e = min(len(text), start + 30)
    ctx = text[s:e]
    return bool(_INJ_NEG_CTX.search(ctx) or _INJ_RECOVERED.search(ctx))


def _injury_mentions(text, exclude_names=()):
    """提取伤缺名单(去重, 过滤垃圾名/中性语境)。返回 [(球员名, 起始位置, 位置|None)]。"""
    seen = set()
    out = []

    def _add(name, start, pos):
        name = (name or '').strip()
        key = name.lower().replace('\u00b7', '')
        if len(key) < 2 or key in seen:
            return
        if any(e and (e in key or key in e) for e in exclude_names):
            return
        if _bad_name(key):
            return
        if _bad_ctx(text, start):
            return
        for k in seen:
            if k in key or key in k:
                return
        seen.add(key)
        out.append((name, start, pos))

    # 1) 强模式: 位置词+名字+伤停词 (门将尼兰德缺席 / 前锋贾努扎伊伤疑)
    for m in _INJ_POS_PAT.finditer(text):
        _add(m.group('name'), m.start(), m.group('pos'))
    # 2) 列表格式: 伤停区块内 "- 位置词名字（英文名）、..." 条目
    for head in _LIST_HEAD.finditer(text):
        if _bad_ctx(text, head.start()):
            continue
        base = head.start()
        seg_end = len(text)
        mm = re.search(r'\n#{1,6}\s', text[base + 1:])
        if mm:
            seg_end = base + 1 + mm.start()
        region = text[base: min(seg_end, base + 500)]
        for m in _INJ_ITEM.finditer(region):
            pos = m.group('pos')
            name = m.group('name')
            gs = base + m.start('name')
            if not pos:
                after = region[m.end(): m.end() + 30]
                if not re.search(r'(伤缺|伤停(?!信息)|缺席|缺阵|无缘|停赛|伤疑|受伤|因伤|ruled out|injured|suspended|doubtful)', after, re.I):
                    continue
            _add(name, gs, pos)
    # 3) 粗体名字+伤停语境 (位置从名字前后30字符取)
    for m in _INJ_BOLD.finditer(text):
        pos = None
        ctx = text[max(0, m.start() - 12): min(len(text), m.end() + 25)].lower()
        for pn, kws in _POS_KW:
            if any(kw in ctx for kw in kws):
                pos = pn
                break
        _add(m.group('name'), m.start(), pos)
    # 4) 英文模式
    for m in _INJURY_PATTERNS[2].finditer(text):
        _add(m.group(1), m.start(), None)
    # 4) 通用中文模式(弱): 配合质量/语境过滤
    for pat in (_INJURY_PATTERNS[0], _INJURY_PATTERNS[1]):
        for m in pat.finditer(text):
            _add(m.group(1), m.start(), None)
    return out


def _position_counts(text, mentions):
    """按伤停名字紧邻前方位置词统计位置(不误算阵容名单)。"""
    if not mentions:
        return {}
    counts = {}
    seen_pos = set()
    for name, start, pos in mentions:
        pkey = (name or '').lower().replace('\u00b7', '')
        if pkey in seen_pos:
            continue
        seen_pos.add(pkey)
        if pos:
            p = _norm_pos(pos)
            counts[p] = counts.get(p, 0) + 1
            continue
        head = text[max(0, start - 12):start].lower()
        for pos_name, kws in _POS_KW:
            if any(kw in head for kw in kws):
                counts[pos_name] = counts.get(pos_name, 0) + 1
                break
    return counts


def _name_variants(n):
    """队名匹配变体: 全名 + 中文名前2/后2字。"""
    if not n:
        return []
    vs = [n]
    if re.search(r'[\u4e00-\u9fa5]', n) and len(n) >= 3:
        vs += [n[:2], n[-2:]]
    return vs


def _inj_side(text, start, home_names, away_names):
    """伤停归属: 'home'/'away'/'both'/None (按匹配所在行+后40字符的队名提及)。"""
    pos = start
    for _ in range(15):
        nl = text.rfind('\n', 0, pos)
        if nl == -1:
            break
        line = text[nl + 1:pos]
        stripped = line.strip()
        if stripped.startswith('#') or (stripped.startswith('**') and stripped.rstrip().endswith('**')):
            h = any(n and n in line for n in home_names)
            a = any(n and n in line for n in away_names)
            if h and not a:
                return 'home'
            if a and not h:
                return 'away'
            if h and a:
                return 'both'
        pos = nl
    line_start = text.rfind('\n', 0, start) + 1
    seg = text[line_start: min(len(text), start + 40)]
    h = any(n and n in seg for n in home_names)
    a = any(n and n in seg for n in away_names)
    if h and a:
        return 'both'
    if h:
        return 'home'
    if a:
        return 'away'
    return None


def _first_match(segs, patterns):
    """按顺序返回第一个命中的关键词组标签。"""
    for label, pat in patterns:
        for s in segs:
            if re.search(pat, s, re.IGNORECASE):
                return label
    return None


def _has_any(segs, patterns):
    for s in segs:
        for p in patterns:
            if re.search(p, s, re.IGNORECASE):
                return True
    return False


def parse_web_intel(text, data=None):
    """从 web_search 情报文本提取规则字段。匹配不到不设字段。"""
    text = str(text or '')
    low = text.lower()
    fields = {}
    data = data or {}
    home = data.get('home')
    away = data.get('away')

    # ---------- 1) 伤缺(主客归属) ----------
    home_cn = data.get('home_cn')
    away_cn = data.get('away_cn')
    home_names = _name_variants(home) + (['主队'] if home else []) + ([home_cn] if home_cn else [])
    away_names = _name_variants(away) + (['客队'] if away else []) + ([away_cn] if away_cn else [])
    excludes = [n for n in home_names + away_names if n]
    mentions = _injury_mentions(text, excludes)
    if mentions:
        fields['key_injuries'] = len(mentions)
        pos_counts = _position_counts(text, mentions)
        if pos_counts:
            fields['injuries'] = pos_counts
        h_n = a_n = 0
        h_pos, a_pos = {}, {}
        for name, start, pos in mentions:
            side = _inj_side(text, start, home_names, away_names)
            if side == 'home':
                h_n += 1
                if pos:
                    p = _norm_pos(pos)
                    h_pos[p] = h_pos.get(p, 0) + 1
            elif side == 'away':
                a_n += 1
                if pos:
                    p = _norm_pos(pos)
                    a_pos[p] = a_pos.get(p, 0) + 1
        if h_n:
            fields['home_key_injuries'] = h_n
            if h_pos:
                fields['home_injuries'] = h_pos
        if a_n:
            fields['away_key_injuries'] = a_n
            if a_pos:
                fields['away_injuries'] = a_pos

    # ---------- 2) 裁判风格 ----------
    style = None
    if re.search(r'(点球猎手|爱判点球|penalty hunter|award.*penalt)', low):
        style = 'penalty_hunter'
    elif '主场哨' in text or re.search(r'(home bias|home referee)', low):
        style = 'home_whistle'
    elif re.search(r'裁判.*(严|紧)', text) or re.search(r'referee.*(strict|harsh)', low):
        style = 'strict'
    elif re.search(r'裁判.*(松|宽松)', text) or re.search(r'referee.*(lenient|loose)', low):
        style = 'lenient'
    if style:
        fields['referee_style'] = style

    # ---------- 3) 东道主首战 / 告别战 ----------
    if re.search(r'(揭幕战|东道主|开幕战|opening match|host nation|hosts?)', text, re.IGNORECASE) and \
       re.search(r'(首战|第一场|首场|first match|opener)', text, re.IGNORECASE):
        fields['is_host_opener'] = True
    if re.search(r'(告别战|告别主场|主场告别|farewell|last home game)', text, re.IGNORECASE):
        fields['is_farewell'] = True

    # ---------- 4) 小组赛轮次 / 首战结果 ----------
    m = re.search(r'MD(\d)', low)
    if m:
        fields['group_md'] = int(m.group(1))
    else:
        m = _ROUND_RE.search(text)
        if m:
            r = m.group(1)
            fields['group_md'] = int(r) if r.isdigit() else _CN_NUM.get(r, 2)
    r1 = re.search(r'首战(?:已)?(胜|赢|输|负|平|战平|取胜|告负)', text)
    if r1:
        r = r1.group(1)
        fields['md1_result'] = 'win' if r in ('胜', '赢', '取胜') else ('loss' if r in ('输', '负', '告负') else 'draw')

    # ---------- 5) 出线动机 / 情绪 / 额外动力 / 战术 (按句归属) ----------
    hs, as_ = _team_sentences(text, home, away, 'home'), _team_sentences(text, away, home, 'away')
    hm = _motivation_from_segs(hs)
    am = _motivation_from_segs(as_)
    if hm is not None:
        fields['home_motivation'] = hm
    if am is not None:
        fields['away_motivation'] = am

    hp = _first_match(hs, _PSYCH_ORDER)
    ap = _first_match(as_, _PSYCH_ORDER)
    if hp:
        fields['home_psychology'] = hp
    if ap:
        fields['away_psychology'] = ap

    if _has_any(hs, _EXTRA_MOTIVATION):
        fields['home_extra_motivation'] = True
    if _has_any(as_, _EXTRA_MOTIVATION):
        fields['away_extra_motivation'] = True
    if _has_any(hs, _LOW_EFFICIENCY):
        fields['home_low_efficiency'] = True
    if _has_any(as_, _LOW_EFFICIENCY):
        fields['away_low_efficiency'] = True

    hst = _first_match(hs, _STYLE_ORDER)
    ast_ = _first_match(as_, _STYLE_ORDER)
    if hst:
        fields['home_style'] = hst
    if ast_:
        fields['away_style'] = ast_

    # ---------- 6) 环境/天气/高原 ----------
    if re.search(r'暴雨|积水|waterlogged', low):
        fields['weather'] = 'waterlogged'
    elif re.search(r'大雨|暴雨|heavy rain', low):
        fields['weather'] = 'rain_heavy'
    elif re.search(r'中雨|moderate rain', low):
        fields['weather'] = 'rain_medium'
    elif re.search(r'小雨|light rain', low):
        fields['weather'] = 'rain_light'
    if re.search(r'大风|狂风|强风|windy|strong wind', low):
        fields['weather'] = 'windy'
    if re.search(r'湿热|闷热|hot and humid', low):
        fields['weather_hot_humid'] = True
    if re.search(r'高温|炎热|heatwave|extreme heat', low):
        fields['heat'] = True
    if re.search(r'高原|海拔|altitude', low):
        m = re.search(r'(?:海拔|高原)\s*(\d+)\s*米?', text)
        fields['altitude_m'] = float(m.group(1)) if m else 2200.0
    if re.search(r'低地|海平面|sea.level|lowland', low):
        fields['lowland_team'] = True
    if re.search(r'欧洲(队|球队)|欧洲列强|european', low):
        fields['european_team'] = True

    # ---------- 7) 休息天数 / 适应天数 / 开赛时间 (来自 data) ----------
    hr = data.get('home_last_match_days', data.get('last_match_days'))
    ar = data.get('away_last_match_days', data.get('last_match_days'))
    if hr is not None:
        fields['home_rest_days'] = float(hr)
    if ar is not None:
        fields['away_rest_days'] = float(ar)
    acc = data.get('away_acclimatize_days')
    if acc is not None:
        fields['away_acclimatize_days'] = float(acc)
    elif re.search(r'提前\s*(\d+)\s*天', text):
        fields['away_acclimatize_days'] = float(re.search(r'提前\s*(\d+)\s*天', text).group(1))
    kt = data.get('kickoff_clock', data.get('kickoff_time'))
    if kt is not None:
        mh = re.search(r'(\d{1,2}):?(\d{2})?', str(kt))
        if mh:
            fields['kickoff_clock'] = int(mh.group(1))

    return fields


def _motivation_from_segs(segs):
    """出线动机4档 (基于已归属句子的文本): 4=生死战 3=必须赢 2=正常 1=无欲无求。"""
    if not segs:
        return None
    low_seg = " ".join(segs).lower()
    if re.search(r'(生死战|背水一战|必须赢|必须取胜|do or die|must win|back against the wall)', low_seg):
        return 4
    if re.search(r'(出线关键|关键战|需要赢|要拿下|need.*win|must not lose)', low_seg):
        return 3
    if re.search(r'(已出线|提前出线|无欲无求|保平即可|nothing to play for|already qualified|轮换|练兵)', low_seg):
        return 1
    return None
