@echo off
chcp 936 >nul
title Wendeng - Full Run (with download)
cd /d "D:\xiaobai-claude code\comfyUImd\_scripts"
echo ============================================================
echo   FULL RUN - inventory / update / generate / download
echo ------------------------------------------------------------
echo   1^) Inventory   GPU / nodes / models / disk space
echo   2^) Update      push the trimmed workflow to the server
echo   3^) Generate    Wendeng face front (SDXL img2img, no redraw)
echo   4^) Download    Kontext x4 files (about 15GB, in parallel)
echo   5^) Verify      check files then run head-turn x3
echo ============================================================
echo.
echo   Expect 20-30 minutes. Download is the long part.
echo.
"C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" oneshot.py all

echo.
echo ============================================================
echo   Done. Confirm the outputs are downloaded, then SHUT DOWN.
echo   (Credits burn by uptime, not by whether it is generating)
echo ============================================================
pause
