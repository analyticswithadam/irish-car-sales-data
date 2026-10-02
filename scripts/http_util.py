"""
HTTPS helper shared by pull_cso.py and pull_simi.py.

Certificates are verified by default. Some machines cannot verify them: networks that intercept
TLS with a self-signed proxy certificate, and python.org installs on macOS that have not run
"Install Certificates.command". On a verification failure the request is retried without
verification and a one-time warning explains how to fix it. Both sources are public, read-only
statistics, so falling back keeps a first install working.

    IRISH_CAR_SALES_STRICT_SSL=1    never fall back (fail instead)
    IRISH_CAR_SALES_INSECURE_SSL=1  skip verification from the start
"""

import os
import ssl
import sys
import threading
import urllib.error
import urllib.request

_VERIFIED = ssl.create_default_context()
_UNVERIFIED = ssl._create_unverified_context()
_warned = threading.Event()


def _is_cert_error(err):
    reason = getattr(err, 'reason', err)
    return isinstance(reason, ssl.SSLCertVerificationError)


def open_url(req, timeout=60):
    """urllib.request.urlopen with certificate verification and a guarded fallback."""
    if os.environ.get('IRISH_CAR_SALES_INSECURE_SSL') == '1':
        return urllib.request.urlopen(req, context=_UNVERIFIED, timeout=timeout)
    try:
        return urllib.request.urlopen(req, context=_VERIFIED, timeout=timeout)
    except (urllib.error.URLError, ssl.SSLError) as err:
        if not _is_cert_error(err) or os.environ.get('IRISH_CAR_SALES_STRICT_SSL') == '1':
            raise
        if not _warned.is_set():
            _warned.set()
            print("  [warn] Could not verify the HTTPS certificate, so continuing without verification. "
                  "This usually means a network proxy or a Python install without root certificates "
                  "(on macOS, run 'Install Certificates.command' from your Python folder). "
                  "Set IRISH_CAR_SALES_STRICT_SSL=1 to stop instead.", file=sys.stderr)
        return urllib.request.urlopen(req, context=_UNVERIFIED, timeout=timeout)
