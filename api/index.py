import os
import sys
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Ensure backend directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create a minimal app that Vercel can recognize
app = FastAPI()

# Try to import the actual backend app and use it directly
try:
    from backend.app import app as backend_app
    # Replace the module-level app with the actual backend app
    # This preserves all routes and middleware
    app = backend_app
    
except Exception as e:
    import traceback
    error_traceback = traceback.format_exc()
    error_msg = f"Backend initialization failed: {str(e)}"
    
    # If import fails, provide error diagnostics
    @app.get("/")
    def health():
        return JSONResponse(
            {
                "status": "error",
                "message": error_msg,
                "details": error_traceback
            },
            status_code=500
        )
    
    @app.get("/health")
    def health_check():
        return JSONResponse(
            {
                "status": "error", 
                "message": error_msg
            },
            status_code=500
        )

# Vercel handler
handler = app

