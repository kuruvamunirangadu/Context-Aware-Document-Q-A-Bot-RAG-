#!/bin/bash

# Start the FastAPI backend server

echo "Installing dependencies..."
pip install -r backend/requirements.txt

echo ""
echo "========================================"
echo "Backend server starting on port 8000"
echo "========================================"
echo ""

uvicorn backend.app:app --reload --port 8000
