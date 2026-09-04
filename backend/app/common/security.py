import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.common.config import get_settings

_pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated=["bcrypt"],
    argon2__type="ID",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# This intentionally remains small and auditable. The structural checks below
# do the rest of the work; this list catches passwords that most commonly
# satisfy superficial complexity requirements.
_COMMON_PASSWORDS = frozenset(
    {
        "123456789012",
        "admin123456!",
        "changeme123!",
        "letmein12345!",
        "password123!",
        "password1234",
        "password1234!",
        "qwerty123456",
        "qwerty123456!",
        "welcome12345!",
        "welcome123!",
    }
)
_COMMON_PASSWORD_STEMS = frozenset(
    {
        "abc",
        "admin",
        "administrator",
        "changeme",
        "dragon",
        "football",
        "iloveyou",
        "letmein",
        "login",
        "monkey",
        "password",
        "qwerty",
        "secret",
        "welcome",
    }
)
_LEETSPEAK_TRANSLATION = str.maketrans(
    {
        "@": "a",
        "3": "e",
        "1": "i",
        "!": "i",
        "0": "o",
        "$": "s",
        "5": "s",
        "7": "t",
    }
)


def _normalized_secret_text(value: str) -> str:
    """Normalize text for password/context comparisons without changing passwords."""

    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value)
        .casefold()
        .translate(_LEETSPEAK_TRANSLATION)
        if character.isalnum()
    )


def _identity_tokens(*values: str | None) -> set[str]:
    """Return meaningful identity fragments that must not appear in a password."""

    tokens: set[str] = set()
    for value in values:
        if not value:
            continue
        # Include each whitespace/punctuation-delimited fragment as well as the
        # full normalized value (for example, an email local-part).
        for fragment in value.replace("@", " ").replace(".", " ").split():
            normalized = _normalized_secret_text(fragment)
            if len(normalized) >= 3:
                tokens.add(normalized)
        normalized = _normalized_secret_text(value)
        if len(normalized) >= 3:
            tokens.add(normalized)
    return tokens


def normalize_email(value: str) -> str:
    """Return the canonical form used for storage and lookup.

    Syntax validation remains the responsibility of Pydantic's ``EmailStr``;
    this helper deliberately has no dependency on the schema layer.
    """

    return value.strip().lower()


def validate_password(
    password: str,
    *,
    email: str | None = None,
    name: str | None = None,
    org_name: str | None = None,
    username: str | None = None,
    tenant_code: str | None = None,
) -> None:
    """Validate passwords at account creation/change boundaries.

    Passwords are never stripped or normalized. Login paths must not call this
    function because an existing password must be accepted exactly as stored.
    """

    errors: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"be at most {MAX_PASSWORD_LENGTH} characters")
    if not any(char.islower() for char in password):
        errors.append("include a lowercase letter")
    if not any(char.isupper() for char in password):
        errors.append("include an uppercase letter")
    if not any(char.isdigit() for char in password):
        errors.append("include a number")
    if not any(unicodedata.category(char)[0] in {"P", "S"} for char in password):
        errors.append("include a special character")

    password_folded = password.casefold()
    common_candidate = "".join(character for character in password_folded if character.isalnum())
    deobfuscated_candidate = "".join(
        character
        for character in password_folded.translate(_LEETSPEAK_TRANSLATION)
        if character.isalnum()
    )
    common_stem_match = any(
        candidate.startswith(stem)
        for candidate in (common_candidate, deobfuscated_candidate)
        for stem in _COMMON_PASSWORD_STEMS
    )
    if password_folded in _COMMON_PASSWORDS or common_stem_match:
        errors.append("not be a commonly used password")

    normalized_password = _normalized_secret_text(password)
    # Passwords are exact secrets; this comparison is solely for policy
    # enforcement at creation/change boundaries. Never log either value.
    if any(
        token in normalized_password
        for token in _identity_tokens(email, name, org_name, username, tenant_code)
    ):
        errors.append("not contain your name, email, username, organization, or tenant code")

    if errors:
        raise ValueError("Password must " + ", ".join(errors) + ".")


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    verified, _ = verify_password_and_update(plain_password, password_hash)
    return verified


def _perform_dummy_verification() -> None:
    # Every failed lookup burns one Argon2id and one bcrypt verification. Real
    # accounts burn the opposite dummy scheme alongside their stored scheme,
    # avoiding a fast "account does not exist" branch and reducing observable
    # differences while legacy bcrypt accounts are being migrated.
    _pwd_context.verify(_DUMMY_PASSWORD, _DUMMY_ARGON2_HASH)
    _pwd_context.verify(_DUMMY_PASSWORD, _DUMMY_BCRYPT_HASH)


def verify_password_and_update(plain_password: str, password_hash: str) -> tuple[bool, str | None]:
    """Verify a hash and return an Argon2id replacement for legacy bcrypt.

    Callers should persist ``replacement_hash`` only after a successful
    verification. Malformed or unsupported hashes are treated as a mismatch.
    """

    try:
        scheme = _pwd_context.identify(password_hash)
    except (TypeError, ValueError):
        scheme = None
    if scheme not in {"argon2", "bcrypt"}:
        _perform_dummy_verification()
        return False, None

    try:
        verified, replacement_hash = _pwd_context.verify_and_update(plain_password, password_hash)
    except (TypeError, ValueError):
        verified, replacement_hash = False, None
    finally:
        if scheme == "argon2":
            _pwd_context.verify(_DUMMY_PASSWORD, _DUMMY_BCRYPT_HASH)
        else:
            _pwd_context.verify(_DUMMY_PASSWORD, _DUMMY_ARGON2_HASH)
    return bool(verified), replacement_hash


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _pwd_context.needs_update(password_hash)
    except (TypeError, ValueError):
        return True


# Created once at process startup so nonexistent accounts execute the same two
# password-hash families supported for real accounts.
_DUMMY_PASSWORD = "Dummy-Account-Password-4f2c!"
_DUMMY_ARGON2_HASH = _pwd_context.hash(_DUMMY_PASSWORD, scheme="argon2")
_DUMMY_BCRYPT_HASH = _pwd_context.hash(_DUMMY_PASSWORD, scheme="bcrypt")


def verify_password_or_dummy(plain_password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _perform_dummy_verification()
        return False
    return verify_password(plain_password, password_hash)


def create_access_token(claims: dict[str, Any]) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {**claims, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
