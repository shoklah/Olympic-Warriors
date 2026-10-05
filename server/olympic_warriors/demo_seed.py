"""
The answers of a real registration form, kept as a local seed for the demo edition: the form is
read once (`build_demo_seed`) and `seed_demo_edition` then needs only the seed. The seed holds
real people's private answers (their wishes are confidential), so it is a gitignored file, never
committed.
"""

import json
import re
import unicodedata
from collections import namedtuple
from pathlib import Path

import pandas as pd

from django.conf import settings
from django.core.management.base import CommandError

from olympic_warriors import registration

SEED_FILE = "demo-seed.json"


def seed_path():
    """Where the seed lives: DEMO_SEED_PATH, else next to manage.py."""
    return Path(getattr(settings, "DEMO_SEED_PATH", None) or Path(settings.BASE_DIR) / SEED_FILE)


# A clause that says who not to be with (on accent-free lower case): "ne pas être avec X",
# "pas avec X", "éviter X", "je ne veux pas être avec X". "Je ne veux pas être le boulet" is not one.
AVOIDANCE = re.compile(
    r"(?:\bpas|\bjamais)\s+(?:etre\s+|me\s+mettre\s+|en\s+equipe\s+)*avec\b"
    r"|\beviter\b|\bsurtout\s+pas\b"
)
CLAUSES = re.compile(r"(?<=[.!?;])\s+|\n+")
WISH_LIMIT = 500


def _plain(text):
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def split_wishes(text):
    """
    (team_with, team_avoid) of the form's single wishes question, which the in-app form asks as
    two. A text with no clause about who to avoid is all « with » and one that is all about
    avoiding is all « avoid », both left as written; a mix is split clause by clause.
    """
    clauses = [c for c in CLAUSES.split(text) if c.strip()]
    avoid = [c for c in clauses if AVOIDANCE.search(_plain(c))]
    if not avoid:
        return text[:WISH_LIMIT], ""
    if len(avoid) == len(clauses):
        return "", text[:WISH_LIMIT]
    kept = [c for c in clauses if c not in avoid]
    return " ".join(c.strip() for c in kept)[:WISH_LIMIT], " ".join(c.strip() for c in avoid)[:WISH_LIMIT]


FormRow = namedtuple("FormRow", "frequency history team_with team_avoid global_level")


def read_form(source, label=None):
    """
    {username: FormRow} of a registration form CSV, given as a path or an open file; `label` names
    it in the errors (the path by default).
    """
    label = label or source
    try:
        df = pd.read_csv(source)
        extras = registration.resolve_extras(df)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise CommandError(f"Cannot read the registration form {label}: {exc}") from exc
    if registration.NAME_HEADER not in df.columns or not extras:
        raise CommandError(f"{label} has no usable registration form columns.")
    level_columns = [h for h in df.columns if str(h).strip().startswith(registration.GLOBAL_LEVEL_PREFIX)]
    rows = {}
    for _, row in df.iterrows():
        try:
            username = registration.parse_name(row[registration.NAME_HEADER])[2]
        except ValueError:
            continue
        get = lambda key: registration.clean_text(row[extras[key]]) if key in extras else ""
        team_with, team_avoid = split_wishes(get(registration.WISHES))
        level = pd.to_numeric(row[level_columns[0]], errors="coerce") if level_columns else None
        rows[username] = FormRow(
            registration.parse_frequency(row[extras[registration.FREQUENCY]])
            if registration.FREQUENCY in extras else "",
            get(registration.SPORTS),
            team_with,
            team_avoid,
            int(level) if level is not None and 1 <= level <= 10 else None,
        )
    return rows


def save_seed(rows, path):
    """Writes {username: FormRow} as JSON (names kept, ids sorted by username)."""
    document = {"rows": {username: row._asdict() for username, row in sorted(rows.items())}}
    Path(path).write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")


def load_seed(path):
    """{username: FormRow} of a seed file, or CommandError when it cannot be read."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        return {username: FormRow(**row) for username, row in document["rows"].items()}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CommandError(f"Cannot read the demo seed {path}: {exc}") from exc
