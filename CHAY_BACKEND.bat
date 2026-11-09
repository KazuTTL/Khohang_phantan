@echo off
chcp 65001 >nul
title Khởi Động 3 Node Backend Phân Tán
echo =================================================================
echo   KHỞI ĐỘNG CỤM BACKEND PHÂN TÁN (SmartLog WMS PRO)
echo   1. HQ Coordinator  : http://localhost:8000/docs
echo   2. Chi nhánh Hà Nội: http://localhost:8001/docs
echo   3. Chi nhánh TP.HCM: http://localhost:8002/docs
echo =================================================================

cd /d D:\QLKDCN\backend

:: 1. Khởi động Node Trụ sở chính (HQ - 8000)
echo [1/3] Đang bật Node HQ (Port 8000)...
start "Node HQ - Port 8000 (Saga Coordinator)" cmd /k "title Node HQ (8000) && set PYTHONPATH=D:\QLKDCN\backend&& python -m uvicorn hq_service.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 1 >nul

:: 2. Khởi động Node Chi nhánh Hà Nội (HN - 8001)
echo [2/3] Đang bật Node Chi nhánh Hà Nội (Port 8001)...
start "Node Chi Nhánh Hà Nội - Port 8001" cmd /k "title Node HN (8001) && set PYTHONPATH=D:\QLKDCN\backend&& set BRANCH_CODE=HN&& set PORT=8001&& python -m uvicorn branch_service.main:app --host 0.0.0.0 --port 8001 --reload"

timeout /t 1 >nul

:: 3. Khởi động Node Chi nhánh TP.HCM (HCM - 8002)
echo [3/3] Đang bật Node Chi nhánh TP.HCM (Port 8002)...
start "Node Chi Nhánh TP.HCM - Port 8002" cmd /k "title Node HCM (8002) && set PYTHONPATH=D:\QLKDCN\backend&& set BRANCH_CODE=HCM&& set PORT=8002&& python -m uvicorn branch_service.main:app --host 0.0.0.0 --port 8002 --reload"

echo =================================================================
echo   CẢ 3 NODE BACKEND ĐÃ ĐƯỢC MỞ TRÊN 3 CỬA SỔ RIÊNG BIỆT!
echo   Bạn có thể xem log thời gian thực khi thực hiện giao dịch Saga.
echo =================================================================
pause
