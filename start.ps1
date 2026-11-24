# MemoryMate: start everything with one command.
#   In VS Code's terminal, in the memorymate-app folder, run:   .\start.ps1
# It starts the database (Docker), then opens two windows: the backend and the mobile app server.
# Close those two windows to stop.

$root = $PSScriptRoot

Write-Host ""
Write-Host "1/3  Starting the database (Docker)..." -ForegroundColor Cyan
docker compose -f "$root\docker-compose.yml" up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Docker isn't running. Open Docker Desktop, wait until it says 'Engine running', then run .\start.ps1 again." -ForegroundColor Red
    exit 1
}

Write-Host "2/3  Opening the backend window (FastAPI on port 8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = 'MemoryMate backend'; Set-Location '$root\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 0.0.0.0"

if (Test-Path "$root\mobile\package.json") {
    Write-Host "3/3  Opening the mobile app window (Expo)..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = 'MemoryMate mobile (Expo)'; Set-Location '$root\mobile'; npx expo start"
} else {
    Write-Host "3/3  No mobile folder yet: skipping Expo." -ForegroundColor Yellow
}

# The laptop's address on the current Wi-Fi (the network that has internet).
$ip = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Select-Object -First 1).IPv4Address.IPAddress

Write-Host ""
Write-Host "  MemoryMate is starting. Give it about 10 seconds." -ForegroundColor Green
Write-Host "  Phone:  open Expo Go and tap MemoryMate (or scan the QR code in the Expo window)."
Write-Host "          The app fills in the server address by itself: $($ip):8000"
Write-Host "  Laptop: test page at http://localhost:8000/test"
Write-Host ""
Write-Host "  To stop: close the two new windows. (Database too: docker compose down)"
Write-Host ""
