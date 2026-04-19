"""
app を import する前にテスト用 SQLite と認証 OFF を固定する。
"""

from __future__ import annotations

import os
import tempfile

# app.config / app.db の import より先に実行される必要がある
_fd, _TEST_DB_FILE = tempfile.mkstemp(prefix="webclip_test_", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_FILE}"
os.environ["WEBCLIP_BEARER_AUTH_ENABLED"] = "false"
