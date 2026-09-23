"""
DRF throttle for the token endpoint, the only throttled view.
"""

from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """
    Login attempts per client IP, at the "login" rate of DEFAULT_THROTTLE_RATES. Every
    request counts, failed or not, and a token does not exempt the caller: unlike DRF's
    AnonRateThrottle and ScopedRateThrottle, the key is the IP even for a logged-in user,
    so an account of any kind cannot buy unlimited guesses at another one's password.

    The IP is get_ident(): with NUM_PROXIES = 1 the last X-Forwarded-For entry, the one the
    hop in front of Django added (nginx, or the front forwarding its visitor), else REMOTE_ADDR.
    """

    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
