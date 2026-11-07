# stop_distributed.ps1
Write-Host "Đang dừng tất cả các dịch vụ phân tán trên cổng 8000, 8001, 8002, 3000..." -ForegroundColor Yellow

$ports = @(8000, 8001, 8002, 3000)
foreach ($p in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
    if ($conns) {
        $conns | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "Đã dừng tiến trình chiếm cổng $p" -ForegroundColor Gray
        }
    }
}
Write-Host "Toàn bộ hệ thống đã được dừng!" -ForegroundColor Green
