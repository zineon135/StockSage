import os
import sys
from pathlib import Path

# Isolated in-memory-ish test database and no real API keys.
_TEST_DB = Path(__file__).parent / "_test.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("FINNHUB_API_KEY", "")
os.environ.setdefault("NEWSAPI_KEY", "")
os.environ.setdefault("GEMINI_API_KEY", "")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
