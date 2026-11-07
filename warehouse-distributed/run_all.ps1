# run_all.ps1 — Chạy tất cả service bằng Start-Process (chạy nền với log file riêng)
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " KHỞI ĐỘNG HỆ THỐNG KHO PHÂN TÁN (START-PROCESS TRỰC TIẾP)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

Set-Location "D:\QLKDCN\warehouse-distributed"
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# 1. Kho HN
$env:WAREHOUSE_NAME="HN"; $env:PORT="5001"
Start-Process python -ArgumentList "warehouse/server.py" -RedirectStandardOutput "logs/hn.out.log" -RedirectStandardError "logs/hn.err.log" -NoNewWindow

# 2. Kho DN
$env:WAREHOUSE_NAME="DN"; $env:PORT="5002"
Start-Process python -ArgumentList "warehouse/server.py" -RedirectStandardOutput "logs/dn.out.log" -RedirectStandardError "logs/dn.err.log" -NoNewWindow

# 3. Kho SG
$env:WAREHOUSE_NAME="SG"; $env:PORT="5003"
Start-Process python -ArgumentList "warehouse/server.py" -RedirectStandardOutput "logs/sg.out.log" -RedirectStandardError "logs/sg.err.log" -NoNewWindow

# 4. Payment
Start-Process python -ArgumentList "payment/server.py" -RedirectStandardOutput "logs/payment.out.log" -RedirectStandardError "logs/payment.err.log" -NoNewWindow

# 5. Shipping
Start-Process python -ArgumentList "shipping/server.py" -RedirectStandardOutput "logs/shipping.out.log" -RedirectStandardError "logs/shipping.err.log" -NoNewWindow

# 6. Coordinator
Start-Process python -ArgumentList "coordinator/server.py" -RedirectStandardOutput "logs/coordinator.out.log" -RedirectStandardError "logs/coordinator.err.log" -NoNewWindow

# 7. Frontend Dashboard
Start-Process python -ArgumentList "frontend/server.py" -RedirectStandardOutput "logs/frontend.out.log" -RedirectStandardError "logs/frontend.err.log" -NoNewWindow

Start-Sleep -Seconds 3
Write-Host "`n[+] Tất cả 7 dịch vụ đã khởi động." -ForegroundColor Green
Write-Host ">>> MỞ TRÌNH DUYỆT TẠI: http://localhost:8080 <<<" -ForegroundColor Yellow -BackgroundColor Black
