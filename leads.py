import re


def normalize_whatsapp(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("55") and len(digits) in (12, 13):
        national_number = digits[2:]
    elif len(digits) in (10, 11):
        national_number = digits
        digits = "55" + digits
    else:
        return None

    area_code = national_number[:2]
    subscriber = national_number[2:]
    if not area_code.isdigit() or area_code.startswith("0") or subscriber.startswith("0"):
        return None
    return f"+{digits}"
