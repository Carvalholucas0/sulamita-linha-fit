import csv
import io
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, Response, jsonify, render_template, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import Config
from leads import normalize_whatsapp
from migrations import upgrade_legacy_schema
from models import Lead, MarketingConsentEvent, Registration, SheetSyncJob, db
from quiz import (
    ALL_PROFILES,
    CAMPAIGN_SOURCE,
    MARKETING_CONSENT_VERSION,
    QUESTIONS,
    PRIVACY_NOTICE_VERSION,
    PROFILES,
    QUIZ_VERSION,
    build_answer_snapshot,
    build_declared_preferences,
    build_score_snapshot,
    calculate_profile,
    format_preference,
    option_label,
)
from sheets import SheetSyncError, is_configured, sync_registration


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    sheet_sync_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sheets-sync")
    with app.app_context():
        db.create_all()
        upgrade_legacy_schema(db.engine, app.logger)
        registrations_without_job = (
            db.session.query(Registration.id)
            .outerjoin(SheetSyncJob)
            .filter(SheetSyncJob.registration_id.is_(None))
            .all()
        )
        if registrations_without_job:
            db.session.add_all(
                SheetSyncJob(registration_id=registration_id)
                for (registration_id,) in registrations_without_job
            )
            db.session.commit()

    def retry_sheet_sync(limit):
        if not is_configured(app.config):
            return set()

        jobs = (
            SheetSyncJob.query.filter_by(synced_at=None)
            .order_by(SheetSyncJob.registration_id.asc())
            .limit(limit)
            .all()
        )
        if not jobs:
            return set()

        synced_ids = set()
        for job in jobs:
            try:
                sync_registration(job.registration, ALL_PROFILES, QUESTIONS, app.config)
            except SheetSyncError as error:
                job.attempt_count += 1
                job.last_error = str(error)[:500]
                app.logger.error(
                    "Google Sheets sync failed for registration %s (attempt %s): %s",
                    job.registration_id,
                    job.attempt_count,
                    job.last_error,
                )
            else:
                job.attempt_count += 1
                job.last_error = None
                job.synced_at = datetime.now(timezone.utc)
                synced_ids.add(job.registration_id)

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Falha ao salvar o estado de sincronização da planilha.")
            return set()
        return synced_ids

    def dispatch_sheet_sync(limit):
        if not is_configured(app.config):
            return set()
        if app.testing:
            return retry_sheet_sync(limit)

        def sync_in_app_context():
            with app.app_context():
                retry_sheet_sync(limit)

        sheet_sync_executor.submit(sync_in_app_context)
        return set()

    def validated_answers(data):
        answers = data.get("answers")
        question_ids = {question["id"] for question in QUESTIONS}
        if not isinstance(answers, dict) or set(answers) != question_ids:
            return None
        for question in QUESTIONS:
            valid_options = {option["id"] for option in question["options"]}
            if (
                not isinstance(answers[question["id"]], str)
                or answers[question["id"]] not in valid_options
            ):
                return None
        return answers

    def registration_response(registration):
        synced_ids = dispatch_sheet_sync(limit=1)
        response = jsonify(
            success=True,
            profile={"id": registration.profile, **PROFILES[registration.profile]},
            sheet_backup=(
                "synced" if registration.id in synced_ids else
                "pending" if is_configured(app.config) else
                "not_configured"
            ),
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    def require_admin(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            password = app.config.get("ADMIN_PASSWORD")
            if not password:
                return "Área administrativa não configurada.", 503

            auth = request.authorization
            username = auth.username if auth else ""
            supplied_password = (auth.password or "") if auth else ""
            valid_user = secrets.compare_digest(username, app.config["ADMIN_USER"])
            valid_password = secrets.compare_digest(supplied_password, password)
            if not (valid_user and valid_password):
                return Response(
                    "Autenticação necessária.",
                    401,
                    {"WWW-Authenticate": 'Basic realm="Sulamita Admin"'},
                )
            return view(*args, **kwargs)

        return wrapped

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/privacidade")
    def privacy_notice():
        return render_template("privacy.html")

    @app.get("/api/questions")
    def get_questions():
        return jsonify(QUESTIONS)

    @app.post("/api/submit")
    def submit_quiz():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Envie os dados do cadastro em JSON."), 400

        name = data.get("name")
        whatsapp = data.get("whatsapp")
        neighborhood = data.get("neighborhood")
        consent = data.get("data_consent")
        marketing_consent = data.get("marketing_consent", False)
        submission_key = data.get("submission_key")

        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            return jsonify(error="Informe seu primeiro nome.", field="name"), 400
        first_name = name.strip().split()[0]
        if not isinstance(whatsapp, str) or len(whatsapp.strip()) > 30:
            return jsonify(error="Informe um WhatsApp com DDD.", field="whatsapp"), 400
        normalized_whatsapp = normalize_whatsapp(whatsapp)
        if not normalized_whatsapp:
            return jsonify(error="Confira o número e o DDD do WhatsApp.", field="whatsapp"), 400
        if (
            not isinstance(neighborhood, str)
            or not neighborhood.strip()
            or len(neighborhood.strip()) > 160
        ):
            return jsonify(error="Informe seu bairro e cidade.", field="neighborhood"), 400
        if consent is not True:
            return jsonify(
                error="Leia e aceite o aviso para concluir seu cadastro.",
                field="data-consent",
            ), 400
        if not isinstance(marketing_consent, bool):
            return jsonify(
                error="A autorização de novidades é inválida.",
                field="marketing_consent",
            ), 400
        if not isinstance(submission_key, str) or len(submission_key) != 36:
            return jsonify(
                error="Atualize a página e tente novamente.",
                field="submission",
            ), 400
        answers = validated_answers(data)
        if answers is None:
            return jsonify(error="Responda todas as perguntas do quiz."), 400

        existing_registration = Registration.query.filter_by(
            submission_key=submission_key
        ).one_or_none()
        if existing_registration:
            return registration_response(existing_registration)

        profile_id = calculate_profile(answers)
        now = datetime.now(timezone.utc)

        def save_registration(lead=None):
            current_lead = lead or Lead.query.filter_by(
                whatsapp_normalized=normalized_whatsapp
            ).one_or_none()
            if current_lead is None:
                current_lead = Lead(
                    name=first_name,
                    whatsapp=whatsapp.strip(),
                    whatsapp_normalized=normalized_whatsapp,
                    neighborhood=neighborhood.strip(),
                    marketing_consent=marketing_consent,
                    marketing_consent_at=now if marketing_consent else None,
                    marketing_consent_version=(
                        MARKETING_CONSENT_VERSION if marketing_consent else None
                    ),
                )
                db.session.add(current_lead)
                db.session.flush()
            else:
                current_lead.name = first_name
                current_lead.whatsapp = whatsapp.strip()
                current_lead.neighborhood = neighborhood.strip()
                current_lead.marketing_consent = marketing_consent
                current_lead.marketing_consent_at = now if marketing_consent else None
                current_lead.marketing_consent_version = (
                    MARKETING_CONSENT_VERSION if marketing_consent else None
                )
                current_lead.updated_at = now

            preferences = build_declared_preferences(answers)
            registration = Registration(
                lead_id=current_lead.id,
                name=first_name,
                email=None,
                whatsapp=whatsapp.strip(),
                whatsapp_normalized=normalized_whatsapp,
                neighborhood=neighborhood.strip(),
                marketing_consent=marketing_consent,
                marketing_consent_at=now if marketing_consent else None,
                marketing_consent_version=(
                    MARKETING_CONSENT_VERSION if marketing_consent else None
                ),
                marketing_consent_decided_at=now,
                marketing_consent_text_version=MARKETING_CONSENT_VERSION,
                privacy_notice_accepted_at=now,
                privacy_notice_version=PRIVACY_NOTICE_VERSION,
                answers_json=json.dumps(answers, ensure_ascii=False),
                answer_snapshot_json=json.dumps(
                    build_answer_snapshot(answers), ensure_ascii=False
                ),
                score_json=json.dumps(build_score_snapshot(answers), ensure_ascii=False),
                frequency=preferences["frequency"],
                occasion=preferences["occasion"],
                product_interest=preferences["product_interest"],
                experience_preference=preferences["experience_preference"],
                communication_interest=preferences["communication_interest"],
                campaign_source=CAMPAIGN_SOURCE,
                quiz_version=QUIZ_VERSION,
                submission_key=submission_key,
                profile=profile_id,
                created_at=now,
            )
            db.session.add(registration)
            db.session.flush()
            db.session.add(
                MarketingConsentEvent(
                    lead_id=current_lead.id,
                    registration_id=registration.id,
                    consented=marketing_consent,
                    text_version=MARKETING_CONSENT_VERSION,
                    created_at=now,
                )
            )
            db.session.add(SheetSyncJob(registration_id=registration.id))
            db.session.commit()
            return registration

        try:
            registration = save_registration()
        except IntegrityError:
            db.session.rollback()
            existing_registration = Registration.query.filter_by(
                submission_key=submission_key
            ).one_or_none()
            if existing_registration:
                return registration_response(existing_registration)
            existing_lead = Lead.query.filter_by(
                whatsapp_normalized=normalized_whatsapp
            ).one_or_none()
            if existing_lead is None:
                app.logger.exception("Falha de integridade ao salvar lead da Linha Fit.")
                return jsonify(
                    error="Não foi possível salvar seu cadastro. Tente novamente."
                ), 500
            try:
                registration = save_registration(existing_lead)
            except SQLAlchemyError:
                db.session.rollback()
                app.logger.exception("Falha ao salvar cadastro repetido da Linha Fit.")
                return jsonify(
                    error="Não foi possível salvar seu cadastro. Tente novamente."
                ), 500
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Falha ao salvar cadastro da Linha Fit.")
            return jsonify(
                error="Não foi possível salvar seu cadastro. Tente novamente."
            ), 500

        return registration_response(registration)

    @app.get("/admin")
    @require_admin
    def admin():
        retry_sheet_sync(limit=25)
        leads = Lead.query.order_by(Lead.updated_at.desc()).limit(200).all()
        lead_rows = []
        for lead in leads:
            history = sorted(
                lead.registrations,
                key=lambda registration: registration.created_at,
                reverse=True,
            )
            latest = history[0] if history else None
            lead_rows.append(
                {
                    "lead": lead,
                    "latest": latest,
                    "history_count": len(history),
                    "answers": json.loads(latest.answer_snapshot_json or "{}")
                    if latest
                    else {},
                    "scores": json.loads(latest.score_json or "{}") if latest else {},
                    "history": [
                        {
                            "registration": registration,
                            "answers": json.loads(
                                registration.answer_snapshot_json or "{}"
                            ),
                            "scores": json.loads(registration.score_json or "{}"),
                        }
                        for registration in history
                    ],
                    "preference_labels": {
                        "frequency": option_label("frequency", latest.frequency),
                        "occasion": option_label("occasion", latest.occasion),
                        "product": option_label("product", latest.product_interest),
                        "experience": option_label(
                            "experience", latest.experience_preference
                        ),
                        "news": option_label("news", latest.communication_interest),
                    }
                    if latest
                    else {},
                    "consent_events": sorted(
                        lead.consent_events,
                        key=lambda event: event.created_at,
                        reverse=True,
                    ),
                }
            )
        pending_count = SheetSyncJob.query.filter_by(synced_at=None).count()
        pending_jobs = (
            SheetSyncJob.query.filter_by(synced_at=None)
            .order_by(SheetSyncJob.registration_id.desc())
            .limit(10)
            .all()
        )
        synced_count = SheetSyncJob.query.filter(SheetSyncJob.synced_at.isnot(None)).count()
        return render_template(
            "admin.html",
            lead_rows=lead_rows,
            profiles=ALL_PROFILES,
            sheet_sync_configured=is_configured(app.config),
            pending_jobs=pending_jobs,
            pending_count=pending_count,
            synced_count=synced_count,
        )

    @app.get("/admin/export.csv")
    @require_admin
    def export_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Nome",
                "ID do cadastro",
                "E-mail legado",
                "WhatsApp",
                "WhatsApp normalizado",
                "Bairro/cidade",
                "Perfil",
                "Frequência declarada",
                "Ocasião de consumo",
                "Produto de interesse declarado",
                "Experiência preferida",
                "Assunto de interesse",
                "Respostas (IDs e textos)",
                "Pontuação por perfil",
                "Origem da campanha",
                "Versão do quiz",
                "Aceita novidades",
                "Data da decisão de autorização para novidades",
                "Versão do texto apresentado",
                "Aceite do aviso de privacidade",
                "Versão do aviso de privacidade",
                "Status Google Sheets",
                "Data/hora UTC",
            ]
        )

        def spreadsheet_safe(value):
            value = str(value or "")
            if value.startswith(("=", "+", "-", "@", "\t", "\r")):
                return "'" + value
            return value

        registrations = Registration.query.order_by(Registration.created_at.desc()).all()
        for registration in registrations:
            answers = json.loads(registration.answers_json)
            answer_snapshot = json.loads(registration.answer_snapshot_json or "{}")
            answer_summary = " | ".join(
                f"{question['question']} [{question_id}={question['answer_id']}]: "
                f"{question['answer']}"
                for question_id, question in answer_snapshot.items()
            )
            if not answer_summary:
                answer_summary = " | ".join(
                    f"{question_id}={answer_id}" for question_id, answer_id in answers.items()
                )
            scores = json.loads(registration.score_json or "{}")
            consent_event = MarketingConsentEvent.query.filter_by(
                registration_id=registration.id
            ).one_or_none()
            writer.writerow(
                [
                    spreadsheet_safe(registration.name),
                    registration.id,
                    spreadsheet_safe(registration.email),
                    spreadsheet_safe(registration.whatsapp),
                    spreadsheet_safe(registration.whatsapp_normalized),
                    spreadsheet_safe(registration.neighborhood),
                    spreadsheet_safe(ALL_PROFILES[registration.profile]["title"]),
                    spreadsheet_safe(format_preference("frequency", registration.frequency)),
                    spreadsheet_safe(format_preference("occasion", registration.occasion)),
                    spreadsheet_safe(format_preference("product", registration.product_interest)),
                    spreadsheet_safe(format_preference("experience", registration.experience_preference)),
                    spreadsheet_safe(format_preference("news", registration.communication_interest)),
                    spreadsheet_safe(answer_summary),
                    spreadsheet_safe(
                        " | ".join(
                            f"{profile_id}: {score}"
                            for profile_id, score in scores.items()
                        )
                    ),
                    spreadsheet_safe(registration.campaign_source),
                    spreadsheet_safe(registration.quiz_version),
                    "Sim" if registration.marketing_consent else "Não",
                    consent_event.created_at.isoformat() if consent_event else "",
                    consent_event.text_version if consent_event else "",
                    (
                        registration.privacy_notice_accepted_at.isoformat()
                        if registration.privacy_notice_accepted_at
                        else ""
                    ),
                    registration.privacy_notice_version or "",
                    (
                        "Sincronizada"
                        if registration.sheet_sync and registration.sheet_sync.synced_at
                        else "Pendente"
                    ),
                    registration.created_at.isoformat(),
                ]
            )

        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="sulamita-linha-fit-leads.csv"',
                "Cache-Control": "no-store",
            },
        )

    return app


app = create_app()
