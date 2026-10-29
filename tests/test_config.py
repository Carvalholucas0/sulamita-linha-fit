import os
import unittest
from unittest.mock import patch

from config import _database_url


class DatabaseUrlTests(unittest.TestCase):
    def test_postgres_url_uses_installed_psycopg2_driver(self):
        for prefix in ("postgres://", "postgresql://"):
            with self.subTest(prefix=prefix):
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": f"{prefix}user:password@host/database"},
                ):
                    self.assertEqual(
                        _database_url(),
                        "postgresql+psycopg2://user:password@host/database",
                    )

    def test_explicit_database_driver_is_preserved(self):
        url = "postgresql+psycopg://user:password@host/database"
        with patch.dict(os.environ, {"DATABASE_URL": url}):
            self.assertEqual(_database_url(), url)

