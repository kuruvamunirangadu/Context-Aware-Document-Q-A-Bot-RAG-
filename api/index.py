import os
import sys
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Ensure backend directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create app at module level so Vercel can find it
app = FastAPI()

# Try to import and mount the actual backend app
try:
    from backend.app import app as backend_app
    # Copy all routes from backend app
    app.router.routes.extend(backend_app.router.routes)
    app.user_middleware.extend(backend_app.user_middleware)
except Exception as e:
    # If backend import fails, add error endpoint
    error_msg = f"Backend initialization failed: {str(e)}"
    
    @app.get("/")
    def health():
        return JSONResponse(
            {"error": "Backend initialization failed", "details": str(e)},
            status_code=500
        )
    
    @app.get("/health")
    def health_check():
        return JSONResponse(
            {"status": "error", "details": error_msg},
            status_code=500
        )

# Vercel handler (alternative export name)
handler = app


