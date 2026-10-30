"""Verified OpenAI HTTPS trust, without importing Windows' intermediate cache.

CPython loads both CA and ROOT stores as OpenSSL trust anchors on Windows.
Trusted-first chain building can then prefer an expired cached intermediate
over the server's valid chain. Trust ROOT anchors instead; intermediates still
have to chain to one of them. No machine store or verification flags change.
"""
from __future__ import annotations

import ssl
import sys


def usage_ssl_context() -> ssl.SSLContext:
    if sys.platform != "win32":
        return ssl.create_default_context()
    roots = "".join(
        ssl.DER_cert_to_PEM_cert(der)
        for der, encoding, trust in ssl.enum_certificates("ROOT")
        if encoding == "x509_asn" and (trust is True or ssl.Purpose.SERVER_AUTH.oid in trust)
    )
    if not roots:
        # Never pass empty cadata: create_default_context would reload CA + ROOT.
        raise ssl.SSLCertVerificationError("No trusted Windows server authentication roots")
    context = ssl.create_default_context(cadata=roots)
    # Preserve OpenSSL's configured CA file/directory, including explicit env overrides.
    context.set_default_verify_paths()
    return context
