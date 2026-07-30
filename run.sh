#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install -q -r requirements.txt
echo "Treasury Income Screener: http://127.0.0.1:8000"
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
