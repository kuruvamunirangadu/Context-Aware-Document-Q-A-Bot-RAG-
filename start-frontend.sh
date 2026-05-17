#!/bin/bash

# Start the React frontend with Vite

echo "Navigating to frontend folder..."
cd frontend

echo "Installing dependencies..."
npm install

echo ""
echo "========================================"
echo "Frontend dev server starting on port 5173"
echo "========================================"
echo ""

npm run dev
