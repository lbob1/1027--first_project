@echo off
rem ============================================
rem  MiniKnora demo launcher
rem  1) start backend API  (window 1)
rem  2) start ingest worker (window 2)
rem  3) open the built single-file UI (dist/index.html)
rem  Demo account: demo / demo12345
rem ============================================
cd /d %~dp0

start "MiniKnora API - keep this window open" cmd /k "uv run uvicorn app.main:app --port 8000"
start "MiniKnora Worker - keep this window open" cmd /k "uv run celery -A app.workers.celery_app worker --pool=solo -l info"

echo Waiting for backend to start...
timeout /t 6 /nobreak >nul

start "" "%~dp0front-end page\pyknora-web\dist\index.html"

echo.
echo Demo started. Login: demo / demo12345
echo If login fails at first, wait a few seconds and retry (backend warming up).
