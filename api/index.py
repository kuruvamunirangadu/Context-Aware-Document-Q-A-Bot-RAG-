import os
import sys

# Ensure backend directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.app import app
except Exception as e:
    # If backend import fails, create a minimal app to show the error
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI()
    
    @app.get("/")
    def health():
        return JSONResponse(
            {"error": "Backend initialization failed", "details": str(e)},
            status_code=500
        )

# Vercel serverless handler
handler = app

