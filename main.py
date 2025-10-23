from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="AI Betting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "online",
        "message": "AI Sports Betting API",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "models_loaded": True
    }

@app.get("/api/today-picks")
def today_picks(sport: str = "NBA"):
    # Mock data for now
    return {
        "success": True,
        "sport": sport,
        "picks": [
            {
                "player": "LeBron James",
                "line": 25.5,
                "recommendation": "OVER",
                "ai_score": 8.5,
                "expected_value": 12.3
            },
            {
                "player": "Stephen Curry", 
                "line": 28.5,
                "recommendation": "OVER",
                "ai_score": 7.8,
                "expected_value": 9.2
            }
        ]
    }

@app.get("/api/predictions/{sport}")
def predictions(sport: str):
    return {
        "success": True,
        "sport": sport,
        "predictions": []
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

4. Click: **"Commit new file"**

✅ **Done with file 3!**

---

## 📸 **VISUAL GUIDE**

After creating all 3 files, your GitHub repo should look like this:
```
ai-betting-backend/
├── README.md          (already there)
├── requirements.txt   ← FILE 1 (you created)
├── Procfile          ← FILE 2 (you created)
└── main.py           ← FILE 3 (you created) - THE STARTER CODE
