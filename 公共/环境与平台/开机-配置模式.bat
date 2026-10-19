@echo off
chcp 936 >nul
title Wendeng - Setup Workflow + Download Kontext
cd /d "D:\xiaobai-claude code\comfyUImd\_scripts"
echo ============================================================
echo   SETUP MODE - update workflow + download models (NO image)
echo ------------------------------------------------------------
echo   1^) Inventory   GPU / nodes / models / disk space
echo   2^) Update      push the trimmed workflow to the server
echo   3^) Download    Kontext x4 files (about 15GB, ModelScope)
echo ============================================================
echo.
echo   No image is generated here. After this finishes,
echo   open the browser and click Run yourself.
echo.
"C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" oneshot.py setup

echo.
echo ============================================================
echo   Done. Now refresh the browser and open "“π –∞Ÿœ‡≤æ".
echo   Select the SaveImage node, then press Ctrl+Enter.
echo ============================================================
pause
