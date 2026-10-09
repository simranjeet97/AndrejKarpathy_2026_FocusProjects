#!/bin/bash

# Port to run the application on
PORT=8000

echo "=== QueryForge Command Deck Launch Sequence ==="

# 1. Free the port 8000
echo "Checking port ${PORT}..."
PID=$(lsof -t -i:${PORT})

if [ ! -z "$PID" ]; then
  echo "Port ${PORT} is occupied by process $PID. Freeing port..."
  kill -9 $PID
  sleep 1
  echo "Port ${PORT} has been freed."
else
  echo "Port ${PORT} is already free."
fi

# 2. Initialize database if missing
if [ ! -f "queryforge.db" ]; then
  echo "Initializing local SQLite database queryforge.db..."
  sqlite3 queryforge.db < scripts/init_db.sql
  echo "Database initialized successfully."
fi

# 3. Detect Python interpreter (.venv preferred, then 3.11+)
if [ -f ".venv/bin/python" ]; then
  PYTHON_CMD=".venv/bin/python"
elif [ -f "/opt/homebrew/opt/python@3.10/bin/python3.10" ]; then
  PYTHON_CMD="/opt/homebrew/opt/python@3.10/bin/python3.10"
else
  for ver in python3.13 python3.12 python3.11 python3; do
    if command -v "$ver" &> /dev/null; then
      PYTHON_CMD="$ver"
      break
    fi
  done
fi

echo "Using Python interpreter: $PYTHON_CMD"

# 4. Start the FastAPI server
echo "Launching QueryForge API & Frontend UI on http://localhost:${PORT}/ ..."
$PYTHON_CMD -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT} --reload
