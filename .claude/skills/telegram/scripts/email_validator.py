"""
Email validation with typo detection for common domain mistakes.

Validates email format and suggests corrections for common typos
in popular email domains (gmail, yahoo, hotmail, outlook).
"""
from typing import Optional
import re


# Mapping of common typos to correct domains
DOMAIN_CORRECTIONS: dict[str, str] = {
    # Gmail typos
    "gmil.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.cm": "gmail.com",
    "gmail.con": "gmail.com",
    "gmail.cim": "gmail.com",
    "gmail.vom": "gmail.com",
    "gmail.xom": "gmail.com",
    "gmaill.com": "gmail.com",
    "ggmail.com": "gmail.com",
    # Yahoo typos
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "yhoo.com": "yahoo.com",
    "yhaoo.com": "yahoo.com",
    "yahoo.co": "yahoo.com",
    "yahoo.cm": "yahoo.com",
    "yahoo.con": "yahoo.com",
    # Hotmail typos
    "hotmial.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "hotamil.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "hotmail.co": "hotmail.com",
    "hotmail.cm": "hotmail.com",
    "hotmail.con": "hotmail.com",
    "hotmaill.com": "hotmail.com",
    "htmail.com": "hotmail.com",
    "homail.com": "hotmail.com",
    # Outlook typos
    "outloo.com": "outlook.com",
    "outlok.com": "outlook.com",
    "outlokk.com": "outlook.com",
    "outloook.com": "outlook.com",
    "outlook.co": "outlook.com",
    "outlook.cm": "outlook.com",
    "outlook.con": "outlook.com",
    "outlok.com": "outlook.com",
    "otlook.com": "outlook.com",
    "oulook.com": "outlook.com",
    # Mail.ru typos (common for Russian users)
    "mail.r": "mail.ru",
    "mail.ruu": "mail.ru",
    "mai.ru": "mail.ru",
    "mal.ru": "mail.ru",
    "maill.ru": "mail.ru",
    # Yandex typos (common for Russian users)
    "yandex.r": "yandex.ru",
    "yandex.ruu": "yandex.ru",
    "yndex.ru": "yandex.ru",
    "ynadex.ru": "yandex.ru",
    "yanex.ru": "yandex.ru",
    "yandx.ru": "yandex.ru",
}

# Basic email regex pattern - matches format from models.py
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def validate_email_with_suggestions(email: str) -> tuple[bool, str, Optional[str]]:
    """
    Validate email and suggest corrections for common typos.

    Performs basic format validation and checks the domain against
    a list of common typos, suggesting corrections when found.

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, error_message, suggested_correction)
        - is_valid: True if email is valid and has no typos
        - error_message: Empty string if valid, Russian error message if invalid
        - suggested_correction: Suggested corrected email if typo detected, None otherwise

    Examples:
        >>> validate_email_with_suggestions("user@gmail.com")
        (True, "", None)

        >>> validate_email_with_suggestions("user@gmial.com")
        (False, "Возможно, вы имели в виду user@gmail.com?", "user@gmail.com")

        >>> validate_email_with_suggestions("invalid-email")
        (False, "Пожалуйста, укажите корректный email адрес.", None)
    """
    # Handle empty or whitespace-only input
    if not email or not email.strip():
        return (False, "Для записи на встречу нужен email. На какой адрес отправить приглашение?", None)

    email = email.strip().lower()

    # Basic format check - must have @ and . in domain
    if "@" not in email:
        return (False, "Пожалуйста, укажите корректный email адрес.", None)

    parts = email.split("@")
    if len(parts) != 2:
        return (False, "Пожалуйста, укажите корректный email адрес.", None)

    local_part, domain = parts

    # Check local part is not empty
    if not local_part:
        return (False, "Пожалуйста, укажите корректный email адрес.", None)

    # Check domain has at least one dot
    if "." not in domain:
        return (False, "Пожалуйста, укажите корректный email адрес.", None)

    # Full regex validation
    if not EMAIL_PATTERN.match(email):
        return (False, "Пожалуйста, укажите корректный email адрес.", None)

    # Check for common domain typos
    if domain in DOMAIN_CORRECTIONS:
        corrected_domain = DOMAIN_CORRECTIONS[domain]
        suggested_email = f"{local_part}@{corrected_domain}"
        return (
            False,
            f"Возможно, вы имели в виду {suggested_email}?",
            suggested_email
        )

    # Email is valid with no typos detected
    return (True, "", None)


def get_domain_suggestion(domain: str) -> Optional[str]:
    """
    Get correction suggestion for a domain if it's a known typo.

    Args:
        domain: Email domain to check (e.g., "gmial.com")

    Returns:
        Corrected domain if typo found, None otherwise
    """
    return DOMAIN_CORRECTIONS.get(domain.lower())


# Simple test
if __name__ == "__main__":
    test_cases = [
        # Valid emails
        ("user@gmail.com", True, "", None),
        ("test@yahoo.com", True, "", None),
        ("name@outlook.com", True, "", None),
        ("email@mail.ru", True, "", None),
        # Typo emails
        ("user@gmial.com", False, "Возможно, вы имели в виду user@gmail.com?", "user@gmail.com"),
        ("test@yaho.com", False, "Возможно, вы имели в виду test@yahoo.com?", "test@yahoo.com"),
        ("name@hotmial.com", False, "Возможно, вы имели в виду name@hotmail.com?", "name@hotmail.com"),
        ("test@outloo.com", False, "Возможно, вы имели в виду test@outlook.com?", "test@outlook.com"),
        # Invalid emails
        ("invalid", False, "Пожалуйста, укажите корректный email адрес.", None),
        ("no-at-symbol.com", False, "Пожалуйста, укажите корректный email адрес.", None),
        ("@nodomain.com", False, "Пожалуйста, укажите корректный email адрес.", None),
        ("user@", False, "Пожалуйста, укажите корректный email адрес.", None),
        ("", False, "Для записи на встречу нужен email. На какой адрес отправить приглашение?", None),
    ]

    print("=== Email Validator Tests ===\n")

    all_passed = True
    for email, expected_valid, expected_msg, expected_suggestion in test_cases:
        is_valid, message, suggestion = validate_email_with_suggestions(email)

        passed = (
            is_valid == expected_valid and
            message == expected_msg and
            suggestion == expected_suggestion
        )

        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False

        print(f"[{status}] Email: '{email}'")
        if not passed:
            print(f"  Expected: valid={expected_valid}, msg='{expected_msg}', suggestion={expected_suggestion}")
            print(f"  Got:      valid={is_valid}, msg='{message}', suggestion={suggestion}")
        print()

    print("=" * 40)
    print(f"All tests {'PASSED' if all_passed else 'FAILED'}")
