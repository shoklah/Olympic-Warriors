"""
Parse a Google Forms registration export into player ratings.

The form wording changes every year, so columns are matched by stable
fragments (the bracketed criterion of each skill question, the prefix of the
global-level question) rather than by full header text.
"""

NAME = "Name"
EMAIL = "Email"
GLOBAL_LEVEL = "Global Level"

NAME_HEADER = "Prénom et Nom"
EMAIL_HEADER = "Adresse e-mail"
GLOBAL_LEVEL_PREFIX = "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global"

# Skill name -> PlayerRating identifier, weighting coefficient, and the French
# criterion that appears between brackets in the form header.
RATINGS = {
    "Cohesion and Team Spirit": {"id": "TEAM", "coef": 2, "criterion": "Cohésion et esprit d'équipe"},
    "Mobility": {"id": "MOB", "coef": 3, "criterion": "Souplesse et coordination"},
    "Accuracy and Aiming": {"id": "ACC", "coef": 2, "criterion": "Précision et lancer"},
    "Running and Speed": {"id": "SPD", "coef": 4, "criterion": "Course et vitesse"},
    "Endurance": {"id": "STMN", "coef": 4, "criterion": "Endurance longue durée"},
    "Cardio": {"id": "CARD", "coef": 4, "criterion": "Cardio"},
    "Cultural Knowledge": {"id": "CULT", "coef": 1, "criterion": "Culture générale"},
    "Strength": {"id": "STR", "coef": 3, "criterion": "Force (soulever, pousser, etc)"},
    "Explosiveness": {"id": "EXPL", "coef": 4, "criterion": "Explosivité (effort puissant en un temps court)"},
    "Strategy and Game Vision": {"id": "STRT", "coef": 2, "criterion": "Stratégie et vision de jeu"},
}


def _find_column(headers, predicate, label):
    """Return the single header satisfying predicate, None if absent, raise if several."""
    matches = [header for header in headers if predicate(header)]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous registration form column for {label!r}: {matches}")
    return matches[0] if matches else None


def resolve_columns(df):
    """
    Map internal column names to the DataFrame's actual headers.

    :param df: DataFrame read from the registration CSV.
    :return: dict {internal name: header}. Contains NAME, GLOBAL_LEVEL, every
             key of RATINGS, and EMAIL only when the form has an email column.
    :raises ValueError: if a required column is missing or matched twice.
    """
    headers = [str(header) for header in df.columns]
    columns = {}
    missing = []

    name_header = _find_column(headers, lambda h: h.strip() == NAME_HEADER, NAME_HEADER)
    if name_header is None:
        missing.append(NAME_HEADER)
    else:
        columns[NAME] = name_header

    email_header = _find_column(headers, lambda h: h.strip() == EMAIL_HEADER, EMAIL_HEADER)
    if email_header is not None:
        columns[EMAIL] = email_header

    global_header = _find_column(
        headers, lambda h: h.startswith(GLOBAL_LEVEL_PREFIX), GLOBAL_LEVEL_PREFIX
    )
    if global_header is None:
        missing.append(f"{GLOBAL_LEVEL_PREFIX}...")
    else:
        columns[GLOBAL_LEVEL] = global_header

    for name, spec in RATINGS.items():
        needle = f"[{spec['criterion']}]"
        header = _find_column(headers, lambda h, needle=needle: needle in h, needle)
        if header is None:
            missing.append(needle)
        else:
            columns[name] = header

    if missing:
        raise ValueError(f"Missing registration form columns: {missing}")
    return columns
