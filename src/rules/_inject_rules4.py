# -*- coding: utf-8 -*-
"""向 rule_engine_v2.py 注入第四批战意/环境规则(12条) + R27平局信号接入。"""
import io

path = "rule_engine_v2.py"
src = io.open(path, encoding="utf-8").read()

# 0) R27 接入平局信号判定 (draw_signals + non_draw_signals 排除)
old_draw = "        draw_signals = [s for s in signals if s.rule_id in ['R7', 'R7_draw', 'R_draw_balance', 'R_elo_close']]"
new_draw = "        draw_signals = [s for s in signals if s.rule_id in ['R7', 'R7_draw', 'R_draw_balance', 'R_elo_close', 'R27']]"
assert src.count(old_draw) == 1, "draw_signals anchor"
src = src.replace(old_draw, new_draw, 1)
old_nondraw = "        non_draw_signals = [s for s in signals if s.rule_id not in ['R7', 'R7_draw', 'R_draw_balance', 'R_elo_close']]"
new_nondraw = "        non_draw_signals = [s for s in signals if s.rule_id not in ['R7', 'R7_draw', 'R_draw_balance', 'R_elo_close', 'R27']]"
assert src.count(old_nondraw) == 1, "non_draw_signals anchor"
src = src.replace(old_nondraw, new_nondraw, 1)

# 1) 注册
REG_ANCHOR = "        self.rules['R147'] = self._rule_R147    # 出线算术强制量化\n"
REG_BLOCK = REG_ANCHOR + """        # ============================================================
        # 战意/环境规则 (2026-08-13 第四批: R25/R27/R61/R83/R85/R86/R87/R88/R133/R134/R135/R141)
        # ============================================================
        self.rules['R25'] = self._rule_R25      # 壮行战/告别战
        self.rules['R27'] = self._rule_R27      # 日职排位赛平局魔咒
        self.rules['R61'] = self._rule_R61      # 额外动力因子
        self.rules['R83'] = self._rule_R83      # 额外动力!=进球效率
        self.rules['R85'] = self._rule_R85      # 气候Debuff
        self.rules['R86'] = self._rule_R86      # 高原Debuff
        self.rules['R87'] = self._rule_R87      # 高温轻敌综合征
        self.rules['R88'] = self._rule_R88      # 战术克制权重
        self.rules['R133'] = self._rule_R133    # 心理/情绪因子
        self.rules['R134'] = self._rule_R134    # 高原/气候适应梯度
        self.rules['R135'] = self._rule_R135    # 雨战/风战量化
        self.rules['R141'] = self._rule_R141    # 开赛时间与生物钟
"""
assert src.count(REG_ANCHOR) == 1, "reg anchor count != 1"
src = src.replace(REG_ANCHOR, REG_BLOCK, 1)

# 2) 方法
METHODS_ANCHOR = "        return RuleSignal('R147', '出线算术', False, 0, 0.5, \"\")\n\n\ndef test_v2():"
METHODS = """        return RuleSignal('R147', '出线算术', False, 0, 0.5, "")

    # ============================================================
    # 战意/环境规则 (2026-08-13 第四批)
    # ============================================================

    def _rule_R25(self, data: Dict) -> RuleSignal:
        \"\"\"R25: 壮行战/告别战 - 主场告别战=全力大胜取悦球迷\"\"\"
        if data.get('is_farewell'):
            return RuleSignal('R25', '壮行告别战', True, 1, 0.6, "主场告别战，全力大胜取悦球迷")
        return RuleSignal('R25', '壮行告别战', False, 0, 0.5, "")

    def _rule_R27(self, data: Dict) -> RuleSignal:
        \"\"\"R27: 日职排位赛平局魔咒 - 无欲无求排位赛1-1是默认比分\"\"\"
        league = str(data.get('league', ''))
        hm = int(data.get('home_motivation', 2) or 2)
        am = int(data.get('away_motivation', 2) or 2)
        if any(k in league for k in ('日职', 'J1', 'J联赛', 'j1')) and hm <= 1 and am <= 1:
            return RuleSignal('R27', '日职平局魔咒', True, 1, 0.6, "日职无欲无求排位赛，1-1默认比分，防平")
        return RuleSignal('R27', '日职平局魔咒', False, 0, 0.5, "")

    def _rule_R61(self, data: Dict) -> RuleSignal:
        \"\"\"R61: 额外动力因子 - 回归/首秀等额外动力需效率正常才加成\"\"\"
        triggered = False
        strength = 0
        reason = ""
        if data.get('home_extra_motivation') and not data.get('home_low_efficiency'):
            triggered = True
            strength += 1
            reason += "主队额外动力(回归/首秀/里程碑)+效率正常"
        if data.get('away_extra_motivation') and not data.get('away_low_efficiency'):
            triggered = True
            strength -= 1
            reason += ("；" if reason else "") + "客队额外动力+效率正常"
        if reason:
            reason += "，战意加成"
        return RuleSignal('R61', '额外动力', triggered, strength, 0.6, reason)

    def _rule_R83(self, data: Dict) -> RuleSignal:
        \"\"\"R83: 额外动力!=进球效率 - 低效球队额外动力归零\"\"\"
        triggered = False
        reason = ""
        if data.get('home_extra_motivation') and data.get('home_low_efficiency'):
            triggered = True
            reason += "主队低效+额外动力->额外动力归零"
        if data.get('away_extra_motivation') and data.get('away_low_efficiency'):
            triggered = True
            reason += ("；" if reason else "") + "客队低效+额外动力->额外动力归零"
        return RuleSignal('R83', '额外动力!=效率', triggered, 0, 0.6, reason)

    def _rule_R85(self, data: Dict) -> RuleSignal:
        \"\"\"R85: 气候Debuff - 湿热+欧洲队->进球预期下降\"\"\"
        if data.get('weather_hot_humid') and data.get('european_team'):
            return RuleSignal('R85', '气候Debuff', True, 0, 0.6, "湿热+欧洲队，进球预期下降(小球/慢热倾向)")
        return RuleSignal('R85', '气候Debuff', False, 0, 0.5, "")

    def _rule_R86(self, data: Dict) -> RuleSignal:
        \"\"\"R86: 高原Debuff - 2200m+低地队->下半场进球x0.7\"\"\"
        alt = data.get('altitude_m')
        if alt is not None and float(alt) >= 2000 and data.get('lowland_team'):
            return RuleSignal('R86', '高原Debuff', True, 0, 0.6,
                              f"高原{float(alt):.0f}m+低地队，下半场进球x0.7(小球/爆冷倾向)")
        return RuleSignal('R86', '高原Debuff', False, 0, 0.5, "")

    def _rule_R87(self, data: Dict) -> RuleSignal:
        \"\"\"R87: 高温轻敌综合征 - 高温+T0/T1打T3+小组赛首轮->让胜-1级\"\"\"
        ht = data.get('home_tier')
        at = data.get('away_tier')
        if data.get('heat') and ht is not None and at is not None and int(ht) <= int(at) - 2 \
                and data.get('group_md') == 1:
            return RuleSignal('R87', '高温轻敌', True, -1, 0.6, "高温+T0/T1打T3+小组赛首轮，让胜-1级")
        return RuleSignal('R87', '高温轻敌', False, 0, 0.5, "")

    def _rule_R88(self, data: Dict) -> RuleSignal:
        \"\"\"R88: 战术克制权重 - press克low_block克possession克counter克press\"\"\"
        beats = {'press': 'low_block', 'low_block': 'possession', 'possession': 'counter', 'counter': 'press'}
        hs = data.get('home_style')
        as_ = data.get('away_style')
        if hs in beats and as_ in beats:
            if beats[hs] == as_:
                return RuleSignal('R88', '战术克制', True, 1, 0.5, f"主队{hs}克客队{as_}")
            if beats[as_] == hs:
                return RuleSignal('R88', '战术克制', True, -1, 0.5, f"客队{as_}克主队{hs}")
        return RuleSignal('R88', '战术克制', False, 0, 0.5, "")

    def _rule_R133(self, data: Dict) -> RuleSignal:
        \"\"\"R133: 心理/情绪因子 - 反弹+1/换帅+1/松懈-1/赛季末-1\"\"\"
        pmap = {'反弹': 1, '换帅': 1, '松懈': -1, '赛季末': -1}
        triggered = False
        strength = 0
        reason = ""
        hp = data.get('home_psychology')
        ap = data.get('away_psychology')
        if hp in pmap:
            triggered = True
            strength += pmap[hp]
            reason += f"主队情绪:{hp}({pmap[hp]:+d})"
        if ap in pmap:
            triggered = True
            strength -= pmap[ap]
            reason += ("；" if reason else "") + f"客队情绪:{ap}"
        return RuleSignal('R133', '心理情绪', triggered, strength, 0.6, reason)

    def _rule_R134(self, data: Dict) -> RuleSignal:
        \"\"\"R134: 高原/气候适应梯度 - 客队适应<7天受冲击\"\"\"
        days = data.get('away_acclimatize_days')
        if days is not None:
            d = float(days)
            if d < 3:
                return RuleSignal('R134', '气候适应', True, 1, 0.6,
                                  f"客队适应时间{d:.0f}天(<3)，高原/气候冲击大，利好主队")
            if d < 7:
                return RuleSignal('R134', '气候适应', True, 1, 0.55,
                                  f"客队适应时间{d:.0f}天(3-7)，仍有影响")
        return RuleSignal('R134', '气候适应', False, 0, 0.5, "")

    def _rule_R135(self, data: Dict) -> RuleSignal:
        \"\"\"R135: 雨战/风战量化 - 中雨-0.5/大雨-1/积水-1.5\"\"\"
        w = str(data.get('weather', ''))
        sev = {'小雨': 0, 'rain_light': 0, '中雨': 0.5, 'rain_medium': 0.5,
               '大雨': 1.0, 'rain_heavy': 1.0, '积水': 1.5, 'waterlogged': 1.5,
               '大风': 0.5, 'windy': 0.5}.get(w, 0)
        if sev > 0:
            strength = -1 if sev >= 1.0 else 0
            return RuleSignal('R135', '雨战风战', True, strength, 0.6,
                              f"{w}，进球预期下调{sev:.1f}(小球/受让方受益)")
        return RuleSignal('R135', '雨战风战', False, 0, 0.5, "")

    def _rule_R141(self, data: Dict) -> RuleSignal:
        \"\"\"R141: 开赛时间与生物钟 - 非黄金时段慢热倾向\"\"\"
        h = data.get('kickoff_clock')
        if h is None:
            return RuleSignal('R141', '生物钟', False, 0, 0.5, "")
        h = int(h)
        if 19 <= h <= 22:
            return RuleSignal('R141', '生物钟', False, 0, 0.5, "")
        label = "下午" if 12 <= h < 19 else ("上午" if h < 12 else "深夜")
        debuff = 0.2 if 12 <= h < 19 else (0.3 if h < 12 else 0.5)
        return RuleSignal('R141', '生物钟', True, 0, 0.5,
                          f"开赛{label}({h}时)，生物钟影响-{debuff:.1f}，慢热倾向")
"""
assert src.count(METHODS_ANCHOR) == 1, "methods anchor count != 1"
src = src.replace(METHODS_ANCHOR, METHODS + "\n\ndef test_v2():", 1)

io.open(path, "w", encoding="utf-8", newline="\n").write(src)
print("inject batch4 ok")