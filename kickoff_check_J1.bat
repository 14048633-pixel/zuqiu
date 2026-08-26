@echo off
cd /d "%~dp0"
python prediction_v2\kickoff_check.py --league J1 --fetch >> prediction_v2\output\kickoff_check_J1.log 2>&1
