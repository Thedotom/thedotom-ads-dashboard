@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 > nul
set PYTHONUTF8=1
cd /d "%~dp0"
set "LOG_FILE=%~dp0rank_log.txt"
set "EXPORT_PYTHON=C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "PYTHON=C:\Users\user\AppData\Local\Python\bin\python.exe"
set "PROJECT_DIR=C:\Users\user\Documents\New project 4"
set "PUBLIC_SRC=%PROJECT_DIR%\public_dashboard"
set "PUBLIC_DST=%~dp0..\public_dashboard"

echo [%date% %time%] START >> "%LOG_FILE%"

echo [%date% %time%] SHOPPING RANK SKIP - exact NAVER Shopping source unavailable >> "%LOG_FILE%"

"%PYTHON%" "%~dp0rank_crawler.py" --powerlink-only >> "%LOG_FILE%" 2>&1
set "CRAWLER_ERROR=%ERRORLEVEL%"

if "%CRAWLER_ERROR%"=="0" (
    echo [%date% %time%] CRAWLER DONE >> "%LOG_FILE%"
) else (
    echo [%date% %time%] CRAWLER ERROR %CRAWLER_ERROR% >> "%LOG_FILE%"
)

if exist "%PROJECT_DIR%\scripts\export_public_dashboard.py" (
    if exist "%PROJECT_DIR%\scripts\fetch_cafe24_daily_sales.py" (
        echo [%date% %time%] CAFE24 SALES FETCH START >> "%LOG_FILE%"
        "%EXPORT_PYTHON%" "%PROJECT_DIR%\scripts\fetch_cafe24_daily_sales.py" >> "%LOG_FILE%" 2>&1
        set "CAFE24_ERROR=!ERRORLEVEL!"
        if "!CAFE24_ERROR!"=="0" (
            echo [%date% %time%] CAFE24 SALES FETCH DONE >> "%LOG_FILE%"
        ) else (
            echo [%date% %time%] CAFE24 SALES FETCH ERROR !CAFE24_ERROR! >> "%LOG_FILE%"
        )
    ) else (
        echo [%date% %time%] CAFE24 SALES FETCH SKIP - script not found >> "%LOG_FILE%"
    )
if exist "%PROJECT_DIR%\scripts\build_daily_product_performance.py" (
    echo [%date% %time%] DAILY PRODUCT BUILD START >> "%LOG_FILE%"
    "%EXPORT_PYTHON%" "%PROJECT_DIR%\scripts\build_daily_product_performance.py" >> "%LOG_FILE%" 2>&1
    set "PRODUCT_ERROR=!ERRORLEVEL!"
    if "!PRODUCT_ERROR!"=="0" (
        echo [%date% %time%] DAILY PRODUCT BUILD DONE >> "%LOG_FILE%"
    ) else (
        echo [%date% %time%] DAILY PRODUCT BUILD ERROR !PRODUCT_ERROR! >> "%LOG_FILE%"
    )
) else (
    echo [%date% %time%] DAILY PRODUCT BUILD SKIP - script not found >> "%LOG_FILE%"
)
    echo [%date% %time%] DASHBOARD EXPORT START >> "%LOG_FILE%"
    "%EXPORT_PYTHON%" "%PROJECT_DIR%\scripts\export_public_dashboard.py" >> "%LOG_FILE%" 2>&1
    set "EXPORT_ERROR=!ERRORLEVEL!"
    if "!EXPORT_ERROR!"=="0" (
        echo [%date% %time%] DASHBOARD EXPORT DONE >> "%LOG_FILE%"
        if not exist "%PUBLIC_DST%" mkdir "%PUBLIC_DST%"
        robocopy "%PUBLIC_SRC%" "%PUBLIC_DST%" /E /XD ".git" >> "%LOG_FILE%" 2>&1
        echo [%date% %time%] PUBLIC DASHBOARD COPY DONE >> "%LOG_FILE%"
        git -C "%PUBLIC_DST%" status --porcelain > "%TEMP%\naver_dashboard_git_status.txt" 2>> "%LOG_FILE%"
        for %%A in ("%TEMP%\naver_dashboard_git_status.txt") do set "GIT_STATUS_SIZE=%%~zA"
        if not "!GIT_STATUS_SIZE!"=="0" (
            echo [%date% %time%] GIT PUSH START >> "%LOG_FILE%"
            git -C "%PUBLIC_DST%" add -A >> "%LOG_FILE%" 2>&1
            git -C "%PUBLIC_DST%" commit -m "Auto update dashboard %date% %time%" >> "%LOG_FILE%" 2>&1
            if "!ERRORLEVEL!"=="0" (
                git -C "%PUBLIC_DST%" push origin main >> "%LOG_FILE%" 2>&1
                if "!ERRORLEVEL!"=="0" (
                    echo [%date% %time%] GIT PUSH DONE >> "%LOG_FILE%"
                ) else (
                    echo [%date% %time%] GIT PUSH ERROR !ERRORLEVEL! >> "%LOG_FILE%"
                )
            ) else (
                echo [%date% %time%] GIT COMMIT SKIP OR ERROR !ERRORLEVEL! >> "%LOG_FILE%"
            )
        ) else (
            echo [%date% %time%] GIT PUSH SKIP - no changes >> "%LOG_FILE%"
        )
    ) else (
        echo [%date% %time%] DASHBOARD EXPORT ERROR !EXPORT_ERROR! >> "%LOG_FILE%"
    )
) else (
    echo [%date% %time%] DASHBOARD EXPORT SKIP - script not found >> "%LOG_FILE%"
)

if "%CRAWLER_ERROR%"=="0" (
    echo [%date% %time%] DONE >> "%LOG_FILE%"
) else (
    echo [%date% %time%] ERROR %CRAWLER_ERROR% >> "%LOG_FILE%"
)

echo ---------------------------------------- >> "%LOG_FILE%"
exit /b %CRAWLER_ERROR%
