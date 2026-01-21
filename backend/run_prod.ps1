param(
  [string]$ListenHost = "0.0.0.0",
  [int]$Port = 8000,
  [int]$Workers = 2,
  [string]$LogLevel = "info"
)

$env:SIM_LOG_LEVEL = $LogLevel
python -m uvicorn app.main:app --host $ListenHost --port $Port --workers $Workers --log-level $LogLevel
