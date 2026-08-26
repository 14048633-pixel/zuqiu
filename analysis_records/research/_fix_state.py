# -*- coding: utf-8 -*-
import io, re
p = r"D:\足球分析\SESSION_STATE.md"
s = io.open(p, encoding="utf-8").read()
# 删除开头的旧 header + 旧 最近更新 行(在新 header 之前)
s = re.sub(r"^# 会话状态\s*\n\s*\n> 最近更新：[^\n]*\n\s*\n(?=# 会话状态)", "", s, flags=re.M)
io.open(p, "w", encoding="utf-8").write(s)
print("fixed")
