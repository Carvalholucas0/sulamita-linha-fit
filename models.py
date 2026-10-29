from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254))
    whatsapp = db.Column(db.String(30), nullable=False)
    marketing_consent = db.Column(db.Boolean, nullable=False, default=False)
    answers_json = db.Column(db.Text, nullable=False)
    profile = db.Column(db.String(40), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    sheet_sync = db.relationship(
        "SheetSyncJob",
        back_populates="registration",
        uselist=False,
        cascade="all, delete-orphan",
    )


class SheetSyncJob(db.Model):
    registration_id = db.Column(
        db.Integer,
        db.ForeignKey("registration.id", ondelete="CASCADE"),
        primary_key=True,
    )
    attempt_count = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.String(500))
    synced_at = db.Column(db.DateTime(timezone=True))
    registration = db.relationship("Registration", back_populates="sheet_sync")
