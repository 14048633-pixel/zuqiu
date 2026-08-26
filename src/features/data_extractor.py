"""
比赛数据提取器智能体 - 从用户原始数据提取标准化比赛数据
=============================================================
输入: 用户提供的原始比赛数据 (盘口表 + 情报文本)
输出: 结构化的 match_data 字典, 供 auto_sop 使用

核心能力:
  1. 解析全场/半场盘口 → 提取独赢/让球/大小球赔率
  2. 解析让球细分/大小球细分
  3. 解析情报文本 → 区分主队/客队近期状态
  4. 强制主客队区分: 输出 home_team/away_team + 明确的让球方向标注

用法:
    extractor = MatchDataExtractor()
    match_data = extractor.extract(raw_text)
    # 或手动构建
    match_data = extractor.build_match_data(home, away, odds, hdp, ou, info)
"""
import re
import json
from typing import Dict, List, Optional


class MatchDataExtractor:
    """比赛数据提取器"""

    # ============================================================
    # 主入口: 从原始文本提取
    # ============================================================
    def extract(self, raw_text: str) -> Dict:
        """从用户原始数据文本提取比赛数据"""
        data = {}

        # 1. 提取球队名 (VS/VS分割)
        home, away = self._extract_teams(raw_text)
        data['home'] = home
        data['away'] = away
        data['home_team'] = home
        data['away_team'] = away

        # 2. 提取盘口数据
        odds = self._extract_odds(raw_text)
        data.update(odds)

        # 3. 提取让球细分
        data['hdp_sub'] = self._extract_hdp_sub(raw_text)

        # 4. 提取大小球细分
        data['ou_sub'] = self._extract_ou_sub(raw_text)

        # 5. 提取情报
        info = self._extract_info(raw_text, home, away)
        data.update(info)

        # 6. 标注数据来源
        data['data_source'] = 'user_provided'
        data['home_away_confirmed'] = True

        return data

    # ============================================================
    # 1. 球队名提取 (强制区分主客)
    # ============================================================
    def _extract_teams(self, text: str) -> tuple:
        """从标题行提取主客队. 格式: "主队 VS 客队" (只匹配单行)"""
        for line in text.split('\n'):
            line = line.strip()
            # 匹配 "XXX vs XXX" 单行 (不跨行)
            m = re.search(r'([\u4e00-\u9fffA-Za-z0-9·()（）]+)\s*(?:VS|vs|Vs|vS)\s*([\u4e00-\u9fffA-Za-z0-9·()（）]+)', line)
            if m:
                home = m.group(1).strip('：:、，,。')
                away = m.group(2).strip('：:、，,。')
                return home, away
        return '', ''

    # ============================================================
    # 2. 盘口数据提取
    # ============================================================
    def _extract_odds(self, text: str) -> Dict:
        """提取独赢/让球/大小球赔率"""
        odds = {}
        lines = text.split('\n')

        # 全场独赢: 格式 "独赢 - 2.92 2.16" 或 "独赢 - 主2.92 客2.16" 或 "独赢 - 2.92 3.00 2.16"
        for i, line in enumerate(lines):
            if '独赢' in line and '半场' not in line:
                # 只取"独赢"所在行的数字, 排除表头"主(队名) 客(队名)"里的数字
                # 表头行通常无纯数字, 数据行才有
                nums = re.findall(r'(?:^|[\s(])(\d+\.\d{2})(?=[\s)])', line)
                # 也兼容无括号纯数字
                if len(nums) < 2:
                    nums = re.findall(r'(\d+\.\d{2})', line)
                if len(nums) >= 2:
                    odds['odds_home'] = nums[0]
                    if len(nums) >= 3:
                        odds['odds_draw'] = nums[1]
                        odds['odds_away'] = nums[2]
                    else:
                        odds['odds_away'] = nums[1]
                        # 用户表只有主客两赔率, 补合理平局赔率
                        # 平局赔率应介于主客之间, 更接近高赔方但低于它
                        home_o = float(nums[0])
                        away_o = float(nums[1])
                        low_o = min(home_o, away_o)
                        high_o = max(home_o, away_o)
                        # 平局赔率估算: 主客赔率的调和/均值附近
                        # 经验: 平局赔率 ≈ 高赔方×0.9 ~ 低赔方×1.4 之间
                        draw_o = (low_o + high_o) / 2
                        # 热门方低赔时, 平局应更接近高赔方
                        if low_o < 1.6:
                            draw_o = high_o * 0.9
                        elif low_o < 2.1:
                            draw_o = (low_o + high_o) / 2 * 1.05
                        else:
                            # 低赔方>=2.1(接近盘), 平局≈低赔方×1.35
                            draw_o = low_o * 1.35
                        # 限幅: 平局赔率不能低于低赔方×1.3, 不能高于高赔方
                        draw_o = max(low_o * 1.3, min(draw_o, high_o))
                        odds['odds_draw'] = f"{draw_o:.2f}"
                break

        # 全场让球: 支持两种格式
        #   A) "让球 +0/0.5 1.90 1.92"  (盘口+主赔+客赔, 无@)
        #   B) "让球 +0/0.5 @1.75 -0/0.5 @2.07"  (带@分隔)
        for i, line in enumerate(lines):
            if '让球' in line and '半场' not in line and '独赢' not in line:
                # 格式B: 带@ (主盘口@赔率 客盘口@赔率)
                if '@' in line:
                    parts = re.findall(r'([+-]\d+\.?\d*(?:/\d+\.?\d*)?)\s*@\s*(\d+\.\d+)', line)
                    if len(parts) >= 2:
                        odds['hdp_home'] = f"{parts[0][0]} @{parts[0][1]}"
                        odds['hdp_away'] = f"{parts[1][0]} @{parts[1][1]}"
                        break
                    elif len(parts) == 1:
                        odds['hdp_home'] = f"{parts[0][0]} @{parts[0][1]}"
                        break
                # 格式A: 盘口 + 两个数字 (无@)
                # 支持 [+-] 符号或 0 (平手盘)
                hdp_m = re.search(r'([+-]?\d+\.?\d*(?:/\d+\.?\d*)?)', line)
                if hdp_m:
                    hdp_line = hdp_m.group(1)
                    after = line[hdp_m.end():]
                    nums = re.findall(r'(\d+\.\d+)', after)
                    if len(nums) >= 2:
                        odds['hdp_home'] = f"{hdp_line} @{nums[0]}"
                        odds['hdp_away'] = self._invert_hdp(hdp_line, nums[1])
                    elif len(nums) == 1:
                        odds['hdp_home'] = f"{hdp_line} @{nums[0]}"
                break

        # 全场大小球: "大小球 2.5 大2.00 小1.80" 或 "大小球 2/2.5 大1.87 小1.93"
        for i, line in enumerate(lines):
            if '大小球' in line and '半场' not in line and '独赢' not in line:
                line_m = re.search(r'(\d+\.?\d*(?:/\d+\.?\d*)?)', line)
                ou_line = line_m.group(1) if line_m else '2.5'
                over = re.search(r'大([\d.]+)', line)
                under = re.search(r'小([\d.]+)', line)
                if over:
                    odds['ou_over'] = f"{ou_line} @{over.group(1)}"
                if under:
                    odds['ou_under'] = f"{ou_line} @{under.group(1)}"
                break

        # 兜底: 让球细分表第一行作为主盘口参考
        if 'hdp_home' not in odds:
            for line in lines:
                if re.search(r'[+-]\d+\.?\d*(?:/\d+\.?\d*)?', line) and ('主' in line or '让球' in line):
                    m = re.search(r'([+-]\d+\.?\d*(?:/\d+\.?\d*)?)\s*(\d+\.\d+)', line)
                    if m:
                        odds['hdp_home'] = f"{m.group(1)} @{m.group(2)}"
                    break

        return odds

    def _invert_hdp(self, hdp_line: str, away_odds: str) -> str:
        """根据主队盘口反推客队盘口 (正负互换)"""
        h = hdp_line.strip()
        if h.startswith('+'):
            inv = '-' + h[1:]
        elif h.startswith('-'):
            inv = '+' + h[1:]
        else:
            inv = h
        return f"{inv} @{away_odds}"

    # ============================================================
    # 3. 让球细分提取
    # ============================================================
    def _extract_hdp_sub(self, text: str) -> List[Dict]:
        """提取让球细分表 (主队让球盘口和客队让球盘口)
        格式: "+0.5 1.58 -0.5 2.31" 或 "+0.5 @1.58 -0.5 @2.31" 或 "0 2.07 0 1.75"
        """
        subs = []
        for line in text.split('\n'):
            # 跳过表头 (含"盘口/赔率"字样)
            if any(k in line for k in ['盘口', '赔率', '主队盘口', '类型']):
                continue
            # 匹配 4 组: 主盘口 主赔 客盘口 客赔 (盘口可为 +X/-X/0/X)
            m = re.search(
                r'([+-]?\d+\.?\d*(?:/\d+\.?\d*)?)\s*@?\s*(\d+\.\d+)\s+'
                r'([+-]?\d+\.?\d*(?:/\d+\.?\d*)?)\s*@?\s*(\d+\.\d+)',
                line
            )
            if m:
                subs.append({
                    'home_hdp': {'line': m.group(1), 'odds': m.group(2)},
                    'away_hdp': {'line': m.group(3), 'odds': m.group(4)}
                })
        return subs

    # ============================================================
    # 4. 大小球细分提取
    # ============================================================
    def _extract_ou_sub(self, text: str) -> List[Dict]:
        """提取大小球细分表"""
        subs = []
        for line in text.split('\n'):
            if re.search(r'(大|小)\d+\.?\d*(?:/\d+\.?\d*)?', line):
                m = re.findall(r'(大|小)(\d+\.?\d*(?:/\d+\.?\d*)?)\s*(\d+\.\d+)', line)
                if len(m) >= 2:
                    subs.append({
                        'over': {'line': m[0][1], 'odds': m[0][2]},
                        'under': {'line': m[1][1], 'odds': m[1][2]}
                    })
        return subs

    # ============================================================
    # 5. 情报提取 (区分主客队)
    # ============================================================
    def _extract_info(self, text: str, home: str, away: str) -> Dict:
        """提取情报数据, 明确区分主客"""
        info = {
            'user_form': '',
            'user_h2h': '',
            'user_injuries': '',
            'user_motivation': '',
            'user_analysis': '',
            'home_form': '',
            'away_form': '',
        }

        # 主客队信息: 按段落分
        sections = self._split_sections(text)

        # 近期状态/近10场
        for section, content in sections.items():
            if any(k in section for k in ['近10场', '近期', '战绩', '状态', 'form']):
                # 分离主客
                home_part, away_part = self._split_home_away(content, home, away)
                if home_part:
                    info['home_form'] = home_part
                    info['user_form'] += home_part + '。'
                if away_part:
                    info['away_form'] = away_part
                    info['user_form'] += away_part + '。'

            elif any(k in section for k in ['交锋', 'h2h', '历史']):
                info['user_h2h'] = content.strip()

            elif any(k in section for k in ['伤', '停赛', 'injuries', '缺阵']):
                # 区分主客伤病
                home_part, away_part = self._split_home_away(content, home, away)
                if home_part:
                    info['user_injuries'] += home_part + '。'
                if away_part:
                    info['user_injuries'] += away_part + '。'
                if not info['user_injuries']:
                    info['user_injuries'] = content.strip()

            elif any(k in section for k in ['战意', 'motivation', '优先级', '联赛现状']):
                home_part, away_part = self._split_home_away(content, home, away)
                if home_part:
                    info['user_motivation'] += home_part + '。'
                if away_part:
                    info['user_motivation'] += away_part + '。'
                if not info['user_motivation']:
                    info['user_motivation'] = content.strip()

            elif any(k in section for k in ['总结', '场地', '天气', '战术', '分析', '细节']):
                info['user_analysis'] += content.strip() + '\n'

        # 清理
        for k in info:
            info[k] = info[k].strip()

        return info

    # ============================================================
    # 工具: 段落分割
    # ============================================================
    def _split_sections(self, text: str) -> Dict[str, str]:
        """按标题分割文本为段落"""
        sections = {}
        lines = text.split('\n')
        current = '正文'
        sections[current] = ''
        # 严格标题识别: 以数字+符号开头 或 含明确关键词+冒号
        title_kw = ['近10场', '近十场', '交锋', '伤病', '停赛', '战意', '场地', '天气',
                    '总结', '盘口', '让球', '大小球', '独赢', '近期', '战绩', '情报',
                    '阵容', '轮换', '阵型', '优先级', '历史']
        for line in lines:
            line = line.strip()
            if not line:
                continue
            is_title = False
            # 1. 编号标题: "一、xxx" "1.xxx" "Step X: xxx"
            if re.match(r'^[一二三四五六七八九十]+[、.]', line):
                is_title = True
            elif re.match(r'^(\d+)[、.)）]\s*\S', line):
                is_title = True
            elif re.match(r'^Step\s*\d', line):
                is_title = True
            # 2. 含标题关键词且以冒号结尾
            elif any(k in line for k in title_kw) and (':' in line or '：' in line) and len(line) < 30:
                is_title = True
            # 3. 标题关键词单独成行 (无冒号, 如 "近10场战绩" "伤病停赛" "战意对比")
            #    判断: 短行 + 含关键词 + 不含比分数字(如"7胜0平" "进18球"这类数据)
            elif any(k in line for k in title_kw) and len(line) < 15:
                # 排除数据行 (含 胜/平/负/进/失 搭配数字)
                if not re.search(r'\d+\s*[胜负平]|\d+\s*球', line):
                    # 排除完整句(含句号结尾的内容行, 如"庆南主力后卫停赛。")
                    if not line.endswith('。') and not line.endswith('.') and not line.endswith(';'):
                        is_title = True
            if is_title:
                current = line[:25]
                sections.setdefault(current, '')
            else:
                sections[current] += line + '\n'
        return sections

    # ============================================================
    # 工具: 主客信息分离
    # ============================================================
    def _split_home_away(self, text: str, home: str, away: str) -> tuple:
        """将一段文本按主客队分离 (优先按队名/主/客标记)"""
        home_part = ''
        away_part = ''
        # 按队名分割
        for seg in re.split(r'[。\n；;]', text):
            seg = seg.strip()
            if not seg:
                continue
            # 判断属于主队还是客队
            if home and home[:4] in seg:
                home_part += seg + '。'
            elif away and away[:4] in seg:
                away_part += seg + '。'
            elif '主队' in seg or '主' in seg[:3]:
                home_part += seg + '。'
            elif '客队' in seg or '客' in seg[:3]:
                away_part += seg + '。'
        return home_part, away_part

    # ============================================================
    # 手动构建 match_data
    # ============================================================
    def build_match_data(self, home: str, away: str,
                         odds_home: str, odds_draw: str, odds_away: str,
                         hdp_home: str, hdp_away: str,
                         ou_over: str, ou_under: str,
                         user_form: str = '', user_h2h: str = '',
                         user_injuries: str = '', user_motivation: str = '',
                         user_analysis: str = '') -> Dict:
        """手动构建标准 match_data (明确主客)"""
        return {
            'home': home,
            'away': away,
            'home_team': home,
            'away_team': away,
            'league': '欧联资格赛',
            'odds_home': odds_home,
            'odds_draw': odds_draw,
            'odds_away': odds_away,
            'hdp_home': hdp_home,
            'hdp_away': hdp_away,
            'ou_over': ou_over,
            'ou_under': ou_under,
            'status': 'pre_match',
            'user_form': user_form,
            'user_h2h': user_h2h,
            'user_injuries': user_injuries,
            'user_motivation': user_motivation,
            'user_analysis': user_analysis,
            'data_source': 'user_provided',
            'home_away_confirmed': True,
        }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    extractor = MatchDataExtractor()

    # 完整测试: 特拉维夫数据 (含盘口表+情报)
    raw = """特拉维夫马卡比 vs 索菲亚中央陆军
赛事 欧联资格赛
全场数据
类型 盘口 主(特拉维夫马卡比) 客(索菲亚中央陆军)
独赢 - 1.99 3.45
让球 -0.5 1.99 1.83
大小球 2/2.5 大1.87 小1.93
近10场战绩:
特拉维夫马卡比近10场7胜1平2负总进22失9攻防强势上轮欧联6-0零封谢里夫。
索菲亚中央陆军近10场7胜3平0负不败总进19失10韧性极强客场胜率仅20%。
伤病停赛:
特拉维夫马卡比主力左后卫丹尼格罗珀红牌停赛外援前锋尼古拉斯库十字韧带重伤门将拉波霍夫双主力中卫全健康。
索菲亚中央陆军全员健康无伤病无停赛。
战意对比:
特拉维夫马卡比欧联优先级高全力拿首回合优势。
索菲亚客场死守平局拿到客场进球即完成任务决战留回保加利亚主场。"""
    data = extractor.extract(raw)
    print("=" * 70)
    print("比赛数据提取器 - 完整提取结果")
    print("=" * 70)
    print(f"主队: {data.get('home_team')}")
    print(f"客队: {data.get('away_team')}")
    print(f"独赢: 主{data.get('odds_home')} / 客{data.get('odds_away')}")
    print(f"让球: {data.get('hdp_home')} | {data.get('hdp_away')}")
    print(f"大小: {data.get('ou_over')} | {data.get('ou_under')}")
    print(f"主队情报: {data.get('home_form')[:60]}")
    print(f"客队情报: {data.get('away_form')[:60]}")
    print(f"伤病: {data.get('user_injuries')[:60]}")
    print(f"战意: {data.get('user_motivation')[:60]}")
    print(f"主客区分确认: {data.get('home_away_confirmed')}")
    print()
    print("✅ 数据提取完成, 可直接传入 auto_sop 分析")
