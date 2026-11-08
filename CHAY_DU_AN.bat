@echo off
chcp 65001 >nul
title Khởi Động Hệ Thống Quản Lý Kho Phân Tán
echo =================================================================
echo  ĐANG KHỞI ĐỘNG TOÀN BỘ CỤM DỊCH VỤ KHO PHÂN TÁN (SmartLog WMS PRO)
echo  HQ (8000) ^| HN (8001) ^| HCM (8002) ^| Frontend (3000)
echo =================================================================
cd /d D:\QLKDCN
powershell -ExecutionPolicy Bypass -File D:\QLKDCN\start_distributed.ps1
timeout /t 2 >nul
echo Đang mở trình duyệt tới Web Dashboard...
start http://localhost:3000
echo =================================================================
echo  HỆ THỐNG ĐÃ SẴN SÀNG TẠI: http://localhost:3000
echo =================================================================
pause
