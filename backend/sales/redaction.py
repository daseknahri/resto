"""Masking of bearer secrets (activation / password-reset tokens) in anything the
platform PERSISTS or DISPLAYS — provisioning-job logs and admin-audit metadata.

What is SENT to the owner (email, WhatsApp, the admin's one-time API response) keeps
the raw token; that is the whole point of the link. The ``ActivationToken`` row is
the source of truth whenever an unused link has to be shown again — never a log.
"""
import re

# token=<v> in a URL (raw or URL-encoded inside a WhatsApp ``?text=``), the
# "Activation token: <v>" message line (raw or URL-encoded), and a token carried
# as a path segment (/activate/<v>, /reset-password/<v>). An already-masked value
# ("abcdef...wxyz") is too short before its "..." to match again.
_ANCHORED_TOKEN_RE = re.compile(
    r"(?i)(token(?:=|%3D|:[ \t]*|%3A(?:\+|%20)?)|/(?:activate|reset-password)/)([A-Za-z0-9_-]{8,})"
)
# Belt and braces: every token is ``secrets.token_hex(24)`` (48 lowercase hex chars),
# so a long lowercase-hex run is a secret wherever it ended up.
_LONG_HEX_RE = re.compile(r"[0-9a-f]{32,}")


def mask_secret(secret: str, keep_start: int = 6, keep_end: int = 4) -> str:
    if not secret:
        return ""
    if len(secret) <= keep_start + keep_end:
        return "*" * len(secret)
    return f"{secret[:keep_start]}...{secret[-keep_end:]}"


def mask_token_in(text: str, token: str) -> str:
    """``text`` with every occurrence of the raw ``token`` replaced by its mask.

    Tokens are hex, which ``quote_plus`` leaves untouched, so this also masks the
    URL-encoded copies inside a ``wa.me/...?text=`` link.
    """
    if not text or not token:
        return text or ""
    return text.replace(token, mask_secret(token))


def redact_tokens(text):
    """Defensive mask for text that may predate write-time masking (historical
    ``ProvisioningJob.log`` lines / audit metadata). Non-strings pass through."""
    if not isinstance(text, str) or not text:
        return text
    text = _ANCHORED_TOKEN_RE.sub(lambda m: m.group(1) + mask_secret(m.group(2)), text)
    return _LONG_HEX_RE.sub(lambda m: mask_secret(m.group(0)), text)


def redact_tokens_in(value):
    """``redact_tokens`` applied to every string inside a JSON-shaped value."""
    if isinstance(value, str):
        return redact_tokens(value)
    if isinstance(value, dict):
        return {key: redact_tokens_in(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_tokens_in(item) for item in value]
    return value
