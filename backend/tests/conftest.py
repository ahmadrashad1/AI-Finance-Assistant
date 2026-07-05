import os

# Default test environment so importing `app.*` modules never fails for lack of
# required settings. Individual tests override via monkeypatch where relevant.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test"
)
os.environ.setdefault("LOG_LEVEL", "INFO")
