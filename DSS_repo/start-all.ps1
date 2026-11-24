# Chạy toàn bộ dự án: MySQL + Neo4j (Docker), dịch vụ model, API và web.
# Dùng:  .\start-all.ps1            (cần Docker Desktop đang chạy)
#        .\start-all.ps1 -NoDocker  (không cần Docker: API đọc thẳng CSV, không có đồ thị tri thức)
param([switch]$NoDocker)

Set-Location $PSScriptRoot
$api = 'dev:api'

if ($NoDocker) {
  $api = 'dev:api:memory'
} else {
  docker compose up -d --wait
  if ($LASTEXITCODE -ne 0) {
    Write-Host 'Docker chưa sẵn sàng. Mở Docker Desktop rồi chạy lại, hoặc dùng: .\start-all.ps1 -NoDocker' -ForegroundColor Red
    exit 1
  }
}

function Start-Window($title, $command) {
  Start-Process powershell -WorkingDirectory $PSScriptRoot -ArgumentList '-NoExit', '-Command', "`$host.UI.RawUI.WindowTitle = '$title'; $command"
}

Start-Window 'DSS - Model (8000)' 'python -m uvicorn ml.serve:app --host 127.0.0.1 --port 8000'
Start-Window 'DSS - API (4000)' "npm.cmd run $api"
Start-Window 'DSS - Web (3000)' 'npm.cmd run dev:fe'

Write-Host 'Đang khởi động 3 cửa sổ. Sau khoảng 30 giây mở http://localhost:3000' -ForegroundColor Green
Write-Host 'Dừng: đóng 3 cửa sổ đó; tắt cơ sở dữ liệu bằng: docker compose down'
