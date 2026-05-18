#!/bin/bash
set -e  # Exit on any error

echo "===== Testing Backend Build ====="
cd backend
pip install -r requirements.txt
echo "Backend dependencies installed successfully"
cd ..

echo "===== Testing Frontend Build ====="
cd frontend
npm ci
npm run build
echo "Frontend built successfully"
cd ..

echo "===== Build test complete ====="
