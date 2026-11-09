"""Bounded source-text redaction, not a shell parser or a secret-free guarantee.

Retain original bytes outside recognized value spans. Ambiguous credential syntax
is withheld, never reconstructed/executed. Callers enforce the input-size budget.
"""
import re


_NAME = (r"(?:[\w-]+[_-])?(?:api[_-]?key|access[_-]?key(?:[_-]?id)?|"
         r"(?:access|refresh|id|auth|session)[_-]?token|client[_-]?secret|"
         r"password|passwd|secret(?:[_-]?key)?|token|authorization|auth|cookie|credentials?|private[_-]?key)")
_LABEL = rf"(?<![\w.-])(?:--?|/|\$env:)?{_NAME}(?![\w.-])"
_CREDENTIAL = re.compile(_LABEL + r"(?=\s|[:=]|$)", re.I)
# Only self-contained literal arguments: no shell escapes, interpolation, adjacent
# quote segments, operators or line continuations. All other credential syntax
# falls through to the explicit withholding rule below.
_VALUE = r'''(?:"[^"`$\\\r\n]*"|'[^'`$\\\r\n]*'|[^\s'"`$\\;&|<>()]+)'''
_ARGUMENT = re.compile(
    rf"(?P<label>{_LABEL})(?P<separator>[ \t]*(?:=|:)[ \t]*|[ \t]+)"
    rf"(?P<value>{_VALUE})(?=$|\s|[;&|])", re.I)
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/@]+:[^\s/@]+@", re.I)
_URL_USERINFO = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\r\n/]*@", re.I)
_TOKEN = re.compile(r"\b(?:sk-|gh[pousr]_|github_pat_|AKIA|ASIA|gsk_)[\w-]+|"
                    r"\beyJ[\w-]+\.[\w-]+\.[\w-]+")
_WITHHOLD = (
    (re.compile(r"authorization\s*:|\bcookie\s*:|\bbearer\s", re.I),
     'Authentication header/token input withheld; safe value boundaries unavailable.'),
    (re.compile(r'-----BEGIN', re.I), 'Private-key/certificate block withheld.'),
    (re.compile(r'(?:^|\s)(?:-u|--user)\s', re.I),
     'User-credential input withheld; safe value boundaries unavailable.'),
    (re.compile(r'[\[<](?:redacted|masked)[\]>]', re.I), 'Source already contains masked input.'),
)


def redact(value):
    """Return (safe text or None, reason); never return input in a reason."""
    for pattern, reason in _WITHHOLD:
        if pattern.search(value):
            return None, reason
    spans = []
    for match in _ARGUMENT.finditer(value):
        spans.append((*match.span('value'), '[redacted]'))
    for match in _URL.finditer(value):
        start = match.start() + match[0].index('://') + 3
        spans.append((start, match.end() - 1, '[redacted]'))
    spans.extend((*match.span(), '[redacted]') for match in _TOKEN.finditer(value))
    # Removing whole recognized arguments from the check allows labels to remain
    # visible after redaction, without accepting a second unresolved credential.
    remainder = _ARGUMENT.sub('', value)
    remainder = _URL.sub('', remainder)
    remainder = _TOKEN.sub('', remainder)
    if _CREDENTIAL.search(remainder) or _URL_USERINFO.search(remainder):
        return None, "Sensitive argument withheld; safe value boundaries unavailable."
    if not spans:
        return value, ''
    # Overlapping URL/token/value spans form one redaction; no fragments survive.
    merged = []
    for start, end, _ in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    for start, end in reversed(merged):
        value = value[:start] + '[redacted]' + value[end:]
    return value, 'Sensitive argument/value redacted.'
