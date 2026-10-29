import base64
import unittest
from unittest.mock import patch

from app import create_app
from models import Registration, SheetSyncJob, db
from quiz import QUESTIONS
from sheets import SheetSyncError


class SulamitaAppTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SECRET_KEY": "test-secret",
                "ADMIN_USER": "test-admin",
                "ADMIN_PASSWORD": "test-password",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def valid_payload(self):
        return {
            "name": "Ana",
            "whatsapp": "11999999999",
            "email": "",
            "consent": True,
            "marketing_consent": False,
            "answers": {
                question["id"]: question["options"][0]["id"] for question in QUESTIONS
            },
        }

    def test_submission_persists_registration_and_returns_profile(self):
        response = self.client.post("/api/submit", json=self.valid_payload())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        with self.app.app_context():
            registration = Registration.query.one()
            self.assertEqual(registration.name, "Ana")
            self.assertFalse(registration.marketing_consent)
            self.assertEqual(registration.profile, "pratica")
            self.assertEqual(SheetSyncJob.query.one().registration_id, registration.id)

    def test_submission_is_saved_when_sheet_sync_fails_and_admin_retries(self):
        self.app.config.update(
            SHEETS_SERVICE_ACCOUNT_JSON="{}",
            SHEETS_SPREADSHEET_ID="test-sheet",
        )
        with patch("app.sync_registration", side_effect=SheetSyncError("temporary outage")):
            response = self.client.post("/api/submit", json=self.valid_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["sheet_backup"], "pending")
        with self.app.app_context():
            registration = Registration.query.one()
            job = SheetSyncJob.query.one()
            self.assertEqual(registration.name, "Ana")
            self.assertIsNone(job.synced_at)
            self.assertEqual(job.attempt_count, 1)

        credentials = base64.b64encode(b"test-admin:test-password").decode()
        with patch("app.sync_registration") as sync:
            response = self.client.get(
                "/admin",
                headers={"Authorization": f"Basic {credentials}"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Planilha sincronizada", response.get_data(as_text=True))
        sync.assert_called_once()
        with self.app.app_context():
            job = SheetSyncJob.query.one()
            self.assertIsNotNone(job.synced_at)
            self.assertEqual(job.attempt_count, 2)

    def test_production_submission_queues_sheet_sync_without_waiting(self):
        self.app.testing = False
        self.app.config.update(
            SHEETS_SERVICE_ACCOUNT_JSON="{}",
            SHEETS_SPREADSHEET_ID="test-sheet",
        )
        with patch("app.ThreadPoolExecutor.submit") as submit:
            response = self.client.post("/api/submit", json=self.valid_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["sheet_backup"], "pending")
        submit.assert_called_once()
        with self.app.app_context():
            self.assertEqual(Registration.query.count(), 1)
            self.assertIsNone(SheetSyncJob.query.one().synced_at)

    def test_submission_requires_consent_and_every_answer(self):
        payload = self.valid_payload()
        payload["consent"] = False
        self.assertEqual(self.client.post("/api/submit", json=payload).status_code, 400)

        payload = self.valid_payload()
        payload["answers"].pop(QUESTIONS[0]["id"])
        self.assertEqual(self.client.post("/api/submit", json=payload).status_code, 400)

        payload = self.valid_payload()
        payload["answers"][QUESTIONS[0]["id"]] = []
        self.assertEqual(self.client.post("/api/submit", json=payload).status_code, 400)

    def test_admin_and_csv_require_authentication(self):
        self.assertEqual(self.client.get("/admin").status_code, 401)

        credentials = base64.b64encode(b"test-admin:test-password").decode()
        response = self.client.get(
            "/admin/export.csv",
            headers={"Authorization": f"Basic {credentials}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)

    def test_landing_page_renders(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Linha Fit", response.get_data(as_text=True))
