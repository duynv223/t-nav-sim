# Route Simulation Tool
---

## Quick Start (Native Development)

### Prerequisites
- Python 3.10+
- Node.js 18+
- HERE Maps API Key (free at https://developer.here.com/)

### Backend Setup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will run at: `http://localhost:8000`

### Frontend Setup
```powershell
cd frontend
npm install
# Copy .env.example to .env and add your HERE API key
copy .env.example .env
# Edit .env and set VITE_HERE_API_KEY=your_key_here
npm run dev
```