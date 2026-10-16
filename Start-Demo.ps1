$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
$localDirectory = Join-Path $projectPath '.local'
$demoUrl = 'http://127.0.0.1:8765'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'The project environment is missing. Follow README.md to install it first.'
}
try {
    $health = Invoke-RestMethod -Uri "$demoUrl/api/status" -TimeoutSec 3
    if ($health.lectures) {
        Write-Host "RAG YT RIVISION is already running: $demoUrl"
        exit 0
    }
} catch { }
New-Item -ItemType Directory -Path $localDirectory -Force | Out-Null
$process = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', '8765') -WorkingDirectory $projectPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $localDirectory 'server.stdout.log') -RedirectStandardError (Join-Path $localDirectory 'server.stderr.log') -PassThru
$process.Id | Set-Content -LiteralPath (Join-Path $localDirectory 'server.pid')
Write-Host "Starting RAG YT RIVISION: $demoUrl"
Write-Host 'The first request may take a few seconds while the search model loads.'
