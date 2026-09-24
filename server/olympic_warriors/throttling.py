"""
The login throttle: on the token endpoint, a claim link's POST and the admin login form, the
only throttled requests.
"""

import ipaddress

from rest_framework.throttling import SimpleRateThrottle


def client_key(ident):
    """
    The address a client is counted under. An IPv6 client counts by its /64, the smallest
    block a provider hands a subscriber, who could otherwise take a fresh address for every
    attempt; an IPv4 address written as IPv6 (::ffff:a.b.c.d, how Node reports an IPv4 peer)
    counts as that IPv4, not in the one /64 every IPv4 client would then share. Anything that
    is not an address is kept as it is.
    """
    try:
        address = ipaddress.ip_address(ident)
    except ValueError:
        return ident
    if address.version == 6:
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network((int(address), 64), strict=False))
    return str(address)


class LoginRateThrottle(SimpleRateThrottle):
    """
    Login attempts per client IP, at the "login" rate of DEFAULT_THROTTLE_RATES. Every
    request counts, failed or not, and a token does not exempt the caller: unlike DRF's
    AnonRateThrottle and ScopedRateThrottle, the key is the IP even for a logged-in user,
    so an account of any kind cannot buy unlimited guesses at another one's password.

    The IP is get_ident(): with NUM_PROXIES = 1 the last X-Forwarded-For entry, the one the
    hop in front of Django added (nginx, or the front forwarding its visitor), else REMOTE_ADDR.
    It only reads request.META, so the admin login form (ThrottledAdminAuthenticationForm in
    admin.py) counts its plain Django requests in the same buckets.
    """

    scope = "login"

    def get_cache_key(self, request, view):
        ident = client_key(self.get_ident(request))
        return self.cache_format % {"scope": self.scope, "ident": ident}


class ClaimRateThrottle(LoginRateThrottle):
    """
    The login bucket, on a claim link's POST only. Choosing a password through a link is a
    login attempt, so it counts with /auth/token/ and the admin login in the same per-IP
    budget (same scope, same rate). The GET is not counted: it answers only for a valid
    token, which cannot be guessed, and the claim page re-runs it after every refused POST,
    which would otherwise spend the budget twice per attempt. A function view has one
    throttle list for all its methods, hence the method check here.
    """

    def allow_request(self, request, view):
        if request.method != "POST":
            return True
        return super().allow_request(request, view)
