"""Central log redaction for the Sea Speed API and the Ubuntu worker scripts (issue #698).

Stdlib-only by design: no third-party imports, no secret environment reads and
no import of the API application, so the worker scripts can load this module
without pulling the API dependency surface. The module is pure text
sanitization; ``redact_log_text`` masks credential VALUES while preserving the
surrounding structure and leaving benign text byte-identical.

Two output boundaries are wired through this module:

* the API process (module logger audit records, uvicorn access/error handlers
  and the app-authored direct ``sys.stderr`` prints) via
  :func:`install_api_redaction`, :class:`RedactingFilter` and
  :class:`RedactingFormatter`;
* the Ubuntu worker scripts, which import :func:`redact_log_text` directly and
  sanitize the rendered line before writing it to stdout/stderr.
"""

from __future__ import annotations

import logging
import re

# Fixed replacement marker for every masked VALUE.
REDACTED = "[REDACTED]"

# Authorization headers: "Authorization: Bearer x", the Python header-map repr
# form "'Authorization': 'Bearer x'" and JSON-ish 'authorization="Bearer x"'.
# Case-insensitive; the value runs up to the next structural delimiter so dots
# and trailing base64 "=" padding are consumed with the credential.
_AUTH_BEARER_RE = re.compile(
    r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?\s*bearer\s+)([^\s'\",;}]+)"
)

# Labelled secrets: key=/token= forms including api_key / api-key / access_token.
# The leading negative lookbehind is the FIELD boundary that keeps "monkey="
# from matching the trailing "key"; an underscore prefix such as X_API_KEY is
# still accepted. Quoted values keep their quote characters; a bare value runs
# to the next whitespace, quote, comma, semicolon, closing bracket or URL query
# delimiter (& / #), and may contain dots and trailing "=" padding.
_LABEL_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])("
    r"api[_-]?key|access[_-]?token|auth[_-]?token|refresh[_-]?token|"
    r"bearer[_-]?token|id[_-]?token|client[_-]?secret|"
    r"token|password|passwd|pwd|secret|key"
    r")([\"']?\s*[:=]\s*)"
    r"(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'&#,;)}\]]+))"
)

# Unlabeled free-text heuristic: a WHOLE atom (not a key=value fragment) that
# looks like a digest. A labelled digest field such as "sha256=<hex>" is a
# single atom containing "=" in the middle, so it is never matched whole.
_ATOM_RE = re.compile(r"(?<![A-Za-z0-9+/=_-])([A-Za-z0-9+/=_-]{32,})(?![A-Za-z0-9+/=_-])")
_HEX_RE = re.compile(r"[0-9a-fA-F]{32,}")
_B64_RE = re.compile(r"[A-Za-z0-9+/_-]+={0,2}")
_HEX_LETTER_RE = re.compile(r"[A-Fa-f]")

# Labelled digest fields are structured, non-secret values and are exempt from
# the atom heuristic (spec: "labelled digests are not matched"). Matched against
# the text that ends immediately before the atom, so it covers both the bare
# "sha256=<hex>" form and the JSON '"sha256": "<hex>"' form while leaving every
# unlabeled atom to the normal heuristic.
_DIGEST_LABEL_BEFORE_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])"
    r"(?:sha|sha1|sha224|sha256|sha384|sha512|md5|digest|hash|checksum|etag)"
    r"[\"']?\s*[:=]\s*[\"']?\s*$"
)
# The bare form "sha256=<hex>" is a SINGLE atom (the "=" is inside the atom
# charclass), so the label never appears in the preceding text. Exempt it by
# matching the digest label at the start of the atom itself.
_DIGEST_LABEL_ATOM_RE = re.compile(
    r"(?i)^(?:sha|sha1|sha224|sha256|sha384|sha512|md5|digest|hash|checksum|etag)"
    r"[\"']?\s*[:=]"
)


def _mask_bearer(match: "re.Match[str]") -> str:
    prefix, value = match.group(1), match.group(2)
    if REDACTED in value:  # idempotent: never re-wrap a masked value
        return match.group(0)
    return prefix + REDACTED


def _mask_labelled(match: "re.Match[str]") -> str:
    label, separator = match.group(1), match.group(2)
    double, single, bare = match.group(3), match.group(4), match.group(5)
    if double is not None:
        if not double or REDACTED in double:
            return match.group(0)
        return f'{label}{separator}"{REDACTED}"'
    if single is not None:
        if not single or REDACTED in single:
            return match.group(0)
        return f"{label}{separator}'{REDACTED}'"
    if bare is not None:
        # The bare charclass stops at "]", so an already-masked bare value
        # arrives as "[REDACTED"; the prefix check keeps re-runs idempotent.
        if bare.startswith(REDACTED[:-1]) or REDACTED in bare:
            return match.group(0)
        return label + separator + REDACTED
    return match.group(0)


def _is_maskable_atom(atom: str) -> bool:
    # Whole hex digest containing at least one hex letter. All-digit atoms are
    # numeric telemetry, not credentials, and survive.
    if _HEX_RE.fullmatch(atom) and _HEX_LETTER_RE.search(atom):
        return True
    # A digest embedded in a short prefix (e.g. a "canary-<hex>" token in a
    # traceback source line) still carries a >=32 hex run with a hex letter;
    # ordinary single-case words contain no such run and survive.
    for run in _HEX_RE.finditer(atom):
        if _HEX_LETTER_RE.search(run.group(0)):
            return True
    core = atom.rstrip("=")
    if len(core) < 32 or not _B64_RE.fullmatch(atom):
        return False
    if atom.endswith("="):
        return True
    # Mixed-case + digits is credential-shaped; unremarkable single-case strings
    # (the common free-text word) survive.
    return (
        any(ch.islower() for ch in core)
        and any(ch.isupper() for ch in core)
        and any(ch.isdigit() for ch in core)
    )


def _mask_atom(match: "re.Match[str]") -> str:
    atom = match.group(1)
    # A value immediately preceded by a digest-style label is a labelled
    # digest, not a credential: leave it byte-identical. Cover both the bare
    # "sha256=<hex>" single-atom form and the JSON '"sha256": "<hex>"' form.
    if _DIGEST_LABEL_ATOM_RE.match(atom) or _DIGEST_LABEL_BEFORE_RE.search(
        match.string[: match.start()]
    ):
        return atom
    return REDACTED if _is_maskable_atom(atom) else atom


def redact_log_text(text: str) -> str:
    """Return ``text`` with credential values masked and structure preserved.

    Pure and idempotent: applying it to already-masked text returns the same
    bytes, and text with no credential shape is returned unchanged.
    """
    if not text:
        return text
    text = _AUTH_BEARER_RE.sub(_mask_bearer, text)
    text = _LABEL_RE.sub(_mask_labelled, text)
    text = _ATOM_RE.sub(_mask_atom, text)
    return text


_FILTER_MARKER = "_sea_speed_698_redacting_filter"
_FORMATTER_MARKER = "_sea_speed_698_redacting_formatter"
_IDENTITY_LOGGER_NAMES = ("identity", "api.app.identity")
# uvicorn 0.54.0's LOGGING_CONFIG gives uvicorn.error NO handler of its own:
# its records (incl. tracebacks) propagate to the parent "uvicorn" logger,
# whose "default" handler carries a plain DefaultFormatter. Wrap the parent too
# so formatter-appended exception text is sanitized; uvicorn.access keeps its
# own separately wrapped handler (the idempotence marker prevents double wraps).
_UVICORN_LOGGER_NAMES = ("uvicorn.access", "uvicorn.error", "uvicorn")


class RedactingFilter(logging.Filter):
    """Logger filter that sanitizes a record's rendered message in place.

    Rendering ``record.getMessage()`` first makes the sanitized text visible to
    ``caplog``/``assertLogs``-style captures too; ``record.args`` is cleared
    because the message is already final. An attached ``exc_info`` is also
    pre-rendered (via ``logging.Formatter().formatException``) and sanitized so
    a traceback carrying a credential cannot bypass the filter.
    """

    def __init__(self) -> None:
        super().__init__()
        setattr(self, _FILTER_MARKER, True)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_log_text(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_text = redact_log_text(
                logging.Formatter().formatException(record.exc_info)
            )
        return True


class RedactingFormatter(logging.Formatter):
    """Formatter wrapper that redacts the fully-formatted output.

    Used for uvicorn's access/error handlers, whose formatters consume a
    structured ``record.args`` dict and append exception text themselves; the
    inner formatter runs first so status codes, the request line and tracebacks
    are all covered without clearing ``record.args``.
    """

    def __init__(self, inner: logging.Formatter | None = None) -> None:
        super().__init__()
        self._inner = inner if inner is not None else logging.Formatter()
        setattr(self, _FORMATTER_MARKER, True)

    def format(self, record: logging.LogRecord) -> str:
        return redact_log_text(self._inner.format(record))


def _ensure_identity_filter() -> None:
    """Attach the filter to any already-imported identity logger object.

    The logger name differs between the package (``api.app.identity``) and the
    production uvicorn app-dir (``identity``) import modes, so this scans the
    live logger registry instead of hard-coding one name and never imports the
    application. ``identity`` also attaches its own filter at module init, so a
    not-yet-imported identity logger is covered by that module.
    """
    for logger in list(logging.Logger.manager.loggerDict.values()):
        if not isinstance(logger, logging.Logger):
            continue
        if logger.name not in _IDENTITY_LOGGER_NAMES:
            continue
        if not any(getattr(existing, _FILTER_MARKER, False) for existing in logger.filters):
            logger.addFilter(RedactingFilter())


def _wrap_uvicorn_formatters() -> None:
    for name in _UVICORN_LOGGER_NAMES:
        logger = logging.getLogger(name)
        for handler in logger.handlers:
            formatter = handler.formatter
            if isinstance(formatter, RedactingFormatter) or getattr(
                formatter, _FORMATTER_MARKER, False
            ):
                continue
            handler.setFormatter(RedactingFormatter(formatter))


def install_api_redaction() -> None:
    """Idempotently wire API-side redaction (safe across imports and reloads).

    Attaches :class:`RedactingFilter` to the identity logger and wraps the
    ``uvicorn.access``/``uvicorn.error`` handler formatters. Levels, handler
    identity, propagation and the audit message structure are left unchanged.
    """
    _ensure_identity_filter()
    _wrap_uvicorn_formatters()


__all__ = [
    "REDACTED",
    "redact_log_text",
    "RedactingFilter",
    "RedactingFormatter",
    "install_api_redaction",
]
