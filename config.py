import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _database_url():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    if os.environ.get("RENDER"):
        raise RuntimeError("Configure DATABASE_URL with a persistent PostgreSQL database on Render.")

    instance_path = Path(__file__).resolve().parent / "instance"
    instance_path.mkdir(exist_ok=True)
    return f"sqlite:///{(instance_path / 'sulamita.db').as_posix()}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-only-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    ADMIN_USER = os.environ.get("ADMIN_USER", "sulamita")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    SHEETS_SERVICE_ACCOUNT_JSON = os.environ.get("SHEETS_SERVICE_ACCOUNT_JSON")
    SHEETS_SPREADSHEET_ID = os.environ.get("SHEETS_SPREADSHEET_ID")
