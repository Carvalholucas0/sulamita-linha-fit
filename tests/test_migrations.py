import unittest

from flask import Flask
from models import Lead, MarketingConsentEvent, Registration, db
from migrations import upgrade_legacy_schema
from sqlalchemy import text
from sqlalchemy.pool import StaticPool


class LegacyDatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_ENGINE_OPTIONS={"poolclass": StaticPool},
            SECRET_KEY="test-secret",
        )
        db.init_app(self.app)
        with self.app.app_context():
            engine = db.engine
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE registration (
                            id INTEGER PRIMARY KEY,
                            name VARCHAR(100) NOT NULL,
                            email VARCHAR(254),
                            whatsapp VARCHAR(30) NOT NULL,
                            marketing_consent BOOLEAN NOT NULL,
                            answers_json TEXT NOT NULL,
                            profile VARCHAR(40) NOT NULL,
                            created_at DATETIME NOT NULL
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO registration
                            (id, name, email, whatsapp, marketing_consent, answers_json, profile, created_at)
                        VALUES
                            (1, 'Ana', NULL, '11999999999', 1,
                             '{"moment":"between_tasks","flavor":"classic","choice":"easy","fit_line":"routine"}',
                             'pratica', '2026-10-29 12:00:00')
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO registration
                            (id, name, email, whatsapp, marketing_consent, answers_json, profile, created_at)
                        VALUES
                            (2, 'Ana', NULL, '55 11 99999-9999', 0,
                             '{"moment":"afternoon","flavor":"fresh","choice":"ingredients","fit_line":"balance"}',
                             'equilibrio', '2026-10-30 12:00:00')
                        """
                    )
                )
            db.create_all()
            upgrade_legacy_schema(engine, self.app.logger)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            engine = db.engine
        engine.dispose()

    def test_existing_leads_and_consent_history_are_migrated(self):
        with self.app.app_context():
            self.assertEqual(Lead.query.count(), 1)
            self.assertEqual(Registration.query.count(), 2)
            self.assertEqual(MarketingConsentEvent.query.count(), 2)
            registration = Registration.query.filter_by(id=1).one()
            lead = Lead.query.one()
            declined = Registration.query.filter_by(id=2).one()
            events = sorted(lead.consent_events, key=lambda event: event.id)
            self.assertEqual(registration.lead_id, lead.id)
            self.assertEqual(registration.whatsapp_normalized, "+5511999999999")
            self.assertIn("Entre um compromisso e outro", registration.answer_snapshot_json)
            self.assertIsNone(registration.privacy_notice_accepted_at)
            self.assertIsNone(declined.privacy_notice_accepted_at)
            self.assertTrue(events[0].consented)
            self.assertFalse(events[1].consented)
            self.assertTrue(registration.marketing_consent_at)
            self.assertIsNone(declined.marketing_consent_at)
            self.assertEqual(events[0].text_version, "legacy")
