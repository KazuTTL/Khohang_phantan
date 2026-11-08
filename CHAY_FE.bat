@echo off
chcp 65001 >nul
title Khởi Động Giao Diện Web Frontend (SmartLog WMS)
echo =================================================================
echo   ĐANG KHỞI ĐỘNG GIAO DIỆN FRONTEND (Port 3000)...
echo   Ứng dụng Web: http://localhost:3000
echo =================================================================
cd /d D:\QLKDCN\frontend
timeout /t 1 >nul
start http://localhost:3000
npx vite --port 3000 --host
pause
