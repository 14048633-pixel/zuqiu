@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   足球预测系统 - 一键部署 (J1/K2/中乙/中超)
echo ============================================
echo.

REM ---------- 1. 检查 Python ----------
set "PY="
python --version >nul 2>&1
if %errorlevel%==0 (
  set "PY=python"
) else (
  py -3 --version >nul 2>&1
  if !errorlevel!==0 set "PY=py -3"
)

if not defined PY (
  echo [错误] 未检测到 Python。
  echo 请先安装 Python 3.10+ 并勾选 "Add Python to PATH":
  echo   https://www.python.org/downloads/
  echo.
  if not "%1"=="--test" start "" "https://www.python.org/downloads/"
  goto :end
)

echo [1/3] 已找到 Python: %PY%
echo.

REM ---------- 2. 运行一键部署验证 ----------
echo [2/3] 运行 setup_verify.py (自动装依赖 + 验模块 + 回归测试 106 项)...
echo.
%PY% setup_verify.py
if %errorlevel% neq 0 (
  echo.
  echo [错误] 部署验证未通过，请查看上方失败项后重试。
  goto :end
)

echo.
echo [3/3] 部署成功！系统可正常使用。
echo 下一步: 运行  python auto_sop.py 比赛数据.json  开始赛前分析
if not "%1"=="--test" start "" "使用流程.md"

:end
echo.
if not "%1"=="--test" pause
endlocal
