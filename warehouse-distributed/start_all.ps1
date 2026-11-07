# start_all.ps1 — Chạy tất cả 6 service phân tán và Dashboard FE dưới nền PowerShell Jobs

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " KHỞI ĐỘNG HỆ THỐNG QUẢN LÝ KHO PHÂN TÁN (DISTRIBUTED WMS)" -ForegroundColor Cyan
Write-Host " Tuân thủ: Chương 8 Chịu Lỗi & Mục 8.3 Giao Tiếp Tin Cậy RPC" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# Xóa job cũ (nếu có)
Get-Job | Stop-Job -ErrorAction SilentlyContinue
Get-Job | Remove-Job -Force -ErrorAction SilentlyContinue

# 1. Warehouse HN (5001)
Start-Job -Name "HN" -ScriptBlock {
    Set-Location "D:\QLKDCN\warehouse-distributed"
    $env:WAREHOUSE_NAME="HN"; $env:PORT="5001"
    python warehouse\server.py
}

# 2. Warehouse DN (5002)
Start-Job -Name "DN" -ScriptBlock {
    Set-Location "D:\QLKDCN\warehouse-distributed"
    $env:WAREHOUSE_NAME="DN"; $env:PORT="5002"
    python warehouse\server.py
}

# 3. Warehouse SG (5003)
Start-Job -Name "SG" -ScriptBlock {
    Set-Location "D:\QLKDCN\warehouse-distributed"
    $env:WAREHOUSE_NAME="SG"; $env:PORT="5003"
    python warehouse\server.py
}

# 4. Payment Service (5004)
Start-Job -Name "Payment" -ScriptBlock {
    Set-Location "D:\QLKDCN\warehouse-distributed"
    python payment\server.py
}

# 5. Shipping Service (5005)
Start-Job -Name "Shipping" -ScriptBlock {
    Set-Location "D:\QLKDCN\warehouse-distributed"
    python shipping\server.py
}

# 6. Transaction Coordinator (7000)
Start-Job -Name "Coordinator" -ScriptBlock {
    Set-Location "D:\QLKDCN\warehouse-distributed"
    python coordinator\server.py
}

# 7. Frontend Web Dashboard (8080)
Start-Job -Name "Frontend" -ScriptBlock {
    Set-Location "D:\QLKDCN\warehouse-distributed"
    python frontend\server.py
}

Start-Sleep -Seconds 4

Write-Host "`n[+] Danh sách tiến trình đã khởi động:" -ForegroundColor Green
Get-Job | Format-Table -AutoSize

Write-Host "`n>>> GIAO DIỆN WEB DASHBOARD: http://localhost:8080 <<<" -ForegroundColor Yellow -BackgroundColor Black
Write-Host "Coordinator API:             http://localhost:7000" -ForegroundColor Gray
Write-Host "Để xem trạng thái:           Get-Job" -ForegroundColor Gray
Write-Host "Để xem log của 1 job:        Receive-Job -Name <jobName> -Keep" -ForegroundColor Gray
Write-Host "Để dừng tất cả:              Get-Job | Stop-Job; Get-Job | Remove-Job" -ForegroundColor Gray
