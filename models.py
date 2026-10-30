from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254))
    whatsapp = db.Column(db.String(30), nullable=False)
    whatsapp_normalized = db.Column(db.String(16))
    neighborhood = db.Column(db.String(160))
    marketing_consent = db.Column(db.Boolean, nullable=False, default=False)
    marketing_consent_at = db.Column(db.DateTime(timezone=True))
    marketing_consent_version = db.Column(db.String(80))
    marketing_consent_decided_at = db.Column(db.DateTime(timezone=True))
    marketing_consent_text_version = db.Column(db.String(80))
    privacy_notice_accepted_at = db.Column(db.DateTime(timezone=True))
    privacy_notice_version = db.Column(db.String(80))
    answers_json = db.Column(db.Text, nullable=False)
    answer_snapshot_json = db.Column(db.Text)
    score_json = db.Column(db.Text)
    frequency = db.Column(db.String(40))
    occasion = db.Column(db.String(40))
    product_interest = db.Column(db.String(40))
    experience_preference = db.Column(db.String(40))
    communication_interest = db.Column(db.String(40))
    campaign_source = db.Column(db.String(160))
    quiz_version = db.Column(db.String(80))
    submission_key = db.Column(db.String(36), unique=True)
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
    lead = db.relationship("Lead", back_populates="registrations")


class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    whatsapp = db.Column(db.String(30), nullable=False)
    whatsapp_normalized = db.Column(db.String(16), nullable=False, unique=True)
    neighborhood = db.Column(db.String(160), nullable=False)
    marketing_consent = db.Column(db.Boolean, nullable=False, default=False)
    marketing_consent_at = db.Column(db.DateTime(timezone=True))
    marketing_consent_version = db.Column(db.String(80))
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    registrations = db.relationship("Registration", back_populates="lead")
    consent_events = db.relationship(
        "MarketingConsentEvent",
        back_populates="lead",
        cascade="all, delete-orphan",
    )


class MarketingConsentEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=False, index=True)
    registration_id = db.Column(
        db.Integer,
        db.ForeignKey("registration.id", ondelete="SET NULL"),
        unique=True,
    )
    consented = db.Column(db.Boolean, nullable=False)
    text_version = db.Column(db.String(80), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    lead = db.relationship("Lead", back_populates="consent_events")


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
