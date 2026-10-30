import json

from quiz import format_preference


class SheetSyncError(Exception):
    pass


HEADERS = [
    "ID",
    "Nome",
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
    "Respostas do quiz",
    "Pontuação por perfil",
    "Origem da campanha",
    "Versão do quiz",
    "Aceita novidades",
    "Data da decisão de autorização para novidades",
    "Versão do texto apresentado",
    "Aceite do aviso de privacidade",
    "Versão do aviso de privacidade",
    "Data UTC",
]


def is_configured(config):
    return bool(config.get("SHEETS_SERVICE_ACCOUNT_JSON") and config.get("SHEETS_SPREADSHEET_ID"))


def registration_values(registration, profiles, questions):
    answers = json.loads(registration.answers_json)
    answer_snapshot = json.loads(getattr(registration, "answer_snapshot_json", None) or "{}")
    answer_summary = " | ".join(
        f"{answer['question']} [{question_id}={answer['answer_id']}]: {answer['answer']}"
        for question_id, answer in answer_snapshot.items()
    )
    if not answer_summary:
        answer_summary = " | ".join(
            f"{question_id}={answer_id}" for question_id, answer_id in answers.items()
        )
    scores = json.loads(getattr(registration, "score_json", None) or "{}")
    return [
        registration.id,
        registration.name,
        getattr(registration, "email", None) or "",
        registration.whatsapp,
        getattr(registration, "whatsapp_normalized", None) or "",
        getattr(registration, "neighborhood", None) or "",
        profiles[registration.profile]["title"],
        format_preference("frequency", getattr(registration, "frequency", None)),
        format_preference("occasion", getattr(registration, "occasion", None)),
        format_preference("product", getattr(registration, "product_interest", None)),
        format_preference("experience", getattr(registration, "experience_preference", None)),
        format_preference("news", getattr(registration, "communication_interest", None)),
        answer_summary,
        " | ".join(f"{profile_id}: {score}" for profile_id, score in scores.items()),
        getattr(registration, "campaign_source", None) or "",
        getattr(registration, "quiz_version", None) or "",
        "Sim" if registration.marketing_consent else "Não",
        (
            registration.marketing_consent_decided_at.isoformat()
            if getattr(registration, "marketing_consent_decided_at", None)
            else ""
        ),
        getattr(registration, "marketing_consent_text_version", None) or "",
        (
            registration.privacy_notice_accepted_at.isoformat()
            if getattr(registration, "privacy_notice_accepted_at", None)
            else ""
        ),
        getattr(registration, "privacy_notice_version", None) or "",
        registration.created_at.isoformat(),
    ]


def sync_registration(registration, profiles, questions, config):
    try:
        import gspread
        import requests
        from google.auth.exceptions import GoogleAuthError
        from google.oauth2.service_account import Credentials

        service_account_info = json.loads(config["SHEETS_SERVICE_ACCOUNT_JSON"])
        credentials = Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(credentials)
        client.set_timeout((5, 15))
        worksheet = client.open_by_key(config["SHEETS_SPREADSHEET_ID"]).worksheet("Respostas")

        existing_headers = worksheet.get("A1:V1")
        if not existing_headers or not any(str(cell).strip() for cell in existing_headers[0]):
            worksheet.update("A1:V1", [HEADERS], value_input_option="RAW")
        elif existing_headers[0] != HEADERS:
            raise SheetSyncError(
                'A primeira linha da aba "Respostas" deve conter os cabeçalhos esperados.'
            )

        target_row = registration.id + 1
        if worksheet.row_count < target_row:
            worksheet.add_rows(target_row - worksheet.row_count)
        worksheet.update(
            f"A{target_row}:V{target_row}",
            [registration_values(registration, profiles, questions)],
            value_input_option="RAW",
        )
    except SheetSyncError:
        raise
    except (ImportError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SheetSyncError(f"Configuração inválida do Google Sheets: {error}") from error
    except (GoogleAuthError, gspread.exceptions.GSpreadException, requests.exceptions.RequestException) as error:
        raise SheetSyncError(f"Falha ao sincronizar com o Google Sheets: {error}") from error
