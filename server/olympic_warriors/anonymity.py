"""
The name a public payload shows for a user: the real one, or an anonymous one once the
person deleted their account (UserProfile.anonymized). The real name stays in the database;
only what is served changes, so an organiser can undo it.
"""

ANONYMOUS_NAMES = ("Joueur", "anonyme")


def shown_names(user):
    """(first_name, last_name) to serve for `user`. Reads the loaded `profile` relation, so
    callers that serve many users join it (`select_related("user__profile")`); a missing row
    reads as not anonymized."""
    profile = getattr(user, "profile", None)
    if profile is not None and profile.anonymized:
        return ANONYMOUS_NAMES
    return (user.first_name, user.last_name)
