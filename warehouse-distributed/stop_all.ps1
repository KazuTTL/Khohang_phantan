# stop_all.ps1 — Dừng toàn bộ các service
Write-Host "Đang dừng tất cả các tiến trình của hệ thống phân tán..." -ForegroundColor Yellow

# Dừng PowerShell Jobs
Get-Job | Stop-Job -ErrorAction SilentlyContinue
Get-Job | Remove-Job -Force -ErrorAction SilentlyContinue

# Dừng theo cổng mạng (5001-5005, 7000, 8080)
$ports = @(5001, 5002, 5003, 5004, 5005, 7000, 8080)
foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns.OwningProcess | Select-Object -Unique
        foreach ($p in $pids) {
            try {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
                Write-Host "[+] Đã dừng tiến trình PID $p trên Port $port" -ForegroundColor Green
            } catch {}
        }
    }
}

Write-Host "Hoàn tất dừng hệ thống." -ForegroundColor Green
