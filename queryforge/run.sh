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

# 3. Detect correct Python 3.10+ interpreter (since PEP 604 'str | None' union syntax is used)
PYTHON_CMD="python3"
if [ -f "/opt/homebrew/opt/python@3.10/bin/python3.10" ]; then
  PYTHON_CMD="/opt/homebrew/opt/python@3.10/bin/python3.10"
elif command -v python3.10 &> /dev/null; then
  PYTHON_CMD="python3.10"
fi

echo "Using Python interpreter: $PYTHON_CMD"

# 4. Start the FastAPI server
echo "Launching QueryForge API & Frontend UI on http://localhost:${PORT}/ ..."
$PYTHON_CMD -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT} --reload
