@echo off
chcp 65001 >nul
title Dừng Hệ Thống Quản Lý Kho Phân Tán
echo =================================================================
echo  ĐANG DỪNG CÁC DỊCH VỤ PHÂN TÁN (Cổng 8000, 8001, 8002, 3000)...
echo =================================================================
cd /d D:\QLKDCN
powershell -ExecutionPolicy Bypass -File D:\QLKDCN\stop_distributed.ps1
echo =================================================================
echo  TOÀN BỘ CÁC DỊCH VỤ ĐÃ ĐƯỢC DỪNG AN TOÀN!
echo =================================================================
pause
