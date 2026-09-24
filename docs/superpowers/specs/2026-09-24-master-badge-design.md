# Master badge

> **Built 2026-09-24.** Extends the player badges design spec (catalogue, "Disciplines")
> and the badge collection spec ("Families").

## Goal

A discipline badge next to `specialist`: `master` goes to the people who won a discipline
**every time it was held**. Unlike every other badge it is a title held, not earned for
good: the next edition of that discipline that the person does not win takes it away.

## Rule

| Code | FR | EN | Rule | Repeat | Metal | Icon |
|---|---|---|---|---|---|---|
| `master` | Maître | Master | Won every edition of the sequence that ranked the discipline, at least 2 of them | one per discipline, held until lost | gold | A martial arts belt, knotted, its two ends hanging |

- **An edition of a discipline** is an edition of the sequence where a discipline of that
  name has a ranked result (`ResultStanding.ranking` above 0), so revealed and scored, as
  for the other discipline badges. Disciplines are matched across editions by name. A
  hidden or unscored discipline ranks nothing: that edition neither extends nor breaks the
  run, so a badge never leaks a hidden result. A hand-ranked edition has no results and
  does not count either.
- **Winning it** means being seated on a valid team ranked 1st there. A shared 1st place
  is a win. Two disciplines of one name in one edition are two events, and both must be
  won.
- **Every edition**, not only those the person played: a person who missed an edition of
  the discipline, before their first participation or after, did not win it.
- **At least 2 editions** (`MASTER_EDITIONS` in `badges.py`). With one, `master` would be
  a plain discipline win, which the gods already reward.
- **Earned at** the edition that completed it, the second edition of the discipline.
  The row stays the same while the person keeps winning, so its `created_at` and an
  organiser's revocation (`is_active` off) survive.
- **Lost** when a later edition of the discipline finishes and the person did not win it,
  played or missed. The rule is judged on the whole sequence, not up to each edition as
  every other rule is, so `earned()` stops returning it and the next refresh deletes the
  row. A lost title cannot come back without a correction of past data, since one edition
  was not won. An unfinished edition is not in the sequence yet, so the title is kept
  until the edition is over and the refresh runs (the nightly cron job, the Edition
  action or an import).

## Build

- `Badge.Codes.MASTER` after `SPECIALIST`, so 62 codes; migration `0035` updates the
  field's choices. `Badge.discipline` holds its discipline name, like `specialist`.
- `badges.py`: `_held(results)` gives, per discipline name, each edition of the sequence
  that ranked it with its winning teams, from the same `Standings.disciplines_of` data as
  the other discipline rules, so no query is added (`BADGES_QUERIES` does not change).
  `_masters(h, results)` yields the badge, called from `_disciplines`.
- `refresh()` needs no change: it already deletes the rows no longer earned.
- Front: `master: 'gold'` in `BADGES`, after `specialist` in the `disciplines` family (9
  codes), a glyph `img/badges/master.svg`, and `badge.master.name`/`.rule` in both
  dictionaries. The rule text says it can be lost. In the sheet, `badgeDetail` gives the
  discipline then « depuis 2022 » / "since 2022" (`badge.since`, the edition that
  completed it), since the title is held rather than dated.

## Tests

- `test_badges.py`, `TestDisciplines`: earned at the second edition, one edition is not
  enough, lost at the next edition not won (kept while that edition is unfinished), lost
  to a missed edition, the editions before the person's first count, editions without the
  discipline and hidden ones do not count, a shared 1st place is a win, two disciplines of
  one name are two events, one badge per discipline. `MASTER` is among the
  `DISCIPLINE_CODES` that a hidden or hand-ranked edition never gives. The discipline
  helpers moved into a `DisciplineWorld` mixin for reuse.
- `test_badge_refresh.py`, `TestMasterRefresh`: a title held on keeps its row (and its
  revocation), a title lost is deleted and nothing else is.
- Front: `BADGE_CODES`, the family sizes, the catalogue total of 62 in the collection and
  profile tests, and `badgeDetail` for `master` in English and French.
