import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import gspread
from google.oauth2.service_account import Credentials

from quiz import PROFILES, QUESTIONS
from sheets import HEADERS, SheetSyncError, registration_values, sync_registration


class GoogleSheetsSyncTests(unittest.TestCase):
    def test_registration_values_preserve_all_quiz_answers(self):
        registration = SimpleNamespace(
            id=3,
            name="Ana",
            email=None,
            whatsapp="11999999999",
            marketing_consent=False,
            answers_json=json.dumps(
                {question["id"]: question["options"][0]["id"] for question in QUESTIONS}
            ),
            profile="pratica",
            created_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
        )

        row = registration_values(registration, PROFILES, QUESTIONS)

        self.assertEqual(len(row), len(HEADERS))
        self.assertEqual(row[0], 3)
        self.assertEqual(row[1], "Ana")
        self.assertEqual(row[2], "")
        self.assertIn(QUESTIONS[0]["options"][0]["text"], row[5])
        self.assertEqual(row[7], "Não")

    def test_sync_writes_to_stable_row_as_raw_values(self):
        registration = SimpleNamespace(
            id=4,
            name="=not a formula",
            email=None,
            whatsapp="11999999999",
            marketing_consent=False,
            answers_json=json.dumps(
                {question["id"]: question["options"][0]["id"] for question in QUESTIONS}
            ),
            profile="pratica",
            created_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
        )
        client = patch("gspread.authorize").start()
        self.addCleanup(patch.stopall)
        spreadsheet = client.return_value.open_by_key.return_value
        worksheet = spreadsheet.worksheet.return_value
        worksheet.get.return_value = [HEADERS]
        worksheet.row_count = 100

        with patch.object(Credentials, "from_service_account_info") as credentials:
            sync_registration(
                registration,
                PROFILES,
                QUESTIONS,
                {
                    "SHEETS_SERVICE_ACCOUNT_JSON": "{}",
                    "SHEETS_SPREADSHEET_ID": "spreadsheet-id",
                },
            )

        credentials.assert_called_once()
        client.return_value.set_timeout.assert_called_once_with((5, 15))
        worksheet.update.assert_called_once()
        args, kwargs = worksheet.update.call_args
        self.assertEqual(args[0], "A5:I5")
        self.assertEqual(kwargs["value_input_option"], "RAW")
        self.assertEqual(args[1][0][1], "=not a formula")

    def test_sync_rejects_an_unexpected_header(self):
        client = patch("gspread.authorize").start()
        self.addCleanup(patch.stopall)
        worksheet = client.return_value.open_by_key.return_value.worksheet.return_value
        worksheet.get.return_value = [["Existing data"]]
        worksheet.row_count = 100
        registration = SimpleNamespace(id=1)

        with patch.object(Credentials, "from_service_account_info"):
            with self.assertRaisesRegex(SheetSyncError, "cabeçalhos"):
                sync_registration(
                    registration,
                    PROFILES,
                    QUESTIONS,
                    {
                        "SHEETS_SERVICE_ACCOUNT_JSON": "{}",
                        "SHEETS_SPREADSHEET_ID": "spreadsheet-id",
                    },
                )
