param(
  [string]$ListenHost = "0.0.0.0",
  [int]$Port = 8000,
  [string]$LogLevel = "info"
)

$env:SIM_LOG_LEVEL = $LogLevel
python -m uvicorn app.main:app --reload --host $ListenHost --port $Port --log-level $LogLevel
