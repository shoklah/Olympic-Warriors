# Badge progress: a bar in the badge sheet

## Goal

The badge sheet says what a badge needs (« Jouer 3, 5 puis 10 éditions ») and, for a tiered
badge, the next goal (« Prochain niveau : 10 éditions »), but never how far the person is.
This spec adds a **progress bar** to the sheet of every badge whose rule is a count:
« 7 / 10 éditions ». The progress is stored by the badge refresh, so a bar never disagrees
with the badges.

It also moves the badge and avatar sizes from `px` to `rem` (§ Sizes).

Decisions taken while grilling (2026-09-30):
1. **Every countable badge gets a bar**: the tiered ones, the counts that only grow, the
   streaks, the ones counted per discipline, partner or edition, and the two that can
   become impossible: 19 bars, plus argonaut's out-of-reach line, so 20 codes listed below;
   the 42 others get none.
2. **Public**: every visitor of a profile sees its bars, as they see its badges and their
   rarity. Progress is derived from public results.
3. **Stored at the badge refresh**, in the same pass and the same transaction as the
   badges, so a bar moves exactly when the badges move, and the refresh runs the morning
   after every edition (decision 10).
4. **One track with a tick per tier** for a tiered badge: 0 to the top threshold, a tick at
   each threshold, lit once this bar's count passes it (decision 9).
5. **Streaks show the current run**, falling back to 0 after a break, with the best run in
   a quiet note under the bar.
6. **Out of reach, no bar**: once a badge can no longer be earned (eternal-second after a
   win, lucky-charm after an early edition off the podium, argonaut for anyone who missed
   the first edition), the bar gives way to a muted « Plus atteignable » line.
7. **Per discipline, partner or edition, the closest one, named**: « 2 / 3 · Relais »,
   « 2 / 3 avec Léa Martin », « 2 / 3 en 2025 ».
8. **Earned means done**: a non-tiered badge's bar goes once it is earned (the sheet keeps
   its years); a tiered badge keeps its track until tier 3, then shows it full with
   « Niveau maximum ». Comrades is the exception (decision 11).

Decisions taken while reviewing the spec (2026-09-30):
9. **Ticks light as the fill passes them**, not as the tiers are held, so a tick never
   contradicts its bar: ever-present with a current run of 1 lights none (its best run in
   the note), a specialist bar for Darts at 2 lights only the 2, whatever Relay holds. The
   tiers held stay on the medallion's pips and the « Niveau 2 » entry lines.
10. **The refresh runs the morning after an edition.** The cron runs daily, but
    `refresh_badges --if-due` refreshes only when an edition has finished since the last
    refresh, or the last refresh is a month old; badges and bars are fresh the morning after
    every edition, a correction of past data still lands within a month, and the rest of the
    year nothing is recomputed daily.
11. **Comrades keeps a bar toward the next partner**: earned once per partner, like
    specialist per discipline, it shows the closest partner still below 3 for as long as
    there is one, earned or not.
12. **`rem` for what sits in text**: every medallion and the avatars beside a name. The
    profile header's portrait (96/128px) and the photo editor's preview (160px) are pictures,
    not text-sized marks, and stay in `px`.

Taken without asking (say if you disagree):
- The bar is `aria-hidden`; a visible count line carries the meaning (« 7 sur 10
  éditions »), so screen readers read the same sentence everyone reads.
- A `BadgeProgress` table, diffed by the refresh like the badges, so a second refresh
  writes nothing.
- The sheet is public, so no line says « vous »: « Plus atteignable : déjà champion d'une
  édition », not « vous avez déjà gagné ».
- Every person gets their rows, zeros included, even one whose only edition is still
  running, so a newcomer's sheet shows « Vétéran 0 / 3 » rather than nothing.
- The count lines are plain strings, not plurals: every target is at least 2 and a tier-3
  count at least 4, so « 1 / 3 éditions » is always right.
- When every discipline won is at 4 wins, specialist shows the best one, full, « Niveau
  maximum ».

## The 20 codes with progress

Every counter reads the same `History` as the rules (`badges.history`): the finished active
editions of the sequence, counted participations, revealed contested results, played
games. **Now** means after the last edition of the sequence. A person with no finished
edition yet (only a running one) has no seat in the `History` but gets rows all the same,
from `profiles.person_ids()`: zeros, and argonaut out of reach once the first edition is
over.

| Code | Counter | Target | Detail | Out of reach |
|---|---|---|---|---|
| `veteran` | editions played | 3 / 5 / 10 | | |
| `ever-present` | current run of editions in a row (best run in the note) | 4 / 6 / 8 | | |
| `networker` | distinct teammates | 5 / 10 / 20 | | |
| `specialist` | wins in one discipline: the one closest to its next tier (most wins below 4, then the latest win, then the name); every discipline at 4: the best, full | 2 / 3 / 4 | its name | |
| `all-rounder` | distinct disciplines won | 3 / 5 / 8 | | |
| `legend` | editions won | 3 | | |
| `full-set` | medal colours won (1st, 2nd, 3rd) | 3 | | |
| `decathlete` | disciplines with a podium, in editions of at least 4 teams | 10 | | |
| `olympus` | gods with a discipline won | 9 | | |
| `back-to-back` | current run of editions won (best in the note) | 2 | | |
| `threepeat` | same run | 3 | | |
| `dynasty` | same run | 4 | | |
| `podium-regular` | current run of podiums (best in the note) | 3 | | |
| `on-the-rise` | current run of rises in the ranking (best in the note) | 2 | | |
| `reign` | current run at 1st of the all-time table (best in the note) | 3 | | |
| `comrades` | editions shared with one person: the partner closest to 3 among those below 3 (then the latest edition shared, then the name), earned with others or not; none below 3: no bar | 3 | the partner | |
| `clean-sweep` | discipline wins in one edition: the best edition | 3 | its year | |
| `eternal-second` | 2nd places | 2 | | once an edition is won |
| `lucky-charm` | podiums among the first three counted editions | 3 | | once one of the first three is off the podium |
| `argonaut` | (no counter) | | | for anyone who missed the first edition |

`on-the-rise` counts rises, not editions: the rule's `rise` counter is 1 on the first
ranked edition of a run, so a rise count of `rise - 1` makes « 1 / 2 » after one rise.

The rules' earning conditions stay as they are. The counters are computed next to them
(`_runs`, `_career_of`, `_loyalty`, `_teammates`, `_tables`, `_disciplines_of` already keep
most of these counts), so each counter is the rule's own number. The agreement is tested
through time, since a counter is only ever computed for *now*: on every `World` history of
`test_badges.py`, `compute(today)` runs as of the day after each edition of the sequence in
turn, and at each step a tiered counter's tier is the highest tier earned so far, and a
non-tiered counter reaches its target exactly at the edition where the badge is earned (a
streak's current run, a count's total). The counters are tested raw, before the rows drop
what is earned.

## Backend

### `BadgeProgress` (migration `0039`)

```python
class BadgeProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badge_progress")
    code = models.CharField(max_length=32, choices=Badge.Codes.choices)
    value = models.PositiveIntegerField(null=True)   # null when out of reach
    best = models.PositiveIntegerField(null=True)    # streaks only: the best run
    reachable = models.BooleanField(default=True)
    discipline = models.CharField(max_length=100, blank=True, default="")
    partner = models.ForeignKey(User, null=True, on_delete=models.CASCADE, related_name="+")
    year = models.PositiveIntegerField(null=True)    # clean-sweep's edition
    class Meta:
        constraints = [UniqueConstraint(fields=("user", "code"), name="progress_unique")]
```

The **target** is not stored: it follows from the code and the count (the first threshold
above the count, or the top one past it; for ever-present the first above its best run,
since only a longer run than the best gives a new tier: level 2 held from a run of 6 and a
current run of 5 read « 5 / 8 »), so each threshold keeps one home per side, with
no copy in the table to fall out of step: `badges.py` (`VETERAN_TIERS` and the others, the
non-tiered targets joining them as `PROGRESS_TARGETS`) and the front's `TIER_THRESHOLDS`
(joined by `PROGRESS_TARGETS` too, `badges.test.js` mirroring the server's).

Which rows exist, for every person (`person_ids()`):
- a **tiered** code: always (0 included), so a locked slot shows « 0 / 3 » and tier 3 a full
  track;
- a **non-tiered** code: only while not earned (decision 8), with `reachable` false and no
  `value` once out of reach; comrades while a partner below 3 exists (decision 11);
- no row for the 42 other codes.

An inactive edition is out of the history, as for the badges. `transfer.NOT_EXPORTED` gains
`BadgeProgress`: a real `import_edition` rebuilds it with the badges.

### The refresh

`earned(today)` becomes one pass returning the badges **and** the progress from the same
`History` (`compute(today) -> (earned, progress)`; `earned()` stays as a thin wrapper for its
callers), so `BADGES_QUERIES` does not move. `refresh()` stores both in its transaction, the
progress diffed by `(user, code)`: rows no longer computed are deleted, changed ones
updated, new ones created, the others left alone. A second run still writes nothing.
`RefreshReport` gains `progress` (rows written), which the command and the Edition action
print.

`refresh_badges --if-due` (decision 10) refreshes only when it is due: an active edition
whose `end_date` falls on or after the Paris date of `BadgeRefresh.refreshed_at` and before
today in Paris (it finished since the last refresh), or a last refresh at least 30 days
old, or none at all; otherwise it prints « Rien à recalculer » and writes nothing. The
production crontab entry becomes daily, `0 2 * * * … refresh_badges --if-due`, replacing
the monthly one (the comment on `docker-compose.prod.example.yml`'s `server` service and
CLAUDE.md follow). Plain `refresh_badges`, the Edition action and the import hook stay
unconditional.

### The payload

`GET /profile/<id>/` gains `progress`, one query (the person's rows, `partner` joined):

```json
"progress": [
  {"code": "veteran", "value": 7, "best": null, "reachable": true,
   "discipline": null, "partner": null, "year": null},
  {"code": "comrades", "value": 2, "best": null, "reachable": true, "discipline": null,
   "partner": {"id": 12, "first_name": "Léa", "last_name": "Martin", "photo": null},
   "year": null},
  {"code": "eternal-second", "value": null, "best": null, "reachable": false,
   "discipline": null, "partner": null, "year": null}
]
```

In catalogue order. `/profiles/` rows carry no progress. The query count of `/profile/<id>/`
becomes `PROFILES_QUERIES + 1` (plus `profile_record()`'s 3 per running edition), pinned in
`test_profiles.py`.

## Front

### The sheet

`BadgeSheet` gains a progress block right under the status line (« Badge obtenu » /
« Badge à débloquer »), from the profile's `progress` entry for the slot's code, when there
is one (`progressFor(progress, code)` in `badges.js`):

- **A tiered badge**: one track from 0 to the top threshold, `value` capped at it; a tick at
  each threshold, lit in its tier's metal (bronze, silver, gold) once `value` reaches it,
  `--line` before (decision 9). The count line: « 7 / 10 éditions », the target being the
  first threshold above `value` (above `best` for ever-present), or « 12 éditions · Niveau
  maximum » past the top one. It replaces the locked slot's first-goal
  line (`badge.first.<code>`); the entry lines keep their per-entry goal (a specialist's
  other disciplines).
- **Any other countable badge**: a track from 0 to the target, filled in the badge's metal
  (`--accent` for a plain one), and the count line « 1 / 3 éditions gagnées ».
- **A streak**: under the count line, « Meilleure série : 2 » when the best run is above the
  current one.
- **A named candidate**: the name joins the count line, « 2 / 3 · Relais » (the discipline
  translated), « 2 / 3 avec Léa Martin » (a quiet link to their profile, their 24px
  `Avatar` first), « 2 / 3 en 2025 ».
- **Out of reach**: no track, one muted line per code, `badge.outOfReach.<code>`:
  « Plus atteignable : déjà champion d'une édition » (eternal-second), « Plus atteignable :
  une des trois premières éditions classées hors du podium » (lucky-charm), « Plus
  atteignable : réservé aux joueurs de la première édition » (argonaut).

The track is `aria-hidden` (`role` none); the count line is the text screen readers read,
so it says « sur » rather than « / » in its spoken form (a visually hidden « 7 sur 10
éditions » next to the `aria-hidden` « 7 / 10 »), as the collection's family counts do.

The count lines are per code, plain strings with `{n}` and `{target}` (no plural, see
above): `badge.count.veteran` « {n} / {target} éditions », `badge.count.networker` « {n} /
{target} coéquipiers », `badge.count.specialist` « {n} / {target} victoires », and so on for
the 19 codes with a bar, plus `badge.countMax.<code>` « {n} éditions · Niveau maximum » for
the five tiered ones and `badge.outOfReach.<code>` for the three that can become
impossible, both dictionaries (`parity.test.js`), each code of `PROGRESS_CODES` checked by
`badges.test.js` for its keys.

Nothing changes in the collection grid or the showcase: the bars live in the sheet only.

### Look

- The track: 0.375rem high, `--radius` corners, `--line` behind, the fill in the metal;
  ticks 0.625rem circles on the track, ringed in `--bg-raised` so they read over the fill.
- Width: the sheet's text column, so 100% of it (at most 20rem, centred like the rest of
  the sheet).
- With `prefers-reduced-motion` the fill does not animate (the global block covers it);
  otherwise it grows from 0 over 0.4s when the sheet opens.

## Sizes: `rem`, not `px`

`MedalRank` is sized in `rem` (`--medal-size: 1.9rem`) while `Badge` and `Avatar` are sized in
`px`. Browser zoom scales both, but a larger **default font size** (a browser or system
setting many people with low vision use) grows the text and not the `px` medallions, so a
20px badge ends up tiny beside a name set at 150%. `em` would follow each place's own font
size (a `.label` at 0.75rem would shrink a badge in it); `rem` follows only the person's
setting, the same everywhere.

So what sits in text moves to `rem` (decision 12), at the same rendered size at the
default 16px: every `--badge-size` (20px → 1.25rem, 40px → 2.5rem, 48px → 3rem, 56px →
3.5rem, the sheet's 64px → 4rem) and the avatars beside a name (24px → 1.5rem on the roster,
in the header pills and on a comrades line, 32px → 2rem on leaderboard rows). The profile
header's portrait (96/128px) and the photo editor's preview (160px, over a canvas that draws
pixels) stay in `px`. `Avatar`'s `size` prop keeps its meaning (a number is pixels, a string
any CSS length), so the rem ones are passed as strings (`size="2rem"`). Hairlines stay in
`px` (the ring's inner line, borders), and the pips' `max(5px, …)` floor becomes
`max(0.3125rem, …)`. The layout arithmetic moves with it: five header medallions are now
`5 × 2.875rem` and more, so with a large default font they can outgrow the phone's line;
the header's showcase keeps `flex-wrap: wrap` and the leaderboard row's showcase gets it
below 600px. Checked in Chromium at the default font size (pixel-identical to today) and at
a 24px default (no horizontal scroll, wrapping allowed).

## Tests

- Server: `test_badges.py` (every counter on `World` histories: the streaks' current and best
  runs, a break, the closest specialist discipline and comrades partner, clean-sweep's best
  edition, the three out-of-reach cases, comrades after a first partner, a person with no
  finished edition, the counter/rule agreement through time), `test_badge_refresh.py`
  (progress stored, updated, deleted with the diff, a second run writing nothing, the report,
  the import hook, `--if-due` due and not due in each case), `test_profiles.py` (the payload, the count), `test_transfer.py`
  (`NOT_EXPORTED`).
- Front: `badges.test.js` (`progressFor`, the keys of every progress code), `BadgeSheet.test.js`
  (a tiered track whose ticks light by its own count, ever-present's run below its best
  tier, « Niveau maximum », a plain bar, a streak's best-run
  note, a named discipline, partner and year, out of reach, nothing for a code without
  progress, one French rendering), the profile's `page.test.js` (the sheet opened from a slot
  and from the showcase), `Avatar.test.js`/`Badge.test.js` for the `rem` sizes.

## Out of scope

- Bars in the collection grid or on the showcase.
- Live progress between two refreshes (the morning-after refresh narrows the gap to a
  night).
- Progress toward earning a repeatable badge again, comrades' next partner aside.
- The hall-of-fame placements (goat, top 3, top 10): they are positions, not counts.
