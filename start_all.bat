@echo off
chcp 65001 >nul
title HocVuAI - Khoi dong he thong

echo ============================================================
echo        KHOI DONG HE THONG HOCVUAI (BACKEND + FRONTEND)
echo ============================================================

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: 1. Mo cua so Backend FastAPI
echo [*] Dang khoi dong Backend FastAPI (Port 8000)...
start "HocVuAI Backend API" cmd /k "cd /d "%PROJECT_ROOT%" && call "%PROJECT_ROOT%venv\Scripts\activate.bat" && python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000"

:: 2. Mo cua so Frontend Vite React
echo [*] Dang kiem tra va khoi dong Frontend (Port 3000)...
start "HocVuAI Frontend Vite" cmd /k "cd /d "%PROJECT_ROOT%frontend" && if not exist node_modules (echo [*] Chua co node_modules, dang chay npm install... && npm install) && npm run dev"

:: 3. Cho 5 giay de Backend va Frontend khoi dong
echo [*] Cho 5 giay de cac tien trinh hoan tat khoi dong...
timeout /t 5 /nobreak >nul

:: 4. Tu dong mo trinh duyet
echo [*] Dang mo trinh duyet toi http://localhost:3000 ...
start http://localhost:3000

echo.
echo ============================================================
echo [OK] Da gui lenh khoi dong toan bo he thong.
echo      - Backend:  http://localhost:8000/api/health (Swagger: /docs)
echo      - Frontend: http://localhost:3000
echo ============================================================
pause

