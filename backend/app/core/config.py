import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "quant_research.sqlite3"
APP_NAME = "个人量化决策研究系统 API"
DISCLAIMER = "本系统仅用于个人量化研究和投资复盘，不构成任何投资建议。投资有风险，决策需谨慎。"
CORS_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3002",
    "http://localhost:3000",
    "http://localhost:3002",
]
CORS_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1):\d+$"
MARKET_DATA_SOURCE = os.getenv("MARKET_DATA_SOURCE", "akshare")
AKSHARE_STOCK_SCOPE = os.getenv("AKSHARE_STOCK_SCOPE", "tracked")
AKSHARE_HISTORY_DAYS = int(os.getenv("AKSHARE_HISTORY_DAYS", "250"))
AKSHARE_ADJUST = os.getenv("AKSHARE_ADJUST", "qfq")
AKSHARE_SYNC_INDUSTRY = os.getenv("AKSHARE_SYNC_INDUSTRY", "false").lower() in {"1", "true", "yes"}
CRON_SECRET = os.getenv("CRON_SECRET", "")
JOB_TIMEZONE = os.getenv("JOB_TIMEZONE", "Asia/Shanghai")
AUTO_SCHEDULER_ENABLED = os.getenv("AUTO_SCHEDULER_ENABLED", "true").lower() in {"1", "true", "yes"}
JOB_STALE_MINUTES = int(os.getenv("JOB_STALE_MINUTES", "120"))
