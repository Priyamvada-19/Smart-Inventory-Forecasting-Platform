#!/bin/sh
set -e

echo "Waiting for MySQL to accept connections..."
python - <<'EOF'
import time
import pymysql
from app.config import settings
from urllib.parse import urlparse

url = urlparse(settings.database_url.replace("mysql+pymysql://", "mysql://"))
for attempt in range(30):
    try:
        conn = pymysql.connect(
            host=url.hostname, port=url.port or 3306,
            user=url.username, password=url.password,
            database=url.path.lstrip("/"),
        )
        conn.close()
        print("MySQL is ready.")
        break
    except Exception as e:
        print(f"  attempt {attempt+1}/30: {e}")
        time.sleep(2)
else:
    raise SystemExit("MySQL never became ready")
EOF

if [ "$SEED_ON_STARTUP" = "true" ]; then
  echo "Running init_db.py (seed + train)..."
  python init_db.py
fi

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
