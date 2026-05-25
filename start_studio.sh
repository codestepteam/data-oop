#!/bin/bash

# Port settings
API_PORT=8001
UI_PORT=5173
FALKOR_PORT=6380
FALKOR_HOST="macmini"

echo "=== Data OOP Studio Launcher ==="

# 1. Check if FalkorDB is running
echo "Checking FalkorDB on $FALKOR_HOST:$FALKOR_PORT..."
nc -z $FALKOR_HOST $FALKOR_PORT > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "⚠️  [Warning] FalkorDB does not appear to be running on port $FALKOR_PORT."
  echo "    Ensure it is running via docker-compose (or similar) before using the studio."
else
  echo "✅ FalkorDB is running."
fi

# 2. Start FastAPI Backend
echo "Starting FastAPI backend on port $API_PORT..."
uv run uvicorn server.api:app --host 0.0.0.0 --port $API_PORT --reload &
BACKEND_PID=$!

# 3. Start Vite Frontend
echo "Starting Vite frontend..."
cd ui
npm run dev -- --host 0.0.0.0 --port $UI_PORT &
FRONTEND_PID=$!

# Function to clean up background processes on exit
cleanup() {
  echo -e "\nShutting down Studio..."
  kill $BACKEND_PID 2>/dev/null
  kill $FRONTEND_PID 2>/dev/null
  exit 0
}

# Trap ctrl-c (SIGINT) and exit (SIGTERM)
trap cleanup SIGINT SIGTERM

echo "----------------------------------------"
echo "Data OOP Studio is now launching!"
echo "👉 Backend API: http://$FALKOR_HOST:$API_PORT"
echo "👉 Web Studio:  http://$FALKOR_HOST:$UI_PORT"
echo "Press Ctrl+C to stop all processes."
echo "----------------------------------------"

# Keep the script running to stream logs and wait for processes
wait
