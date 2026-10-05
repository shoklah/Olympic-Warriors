"""
Which email addresses are real. The organisers' own domain stands in for a missing address:
the registration import generates `<username>@olympicwarriors.com` for a player whose form had
none, and no mail sent there reaches the person. One definition for the import, the claim
mailing, the registration form and the invitations, so they cannot drift.
"""

INTERNAL_DOMAIN = "olympicwarriors.com"


def is_internal(email):
    """Whether `email` is at the organisers' own domain or one of its subdomains."""
    domain = (email or "").strip().rpartition("@")[2].lower()
    return domain == INTERNAL_DOMAIN or domain.endswith("." + INTERNAL_DOMAIN)


def usable_email(email):
    """A real address: not blank and not at the organisers' own domain."""
    email = (email or "").strip().lower()
    return bool(email) and not is_internal(email)
