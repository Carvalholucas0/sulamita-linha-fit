import json


class SheetSyncError(Exception):
    pass


HEADERS = [
    "ID",
    "Nome",
    "E-mail",
    "WhatsApp",
    "Perfil",
    "Respostas do quiz",
    "Consentimento para participação",
    "Aceita novidades",
    "Data UTC",
]


def is_configured(config):
    return bool(config.get("SHEETS_SERVICE_ACCOUNT_JSON") and config.get("SHEETS_SPREADSHEET_ID"))


def registration_values(registration, profiles, questions):
    answers = json.loads(registration.answers_json)
    answer_summary = " | ".join(
        f"{question['text']}: "
        f"{next(option['text'] for option in question['options'] if option['id'] == answers[question['id']])}"
        for question in questions
    )
    return [
        registration.id,
        registration.name,
        registration.email or "",
        registration.whatsapp,
        profiles[registration.profile]["title"],
        answer_summary,
        "Sim",
        "Sim" if registration.marketing_consent else "Não",
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

        existing_headers = worksheet.get("A1:I1")
        if not existing_headers or not any(str(cell).strip() for cell in existing_headers[0]):
            worksheet.update("A1:I1", [HEADERS], value_input_option="RAW")
        elif existing_headers[0] != HEADERS:
            raise SheetSyncError(
                'A primeira linha da aba "Respostas" deve conter os cabeçalhos esperados.'
            )

        target_row = registration.id + 1
        if worksheet.row_count < target_row:
            worksheet.add_rows(target_row - worksheet.row_count)
        worksheet.update(
            f"A{target_row}:I{target_row}",
            [registration_values(registration, profiles, questions)],
            value_input_option="RAW",
        )
    except SheetSyncError:
        raise
    except (ImportError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SheetSyncError(f"Configuração inválida do Google Sheets: {error}") from error
    except (GoogleAuthError, gspread.exceptions.GSpreadException, requests.exceptions.RequestException) as error:
        raise SheetSyncError(f"Falha ao sincronizar com o Google Sheets: {error}") from error
