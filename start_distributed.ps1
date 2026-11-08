# start_distributed.ps1
$ports = @(8000, 8001, 8002, 3000)
foreach ($p in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
    if ($conns) {
        $conns | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

# 1. HQ Service (8000)
Write-Host "[1/4] Starting HQ Service (Port 8000)..."
Start-Process -FilePath "cmd.exe" -ArgumentList "/c set PYTHONPATH=D:\QLKDCN\backend && python -m uvicorn hq_service.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory "D:\QLKDCN\backend" -WindowStyle Hidden

# 2. Branch HN (8001)
Write-Host "[2/4] Starting Branch HN Service (Port 8001)..."
Start-Process -FilePath "cmd.exe" -ArgumentList "/c set PYTHONPATH=D:\QLKDCN\backend && set BRANCH_CODE=HN && set PORT=8001 && python -m uvicorn branch_service.main:app --host 0.0.0.0 --port 8001" -WorkingDirectory "D:\QLKDCN\backend" -WindowStyle Hidden

# 3. Branch HCM (8002)
Write-Host "[3/4] Starting Branch HCM Service (Port 8002)..."
Start-Process -FilePath "cmd.exe" -ArgumentList "/c set PYTHONPATH=D:\QLKDCN\backend && set BRANCH_CODE=HCM && set PORT=8002 && python -m uvicorn branch_service.main:app --host 0.0.0.0 --port 8002" -WorkingDirectory "D:\QLKDCN\backend" -WindowStyle Hidden

# 4. Frontend (3000)
Write-Host "[4/4] Starting Frontend Dashboard (Port 3000)..."
Start-Process -FilePath "cmd.exe" -ArgumentList "/c npx.cmd vite --port 3000 --host" -WorkingDirectory "D:\QLKDCN\frontend" -WindowStyle Hidden

Start-Sleep -Seconds 12

Write-Host "Services started:"
Write-Host "Frontend:  http://localhost:3000"
Write-Host "HQ API:    http://localhost:8000/docs"
Write-Host "HN API:    http://localhost:8001/docs"
Write-Host "HCM API:   http://localhost:8002/docs"
