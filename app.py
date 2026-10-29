import csv
import io
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, Response, jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from models import Registration, SheetSyncJob, db
from quiz import QUESTIONS, PROFILES, calculate_profile
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
                sync_registration(job.registration, PROFILES, QUESTIONS, app.config)
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

    @app.get("/api/questions")
    def get_questions():
        return jsonify(QUESTIONS)

    @app.post("/api/submit")
    def submit_quiz():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Envie os dados do formulário em JSON."), 400

        name = data.get("name")
        whatsapp = data.get("whatsapp")
        email = data.get("email", "")
        answers = data.get("answers")
        consent = data.get("consent")
        marketing_consent = data.get("marketing_consent", False)

        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            return jsonify(error="Informe seu nome (até 100 caracteres)."), 400
        if not isinstance(whatsapp, str) or not whatsapp.strip() or len(whatsapp.strip()) > 30:
            return jsonify(error="Informe um WhatsApp válido."), 400
        if not isinstance(email, str) or len(email) > 254:
            return jsonify(error="O e-mail deve ter até 254 caracteres."), 400
        if email.strip() and ("@" not in email or "." not in email.rsplit("@", 1)[-1]):
            return jsonify(error="Informe um e-mail válido."), 400
        if consent is not True:
            return jsonify(error="É necessário consentir com o uso dos dados para participar."), 400
        if not isinstance(marketing_consent, bool):
            return jsonify(error="A preferência de novidades é inválida."), 400

        question_ids = {question["id"] for question in QUESTIONS}
        if not isinstance(answers, dict) or set(answers) != question_ids:
            return jsonify(error="Responda todas as perguntas do quiz."), 400
        for question in QUESTIONS:
            valid_options = {option["id"] for option in question["options"]}
            if not isinstance(answers[question["id"]], str) or answers[question["id"]] not in valid_options:
                return jsonify(error="Uma das respostas não é válida."), 400

        profile_id = calculate_profile(answers)
        profile = PROFILES[profile_id]
        registration = Registration(
            name=name.strip(),
            email=email.strip() or None,
            whatsapp=whatsapp.strip(),
            marketing_consent=marketing_consent,
            answers_json=json.dumps(answers, ensure_ascii=False),
            profile=profile_id,
        )
        try:
            db.session.add(registration)
            db.session.flush()
            db.session.add(SheetSyncJob(registration_id=registration.id))
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Falha ao salvar inscrição da Linha Fit.")
            return jsonify(error="Não foi possível salvar sua participação. Tente novamente."), 500

        synced_ids = dispatch_sheet_sync(limit=1)
        response = jsonify(
            success=True,
            profile={"id": profile_id, **profile},
            sheet_backup=(
                "synced" if registration.id in synced_ids else
                "pending" if is_configured(app.config) else
                "not_configured"
            ),
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/admin")
    @require_admin
    def admin():
        retry_sheet_sync(limit=25)
        registrations = Registration.query.order_by(Registration.created_at.desc()).limit(200).all()
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
            registrations=registrations,
            profiles=PROFILES,
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
                "E-mail",
                "WhatsApp",
                "Perfil",
                "Respostas",
                "Aceita novidades",
                "Status Google Sheets",
                "Data UTC",
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
            answer_summary = " | ".join(
                f"{question['text']}: "
                f"{next(option['text'] for option in question['options'] if option['id'] == answers[question['id']])}"
                for question in QUESTIONS
            )
            writer.writerow(
                [
                    spreadsheet_safe(registration.name),
                    spreadsheet_safe(registration.email),
                    spreadsheet_safe(registration.whatsapp),
                    spreadsheet_safe(PROFILES[registration.profile]["title"]),
                    spreadsheet_safe(answer_summary),
                    "Sim" if registration.marketing_consent else "Não",
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
