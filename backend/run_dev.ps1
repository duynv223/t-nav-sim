# Run backend in development mode
$env:SIM_ENABLE_GPS = "1"
$env:SIM_ENABLE_MOTION = "0"
uvicorn app.main:app --host 0.0.0.0 --port 8000
