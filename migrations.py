import json

from sqlalchemy import inspect, text

from leads import normalize_whatsapp
from models import Lead, MarketingConsentEvent, Registration, db

LEGACY_QUESTIONS = {
    "moment": (
        "Em que momento uma pausa gostosa faria diferença no seu dia?",
        {
            "between_tasks": "Entre um compromisso e outro",
            "afternoon": "Na pausa tranquila da tarde",
            "after_movement": "Depois de um dia em movimento",
            "with_people": "Quando estou reunindo gente querida",
        },
    ),
    "flavor": (
        "Qual clima de sabor combina mais com você?",
        {
            "classic": "Clássico e sem erro",
            "fresh": "Leve e cheio de frescor",
            "comfort": "Aconchegante e bem cremoso",
            "surprise": "Uma combinação que surpreende",
        },
    ),
    "choice": (
        "Na hora de escolher uma empada ou quiche, o que pesa mais?",
        {
            "easy": "Ser prática para levar comigo",
            "ingredients": "Ingredientes que parecem de verdade",
            "comfort_food": "Aquela sensação de comida feita com carinho",
            "new": "Experimentar algo que ainda não provei",
        },
    ),
    "fit_line": (
        "O que você mais quer descobrir na Linha Fit da Sulamita?",
        {
            "routine": "Uma opção gostosa para a rotina",
            "balance": "Mais equilíbrio sem abrir mão do sabor",
            "pleasure": "Uma pausa leve que continua sendo prazerosa",
            "novelty": "Novos sabores para sair do óbvio",
        },
    ),
}


REGISTRATION_COLUMNS = {
    "lead_id": "INTEGER REFERENCES lead (id)",
    "whatsapp_normalized": "VARCHAR(16)",
    "neighborhood": "VARCHAR(160)",
    "marketing_consent_at": "TIMESTAMP",
    "marketing_consent_version": "VARCHAR(80)",
    "marketing_consent_decided_at": "TIMESTAMP",
    "marketing_consent_text_version": "VARCHAR(80)",
    "privacy_notice_accepted_at": "TIMESTAMP",
    "privacy_notice_version": "VARCHAR(80)",
    "answer_snapshot_json": "TEXT",
    "score_json": "TEXT",
    "frequency": "VARCHAR(40)",
    "occasion": "VARCHAR(40)",
    "product_interest": "VARCHAR(40)",
    "experience_preference": "VARCHAR(40)",
    "communication_interest": "VARCHAR(40)",
    "campaign_source": "VARCHAR(160)",
    "quiz_version": "VARCHAR(80)",
    "submission_key": "VARCHAR(36)",
}


def upgrade_legacy_schema(engine, logger):
    if "registration" not in inspect(engine).get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspect(engine).get_columns("registration")
    }
    with engine.begin() as connection:
        for column_name, column_type in REGISTRATION_COLUMNS.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE registration ADD COLUMN "
                        f"{column_name} {column_type}"
                    )
                )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_registration_submission_key "
                "ON registration (submission_key)"
            )
        )

    registrations = Registration.query.order_by(Registration.id.asc()).all()
    leads_by_whatsapp = {}
    for registration in registrations:
        normalized = normalize_whatsapp(registration.whatsapp)
        if not normalized:
            logger.warning(
                "Skipping legacy lead link for registration %s: invalid WhatsApp format.",
                registration.id,
            )
            continue

        lead = leads_by_whatsapp.get(normalized)
        if lead is None:
            lead = Lead.query.filter_by(whatsapp_normalized=normalized).one_or_none()
            if lead is None:
                lead = Lead(
                    name=registration.name,
                    whatsapp=registration.whatsapp,
                    whatsapp_normalized=normalized,
                    neighborhood="Não informado (cadastro legado)",
                    marketing_consent=registration.marketing_consent,
                    marketing_consent_at=registration.created_at
                    if registration.marketing_consent
                    else None,
                    marketing_consent_version="legacy"
                    if registration.marketing_consent
                    else None,
                )
                db.session.add(lead)
                db.session.flush()
            leads_by_whatsapp[normalized] = lead
        else:
            lead.name = registration.name
            lead.whatsapp = registration.whatsapp
            lead.marketing_consent = registration.marketing_consent
            lead.marketing_consent_at = (
                registration.created_at if registration.marketing_consent else None
            )
            lead.marketing_consent_version = (
                "legacy" if registration.marketing_consent else None
            )

        registration.lead_id = lead.id
        registration.whatsapp_normalized = normalized
        if registration.marketing_consent and not registration.marketing_consent_at:
            registration.marketing_consent_at = registration.created_at
            registration.marketing_consent_version = "legacy"
        if not registration.marketing_consent_decided_at:
            registration.marketing_consent_decided_at = registration.created_at
            registration.marketing_consent_text_version = "legacy"
        if not registration.answer_snapshot_json:
            legacy_answers = json.loads(registration.answers_json)
            registration.answer_snapshot_json = json.dumps(
                {
                    question_id: {
                        "question": LEGACY_QUESTIONS[question_id][0],
                        "answer_id": answer_id,
                        "answer": LEGACY_QUESTIONS[question_id][1].get(
                            answer_id, answer_id
                        ),
                    }
                    for question_id, answer_id in legacy_answers.items()
                },
                ensure_ascii=False,
            )
        if not registration.campaign_source:
            registration.campaign_source = "Cadastro legado"
        if not registration.quiz_version:
            registration.quiz_version = "legacy"

        existing_event = MarketingConsentEvent.query.filter_by(
            registration_id=registration.id
        ).one_or_none()
        if existing_event is None:
            db.session.add(
                MarketingConsentEvent(
                    lead_id=lead.id,
                    registration_id=registration.id,
                    consented=registration.marketing_consent,
                    text_version="legacy",
                    created_at=registration.created_at,
                )
            )

    db.session.commit()
