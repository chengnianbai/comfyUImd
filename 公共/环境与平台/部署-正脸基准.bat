@echo off
chcp 936 >nul
title Wendeng - Deploy Flux Face Baseline
cd /d "D:\xiaobai-claude code\comfyUImd\_scripts"

echo ============================================================
echo   DEPLOY   Flux face baseline   (additive / zero deletion)
echo ------------------------------------------------------------
echo   step 1   push   add_flux_baseline_group.py --push     +9 nodes
echo   step 2   run    face baseline T2I + IMG   draft   2 images
echo   step 3   run    face baseline T2I + IMG   final   2 images
echo ------------------------------------------------------------
echo   Before you start:
echo     - the instance is ON
echo     - COMFY_BASE points to the CURRENT gateway
echo       the hash changes on every boot
echo   Expected total: about 6-10 minutes, then SHUT DOWN.
echo.
echo   Do NOT deploy this with oneshot.py all / quick / setup:
echo   those run build_master_wf.py, which rebuilds only 3 blocks
echo   and would DELETE the whole Flux group, 53 nodes.
echo   Do NOT press Save in an old browser tab.
echo ============================================================
echo.

"C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" oneshot.py baseline
if errorlevel 1 goto FAIL

echo.
echo   DONE. Images are downloaded into the local project.
echo   Then SHUT DOWN the instance - credits burn by uptime.
goto END

:FAIL
echo.
echo   *** FAILED. Read the message above. ***
echo   *** If the push failed, the server workflow is unchanged. ***
:END
pause
