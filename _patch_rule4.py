# -*- coding: utf-8 -*-
import io
p = 'prediction_v2/scan_upcoming.py'
s = io.open(p, encoding='utf-8').read()
anchor = '        best["star"] = star\n        best["ev_tier"] = _tier'
# rule4: ???????? (??/?? ou_under_reverse)
LX = chr(0x8054) + chr(0x8d5b)          # ??
Q = chr(0x5c0f) + chr(0x7403)            # ??
FY = chr(0x53cd) + chr(0x5411)           # ??
BZ = chr(0x6807) + chr(0x8bb0)           # ??
SX = chr(0x5b9e) + chr(0x8bc1)           # ??
JJ = chr(0x964d) + chr(0x661f)           # ??
CW = chr(0x4ed3) + chr(0x4f4d)           # ??
JBN = chr(0x51cf) + chr(0x534a)          # ??
XQ = chr(0x52ff) + chr(0x8ffd)           # ??
GZ4 = chr(0x89c4) + chr(0x5219) + chr(0x2463)
insert = (
  '        # ' + GZ4 + '(2026-08-23): ' + chr(0x82f1) + chr(0x51a0) + '/' + chr(0x8377) + chr(0x7532) + ' ' + Q + FY + BZ + '(210' + chr(0x573a) + chr(0x590d) + chr(0x76d8) + ': ???4/?12' + chr(0x547d) + chr(0x4e2d) + '25%, ????7?28.6%) -> ' + Q + '??' + JJ + '+' + CW + JBN + '\n'
  '        if cal.get("ou_under_reverse") and best["name"].startswith("' + Q + '"):\n'
  '            star = max(1, star - 1)\n'
  '            _stake *= 0.5\n'
  '            _ur_tag = "' + LX + Q + FY + BZ + '(%s' + SX + ': ' + Q + '??' + FY + ', ' + XQ + Q + ')" % lg\n'
  '            if _ur_tag not in risk_tags:\n'
  '                risk_tags.append(_ur_tag)\n'
  '            note.append("' + GZ4 + ': %s ' + Q + FY + BZ + '(' + SX + '??<30%, ' + JJ + CW + JBN + ')" % lg)\n'
  '        best["star"] = star\n'
  '        best["ev_tier"] = _tier'
)
c = s.count(anchor)
print('anchor count:', c)
assert c == 1
s = s.replace(anchor, insert)
io.open(p, 'w', encoding='utf-8').write(s)
print('rule4 injected')
