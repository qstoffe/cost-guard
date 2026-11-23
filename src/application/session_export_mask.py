"""Conservative credential masking; no network, entropy tests or PII scrubbing."""
import re

_MASK = '[REDACTED]'
_FIELD = (
    r'(?:(?:[a-z][a-z0-9_-]{0,62}[_-])?'
    r'(?:password|passwd|pwd|api[_-]?key|access[_-]?key(?:[_-]?id)?|'
    r'secret[_-]?access[_-]?key|client[_-]?secret|private[_-]?key|'
    r'(?:access|refresh|auth|session)[_-]?token)|'
    r'(?:(?:github|gh|gitlab|slack|npm|azure|id)[_-]?)?token)'
)
_CREDENTIAL_FIELD = re.compile(_FIELD, re.IGNORECASE | re.ASCII)
_ASSIGNMENT = re.compile(
    rf"""(?P<label>(?<![\w-]){_FIELD}["']?[ \t]*(?:=(?!=|>)|:(?!:))[ \t]*)"""
    # A bare value followed by a call is an expression, not a literal credential.
    r"""(?P<value>"(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*'|"""
    r"""(?!=)(?>[^\s,;"'<>{}\[\]&()]+)(?![ \t]*\())""",
    re.IGNORECASE | re.ASCII
)
_AUTHORIZATION = re.compile(
    r'(?P<scheme>(?<![\w-])(?:Bearer|Basic)[ \t]+)'
    r'(?P<value>[A-Za-z0-9._~+/-]{6,}={0,2})(?![\w.~+/-])', re.IGNORECASE
)
_AUTH_HEADER = re.compile(
    r"""(?P<label>(?<![\w-])(?:proxy-)?authorization["']?[ \t]*[:=][ \t]*["']?"""
    r"""(?:Bearer|Basic)[ \t]+)(?P<value>[A-Za-z0-9._~+/-]+={0,2})(?![\w.~+/-])""",
    re.IGNORECASE
)
_STRUCTURED_AUTHORIZATION = re.compile(r'^(?P<scheme>Bearer|Basic)[ \t]+', re.IGNORECASE)
_URL_PASSWORD = re.compile(
    r'(?P<prefix>[A-Za-z][A-Za-z0-9+.-]{0,24}://[^:/\s@]{1,200}:)'
    r'[^@\s/?#"\']+@'
)
_PRIVATE_KEY = re.compile(
    r'(?P<start>-----BEGIN (?P<label>(?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?)-----)'
    r'(?:\r?\n|\\r?\\n)?(?:(?!-----BEGIN )[\s\S])*?'
    r'(?P<end>-----END (?P=label)-----)'
)
_KNOWN_TOKEN = re.compile(
    r'(?<![A-Za-z0-9_-])(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|'
    r'sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|(?:AKIA|ASIA)[A-Z0-9]{16}|'
    r'AIza[A-Za-z0-9_-]{35}|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}|'
    r'xox[baprs]-[A-Za-z0-9-]{10,}|eyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{8,})'
    r'(?![A-Za-z0-9_-])'
)
_REFERENCES = ('$', 'env.', 'process.env.', 'os.environ', 'os.getenv', 'config.', 'secrets.')
_NON_VALUES = frozenset({
    'null', 'none', 'undefined', 'true', 'false', 'string', 'str', 'number', 'boolean', 'required', 'optional',
})
_NATIVE_LABELS = frozenset({
    'id', 'sessionID', 'parentID', 'messageID', 'callID', 'modelID', 'providerID', 'agentID',
})
_NUMERIC_PASSWORD = re.compile(r'(?:[a-z][a-z0-9_-]{0,62}[_-])?(?:password|passwd|pwd)', re.I | re.ASCII)


def _mask_assignment(match):
    value = match['value']
    quoted = value[0] in ('"', "'")
    inner = value[1:-1] if quoted else value
    if not inner or inner.startswith(_REFERENCES) or (not quoted and inner.casefold() in _NON_VALUES):
        return match[0]
    return match['label'] + (value[0] + _MASK + value[-1] if quoted else _MASK)


def _mask_authorization(match):
    if match['value'].casefold() in {'authentication', 'authorization', 'credentials'}:
        return match[0]
    # Generic Basic/Bearer prose is common; recognize credential syntax, not words.
    value = match['value']
    if not any(char.isdigit() or char in '._~+/=-' for char in value) and not (
        any(char.isupper() for char in value) and any(char.islower() for char in value)
    ):
        return match[0]
    return match['scheme'] + _MASK


def mask_text(value):
    if 'PRIVATE KEY' in value:
        value = _PRIVATE_KEY.sub(lambda m: f"{m['start']}\n{_MASK}\n{m['end']}", value)
    if '://' in value:
        value = _URL_PASSWORD.sub(lambda m: m['prefix'] + _MASK + '@', value)
    if ':' in value or '=' in value:
        value = _ASSIGNMENT.sub(_mask_assignment, value)
        value = _AUTH_HEADER.sub(lambda m: m['label'] + _MASK, value)
    return _KNOWN_TOKEN.sub(_MASK, _AUTHORIZATION.sub(_mask_authorization, value))


def mask_session(data, check):
    """Keep native keys, types and layout; redact only credential-bearing values."""
    visited = 0

    def visit(value, key=''):
        nonlocal visited
        visited += 1
        if visited % 256 == 0:
            check()
        if isinstance(value, dict):
            return {name: visit(item, name) for name, item in value.items()}
        if isinstance(value, list):
            return [visit(item, key) for item in value]
        if key in _NATIVE_LABELS:
            return value
        if key.casefold() in ('authorization', 'proxy-authorization') and isinstance(value, str) and value:
            scheme = _STRUCTURED_AUTHORIZATION.match(value)
            return (scheme[0] if scheme else '') + _MASK
        if _CREDENTIAL_FIELD.fullmatch(key):
            if isinstance(value, str) and value and not value.startswith(_REFERENCES):
                return _MASK
            if type(value) in (int, float) and _NUMERIC_PASSWORD.fullmatch(key):
                return type(value)(0)
        return mask_text(value) if isinstance(value, str) else value

    check()
    return visit(data)
