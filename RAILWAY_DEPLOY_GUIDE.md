# 🚀 Railway Deployment Guide - AI Sports Betting API

## Quick Deploy (5-10 minutes)

### Step 1: Create GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Repository name: `ai-betting-api` (or your choice)
3. Make it **Private** (recommended)
4. Click **Create repository**

### Step 2: Upload Files

Upload these files to your new repository:

**Required (Core Application):**
- `prediction_api.py` - Main API server
- `advanced_ml_backend.py` - 8 AI models + 8 pillars
- `requirements.txt` - Python dependencies
- `Procfile` - Railway start command
- `railway.toml` - Railway configuration
- `runtime.txt` - Python version
- `nixpacks.toml` - Build configuration

**Optional (Documentation):**
- `README.md` - Project documentation
- `.gitignore` - Git ignore rules
- `.python-version` - Python version hint

### Step 3: Deploy to Railway

1. Go to [railway.app](https://railway.app)
2. Sign in with GitHub
3. Click **New Project**
4. Select **Deploy from GitHub repo**
5. Choose your `ai-betting-api` repository
6. Railway will auto-detect Python and start building

### Step 4: Configure Environment

In Railway dashboard → Your project → Variables tab:

```
PYTHON_VERSION=3.12
```

(PORT is automatically set by Railway)

### Step 5: Generate Public URL

1. Go to **Settings** tab
2. Under **Networking**, click **Generate Domain**
3. You'll get a URL like: `ai-betting-api-production.up.railway.app`

### Step 6: Verify Deployment

Test these endpoints:

```bash
# Health check
curl https://YOUR-URL.railway.app/health

# Model status
curl https://YOUR-URL.railway.app/model-status

# API docs
# Visit: https://YOUR-URL.railway.app/docs
```

---

## Expected Build Output

```
==> Installing dependencies
==> pip install -r requirements.txt
    Installing: fastapi, uvicorn, pydantic...
    Installing: numpy, pandas, scipy...
    Installing: scikit-learn, xgboost, lightgbm...
==> Build completed successfully
==> Deploying...
==> Starting: python prediction_api.py
🚀 Starting AI Sports Betting API
📊 8 Advanced AI Models Loaded
📡 Server starting on http://0.0.0.0:XXXX
```

Build time: ~3-5 minutes (ML libraries take time)

---

## Troubleshooting

### Build Fails with Memory Error
- Railway free tier has limited memory
- Upgrade to Hobby plan ($5/month) for reliable builds

### Python Version Error
- Ensure `runtime.txt` contains `python-3.12.3`
- Or set `PYTHON_VERSION=3.12` in Railway variables

### Import Errors
- Check all files are uploaded to GitHub
- Verify `advanced_ml_backend.py` is in same directory as `prediction_api.py`

### Port Connection Issues
- Railway automatically assigns PORT
- Code already handles this with `os.getenv("PORT", 8000)`

---

## API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info & health |
| `/health` | GET | Health check |
| `/model-status` | GET | Status of all 8 models |
| `/predict` | POST | Full prediction with pillars |
| `/simulate-game` | POST | Monte Carlo simulation |
| `/analyze-line` | POST | Line movement analysis |
| `/calculate-edge` | POST | EV & Kelly sizing |
| `/docs` | GET | Interactive API docs |

---

## Test Prediction

```bash
curl -X POST "https://YOUR-URL.railway.app/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "lebron_james",
    "opponent_id": "gsw",
    "features": [25.4, 7.2, 6.8, 1, 35, 28, 2],
    "recent_games": [27, 31, 22, 28, 25, 30, 26, 24, 29, 32],
    "player_stats": {
        "stat_type": "points",
        "expected_value": 27.5,
        "variance": 45.0,
        "std_dev": 6.5
    },
    "schedule": {
        "days_rest": 1,
        "travel_miles": 1500,
        "games_in_last_7": 3
    },
    "injuries": [],
    "depth_chart": {},
    "game_id": "lal_gsw_20250114",
    "current_line": 25.5,
    "opening_line": 26.0,
    "time_until_game": 6.0,
    "betting_percentages": {"public_on_favorite": 68.0},
    "betting_odds": -110,
    "line": 25.5
  }'
```

---

## Success Checklist

- [ ] Railway shows "Active" deployment
- [ ] `/health` returns `{"status": "healthy"}`
- [ ] `/model-status` shows all 8 models "ready"
- [ ] `/docs` opens interactive documentation
- [ ] `/predict` returns predictions with pillar analysis

---

## Estimated Costs

| Plan | Cost | Memory | Suitable For |
|------|------|--------|--------------|
| Free Trial | $0 | 512MB | Testing only |
| Hobby | $5/mo | 8GB | Production use |

The Hobby plan is recommended for reliable ML model deployment.

---

**Your AI Sports Betting API is ready!** 🏀🎯
