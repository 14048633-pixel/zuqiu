@echo off
cd /d "%~dp0"
python prediction_v2\kickoff_check.py --league Î÷¼× --fetch >> prediction_v2\output\kickoff_check_Î÷¼×.log 2>&1
