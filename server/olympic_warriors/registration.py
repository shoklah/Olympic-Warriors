"""
Parse a Google Forms registration export into player ratings.

The form wording changes every year, so columns are matched by stable
fragments (the bracketed criterion of each skill question, the prefix of the
global-level question) rather than by full header text. The skill set itself
changed once (2024 vs 2025 onwards), so each known set is a profile in
FORM_PROFILES and resolve_columns picks the profile whose criteria all match.
"""
import pandas as pd

NAME = "Name"
EMAIL = "Email"
GLOBAL_LEVEL = "Global Level"

NAME_HEADER = "Prénom et Nom"
EMAIL_HEADER = "Adresse e-mail"
GLOBAL_LEVEL_PREFIX = "Sur une échelle de 1 à 10, comment estimes-tu ton niveau global"

# Skill name -> PlayerRating identifier, weighting coefficient, and the French
# criterion that appears between brackets in the form header. One dict per
# form generation; profiles are tried in FORM_PROFILES order.
RATINGS_2025 = {
    "Cohesion and Team Spirit": {
        "id": "TEAM", "coef": 2, "criterion": "Cohésion et esprit d'équipe"
    },
    "Mobility": {"id": "MOB", "coef": 3, "criterion": "Souplesse et coordination"},
    "Accuracy and Aiming": {"id": "ACC", "coef": 2, "criterion": "Précision et lancer"},
    "Running and Speed": {"id": "SPD", "coef": 4, "criterion": "Course et vitesse"},
    "Endurance": {"id": "STMN", "coef": 4, "criterion": "Endurance longue durée"},
    "Cardio": {"id": "CARD", "coef": 4, "criterion": "Cardio"},
    "Cultural Knowledge": {"id": "CULT", "coef": 1, "criterion": "Culture générale"},
    "Strength": {"id": "STR", "coef": 3, "criterion": "Force (soulever, pousser, etc)"},
    "Explosiveness": {
        "id": "EXPL", "coef": 4, "criterion": "Explosivité (effort puissant en un temps court)"
    },
    "Strategy and Game Vision": {
        "id": "STRT", "coef": 2, "criterion": "Stratégie et vision de jeu"
    },
}

# The 2024 form: an "Observation et orientation" skill, endurance and cardio
# merged into one skill, and shorter "Culture" / "Force" labels.
RATINGS_2024 = {
    "Cohesion and Team Spirit": {
        "id": "TEAM", "coef": 2, "criterion": "Cohésion et esprit d'équipe"
    },
    "Observation and Orientation": {
        "id": "OBS", "coef": 1, "criterion": "Observation et orientation"
    },
    "Mobility": {"id": "MOB", "coef": 3, "criterion": "Souplesse et coordination"},
    "Accuracy and Aiming": {"id": "ACC", "coef": 2, "criterion": "Précision et lancer"},
    "Running and Speed": {"id": "SPD", "coef": 4, "criterion": "Course et vitesse"},
    "Endurance and Cardio": {"id": "STMN", "coef": 4, "criterion": "Endurance et cardio"},
    "Cultural Knowledge": {"id": "CULT", "coef": 1, "criterion": "Culture"},
    "Strength": {"id": "STR", "coef": 3, "criterion": "Force"},
    "Explosiveness": {
        "id": "EXPL", "coef": 4, "criterion": "Explosivité (effort puissant en un temps court)"
    },
    "Strategy and Game Vision": {
        "id": "STRT", "coef": 2, "criterion": "Stratégie et vision de jeu"
    },
}

# Latest profile first: a current form must never be mistaken for an older one.
FORM_PROFILES = {"2025": RATINGS_2025, "2024": RATINGS_2024}

# The current skill set, for callers that only care about the latest form.
RATINGS = RATINGS_2025


def _find_column(headers, predicate, label):
    """Return the single header satisfying predicate, None if absent, raise if several."""
    matches = [header for header in headers if predicate(header)]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous registration form column for {label!r}: {matches}")
    return matches[0] if matches else None


def _resolve_skills(headers, ratings):
    """Map each skill of a profile to its header; return (columns, missing needles)."""
    columns = {}
    missing = []
    for name, spec in ratings.items():
        needle = f"[{spec['criterion']}]"
        header = _find_column(headers, lambda h, needle=needle: needle in str(h), needle)
        if header is None:
            missing.append(needle)
        else:
            columns[name] = header
    return columns, missing


def resolve_columns(df):
    """
    Map internal column names to the DataFrame's actual headers.

    :param df: DataFrame read from the registration CSV.
    :return: (columns, ratings). columns is a dict {internal name: header} with
             NAME, GLOBAL_LEVEL, every skill of the matched profile, and EMAIL
             only when the form has an email column. ratings is the matched
             FORM_PROFILES entry, whose coefficients and identifiers apply.
    :raises ValueError: if a required column is missing or matched twice.
    Profiles are tried in FORM_PROFILES order and the first one whose skills
    all match wins. An ambiguous match (two headers for one column) raises
    immediately, while missing columns are collected and reported together
    against the profile with the fewest missing skills.
    """
    headers = list(df.columns)
    columns = {}
    missing = []

    name_header = _find_column(headers, lambda h: str(h).strip() == NAME_HEADER, NAME_HEADER)
    if name_header is None:
        missing.append(NAME_HEADER)
    else:
        columns[NAME] = name_header

    email_header = _find_column(headers, lambda h: str(h).strip() == EMAIL_HEADER, EMAIL_HEADER)
    if email_header is not None:
        columns[EMAIL] = email_header

    global_header = _find_column(
        headers, lambda h: str(h).strip().startswith(GLOBAL_LEVEL_PREFIX), GLOBAL_LEVEL_PREFIX
    )
    if global_header is None:
        missing.append(f"{GLOBAL_LEVEL_PREFIX}...")
    else:
        columns[GLOBAL_LEVEL] = global_header

    attempts = []
    for profile, ratings in FORM_PROFILES.items():
        skill_columns, skill_missing = _resolve_skills(headers, ratings)
        if not skill_missing:
            break
        attempts.append((len(skill_missing), profile, skill_missing))
    else:
        _, profile, skill_missing = min(attempts)
        raise ValueError(
            f"Missing registration form columns (closest form profile {profile!r}): "
            f"{missing + skill_missing}"
        )

    if missing:
        raise ValueError(f"Missing registration form columns: {missing}")
    columns.update(skill_columns)
    return columns, ratings


def parse_name(raw):
    """
    Split a "Prénom et Nom" cell into first name, last name, and username.

    Whitespace is stripped and collapsed. The first token is the first name;
    the remaining tokens, joined by a space, form the last name (may be empty).
    The username is every token concatenated and lowercased, which matches the
    scheme used by earlier editions so returning players keep their account.

    :raises ValueError: if the cell is blank or not a string (pandas NaN).
    """
    tokens = raw.split() if isinstance(raw, str) else []
    if not tokens:
        raise ValueError(f"Invalid participant name: {raw!r}")
    first_name = tokens[0]
    last_name = " ".join(tokens[1:])
    username = "".join(tokens).lower()
    return first_name, last_name, username


def compute_ratings(df, columns, ratings=RATINGS):
    """
    Rename resolved columns to internal names and add Weighted_Rating and
    Global_Rating columns using the historical formulas.

    :param df: DataFrame read from the registration CSV.
    :param columns: mapping returned by resolve_columns.
    :param ratings: the FORM_PROFILES entry returned by resolve_columns.
    :return: a new DataFrame with internal column names and the two ratings.
    :raises ValueError: if any rating is blank, non-numeric, or outside 1-10;
                        every invalid cell of the form is reported together.
    """
    df = df.rename(columns={header: internal for internal, header in columns.items()})

    problems = []
    for column in list(ratings) + [GLOBAL_LEVEL]:
        values = pd.to_numeric(df[column], errors="coerce")
        invalid = df[values.isna() | (values < 1) | (values > 10)]
        for index, row in invalid.iterrows():
            name = row[NAME]
            # 1-based spreadsheet row, header is row 1
            who = repr(name) if isinstance(name, str) else f"row {index + 2}"
            problems.append(f"{column!r} for {who}: {row[column]!r}")
        df[column] = values
    if problems:
        raise ValueError("Invalid ratings in registration form: " + "; ".join(problems))

    total_coef = sum(spec["coef"] for spec in ratings.values())
    weighted = sum(df[name] * spec["coef"] for name, spec in ratings.items()) / total_coef
    weighted = weighted.clip(lower=1, upper=10)

    # A weak self-assessment on the skills but a confident global estimate is
    # treated as under-reporting: multiply by 2.5 (historical rule).
    boost = (weighted < 4) & (df[GLOBAL_LEVEL] > 4)
    weighted = weighted.where(~boost, weighted * 2.5)
    df["Weighted_Rating"] = weighted

    df["Global_Rating"] = ((weighted + df[GLOBAL_LEVEL] * 4) / 5).clip(lower=1, upper=10).round(2)
    return df
