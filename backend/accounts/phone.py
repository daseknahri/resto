"""Phone-number normalization for wallet transfers.

Goal: turn whatever a sender types into the same E.164 form (`+212612345678`) that
the OTP signup flow stores, so recipient lookups match reliably. For a money feature
the rule is "normalize, never guess": if we can't produce a confident E.164 value we
return "" and the caller rejects the input rather than risk crediting a wrong number.
"""


def normalize_e164(raw, default_dial_code: str = "") -> str:
    """Best-effort E.164 normalization. Returns "" when it can't confidently resolve.

    - strips spaces, dashes, dots, parentheses (anything that isn't a digit or '+')
    - "+…"  → kept (already international)
    - "00…" → "+…" (international prefix)
    - "0…"  → "+<default_dial_code>…" when a default_dial_code is configured
    - anything else (bare national number, no country context) → "" (refuse to guess)
    """
    cleaned = "".join(ch for ch in (raw or "") if ch.isdigit() or ch == "+")
    if not cleaned:
        return ""

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    elif cleaned.startswith("00"):
        digits = cleaned[2:]
    elif cleaned.startswith("0"):
        cc = "".join(ch for ch in (default_dial_code or "") if ch.isdigit())
        if not cc:
            return ""  # local number but no country context — don't guess
        digits = cc + cleaned[1:]
    else:
        return ""  # bare digits with no leading 0 or '+' — ambiguous, refuse

    # A '+' anywhere but the start is malformed; digits must be all-numeric and plausible.
    if not digits.isdigit() or len(digits) < 6:
        return ""
    return "+" + digits
