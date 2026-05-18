#!/bin/sh
# Wrapper to select PORT from possible Render env vars and start uvicorn
# Prefers $PORT, then $PORTS, then defaults to 8000
if [ -n "$PORT" ]; then
  PORT_TO_USE="$PORT"
elif [ -n "$PORTS" ]; then
  PORT_TO_USE="$PORTS"
else
  PORT_TO_USE="8000"
fi

exec uvicorn backend.app:app --host 0.0.0.0 --port "$PORT_TO_USE"
