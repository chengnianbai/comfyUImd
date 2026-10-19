@echo off
chcp 936 >nul
title Wendeng - Status Check
cd /d "D:\xiaobai-claude code\comfyUImd\_scripts"

echo ============================================================
echo   STATUS CHECK - read only, changes nothing
echo ============================================================
echo.
echo  [1/2] Instance status + local output list
"C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" oneshot.py report

echo.
echo  [2/2] Local workflow verification (7 branches + run commands)
"C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" verify_master.py

echo.
pause
