# Badge progress: a bar in the badge sheet

## Goal

The badge sheet says what a badge needs (« Jouer 3, 5 puis 10 éditions ») and, for a tiered
badge, the next goal (« Prochain niveau : 10 éditions »), but never how far the person is.
This spec adds a **progress bar** to the sheet of every badge whose rule is a count:
« 7 / 10 éditions ». The progress is stored by the badge refresh, in the same pass as the
badges, so after a refresh a bar and the badges always agree.

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
   each threshold, lit once this bar's count reaches it (decision 9).
5. **Streaks show the current run**, falling back to 0 after a break, with the best run in
   a quiet note under the bar.
6. **Out of reach, no bar**: once a badge can no longer be earned (eternal-second after a
   win, lucky-charm after an early edition off the podium, argonaut for anyone who missed
   the first edition), the bar gives way to a muted « Plus atteignable » line.
7. **Per discipline, partner or edition, the closest one, named**: « 2 / 3 victoires ·
   Relais », « 2 / 3 éditions ensemble avec Léa Martin », « 2 / 3 épreuves gagnées en 2025 ».
8. **Earned means done**: a non-tiered badge's bar goes once it is earned (the sheet keeps
   its years); a tiered badge keeps its track until tier 3, then shows it full with
   « Niveau maximum ». Comrades is the exception (decision 11).

Decisions taken while reviewing the spec (2026-09-30):
9. **Ticks light as the fill reaches them**, not as the tiers are held, so a tick never
   contradicts its bar: ever-present with a current run of 1 lights none (its best run in
   the note), a specialist bar for Darts at 2 lights only the 2, whatever Relay holds. The
   tiers held stay on the medallion's pips and the « Niveau 2 » entry lines. The one
   exception is a badge at its top tier, whose track is full (decision 8): ever-present
   held at tier 3 shows a full track whatever the current run.
10. **The refresh runs the morning after an edition.** The cron runs daily, but
    `refresh_badges --if-due` refreshes only when an edition has finished since the last
    refresh, or the last refresh is a month old; badges and bars are fresh the morning after
    every edition, a correction of past data still lands within a month, and the rest of the
    year nothing is recomputed daily. **Only the first morning** (Hugo, 2026-09-30): results
    revealed or corrected after that wait for the organisers' action « Recalculer les
    badges » or the 30-day fallback, so CLAUDE.md's « run the action once an edition is
    over » stays, as « run the action once the last results are in ».
11. **Comrades keeps a bar toward the next partner**: earned once per partner, like
    specialist per discipline, it shows the closest partner still below 3 for as long as
    there is one, earned or not.
12. **`rem` for what sits in text**: every medallion and the avatars beside a name. The
    profile header's portrait (96/128px) and the photo editor's preview (160px) are pictures,
    not text-sized marks, and stay in `px`.

Taken without asking (say if you disagree):
- The bar is `aria-hidden`; the count line carries the meaning, its fraction read out as
  « 7 sur 10 » (§ The sheet), so screen readers read the sentence everyone sees.
- A `BadgeProgress` table, diffed by the refresh like the badges, so a second refresh
  writes nothing.
- The sheet is public, so no line says « vous »: « Plus atteignable : déjà champion d'une
  édition », not « vous avez déjà gagné ».
- Every person gets their rows, zeros included, even one whose only edition is still
  running, so a newcomer's sheet shows « 0 / 3 éditions » for Vétéran rather than nothing
  (once a refresh has run since they joined: § Deploying).
- The count lines are plain strings, not plurals: every target is at least 2 and a count
  shown without a target (at the top tier) at least 4, so « 1 / 3 éditions » and « 0 / 3
  éditions » are always right.
- When every discipline won is at 4 wins or more, specialist shows the best one, full,
  « Niveau maximum ».
- Where a progress entry is shown, an earned tiered badge's entry lines drop their goal line
  (« Prochain niveau », or « Niveau maximum » at the top tier), which the bar now says,
  except specialist's, whose entries are one per discipline while the bar follows one of
  them.

Changes from the independent review (2026-09-30), none of which moves a decision above:
on-the-rise's counter floored at 0 (it read −1 after an unranked edition); ever-present's
state follows its best run at the top tier; the raw counters and the agreement test made
precise; rows built from the `History`'s own people (no extra query); argonaut's row only
once out of reach; the count line's keys, the tiered fill colour, the sheet's `progress`
prop and its fallback, the showcase's duplicated pip floor, the partner's photo join, the
deploy steps, `PROGRESS_CODES` and the rules reading `PROGRESS_TARGETS`, `--if-due` on Paris
dates in `badges.py`, and `RefreshReport.progress`.

## The 20 codes with progress

Every counter reads the same `History` as the rules (`badges.history`): the finished active
editions of the sequence, counted participations, revealed contested results, played
games. **Now** means after the last edition of the sequence. The people are the
`History`'s `users`, every user with an active `Player` in an active edition, running
editions included (the set `profiles.person_ids()` returns, already loaded by `_load`, so
no query is added). A person without a finished edition yet has no seat: all their
counters are 0, and argonaut is out of reach once the first edition is over.

| Code | Counter | Target | Detail | Out of reach |
|---|---|---|---|---|
| `veteran` | editions played | 3 / 5 / 10 | | |
| `ever-present` | current run of editions in a row, best run in `best` | 4 / 6 / 8, above `best` | | |
| `networker` | distinct teammates | 5 / 10 / 20 | | |
| `specialist` | editions won in one discipline (by name): the one closest to its next tier | 2 / 3 / 4 | its name | |
| `all-rounder` | distinct disciplines won (by name) | 3 / 5 / 8 | | |
| `legend` | editions won | 3 | | |
| `full-set` | medal colours won (1st, 2nd, 3rd) | 3 | | |
| `decathlete` | disciplines (by name) with a podium, in editions of at least 4 teams | 10 | | |
| `olympus` | gods with a discipline won | 9 (`len(GODS)`) | | |
| `back-to-back` | current run of editions won, best in `best` | 2 | | |
| `threepeat` | same run | 3 | | |
| `dynasty` | same run | 4 | | |
| `podium-regular` | current run of podiums, best in `best` | 3 | | |
| `on-the-rise` | current run of rises in the ranking, best in `best` | 2 | | |
| `reign` | current run at 1st of the all-time table, best in `best` | 3 | | |
| `comrades` | editions shared with one person: the partner closest to 3 among those below 3 | 3 | the partner | |
| `clean-sweep` | discipline wins in one edition: the best edition | 3 | its year | |
| `eternal-second` | 2nd places | 2 | | once an edition is won |
| `lucky-charm` | podiums among the first three counted editions | 3 | | once one of the first three counted is off the podium |
| `argonaut` | (no counter) | | | once the first edition is over and the person was not in it |

Each counter is the rule's own number, computed next to it (`_runs`, `_career_of`,
`_loyalty`, `_teammates`, `_hall_of_fame`, `_disciplines_of` already keep most of them):

- **on-the-rise**: the rule's `rise` is 1 on the first ranked edition of a run and 0 after an
  unranked or missed edition, so the counter is `max(rise − 1, 0)` (« 1 / 2 » after one
  rise, never −1) and `best` the highest such value over the sequence.
- **reign**: read from `_hall_of_fame`'s own `reign` counter (its best run kept beside it),
  so the tables are not replayed a second time.
- **specialist**: the raw counter is {discipline name: editions won}, as the rule counts
  (`won_times`, one per edition whatever the number of disciplines of that name won there).
  The row shows the name with the most wins below 4, then the latest edition won, then the
  name (`profiles._sort_key`); every name at 4 or more: the most wins, then the latest, then
  the name, shown full. No win: value 0, no discipline.
- **comrades**: the raw counter is {partner id: editions shared}. The row shows the partner
  with the most editions shared below 3, then the latest edition shared, then the last
  name, first name and id (`_sort_key`, as `_grouped` orders partners). No teammate at all:
  value 0, no partner.
- **clean-sweep**: the raw counter is {sequence index: discipline wins}, counting results
  won as the rule does (`len(wins)`, two disciplines of one name counting twice). The row
  shows the best edition, the latest among equals, its year set; no win: value 0, no year.
- **full-set**: the count of distinct places among 1, 2 and 3 (`len(places)`); the rule
  keeps comparing with `{1, 2, 3}`.
- A value of 0 never carries a discipline, a partner or a year.

**Veteran counts finished editions**, like every badge: while an edition runs, the sheet
can say « 2 / 3 éditions » beside a profile whose « Éditions » count already reads 3.

### The raw counters and the rules agree

`_counters(h)` returns each person's raw counters (the dicts above, the streaks' current
and best runs, the out-of-reach flags), before any row is dropped; `compute()` turns them
into rows. Since a counter is only ever computed for *now*, their agreement with the rules is
tested through time: `World` gets a `tearDown` (it is the mixin every test class of
`test_badges.py` builds its data with, `DisciplineWorld` included), `assert_counters_agree()`,
which replays whatever the test built: for each active edition's `end_date` + 1 day in
turn, it takes `history(date)`, the rules' earned set and `_counters(h)`, and checks for
every person, L being the last edition of that sequence:

- **tiered**: the tier of the counter is the highest tier earned of that code; per
  discipline name for specialist (the tier of `wins[name]` is the highest earned with that
  discipline); ever-present from `best`, not the current run;
- **counts that can jump** (legend, full-set, decathlete, olympus): earned exactly when the
  counter reaches the target;
- **streaks** (back-to-back, threepeat, dynasty, podium-regular, on-the-rise, reign): the
  current run equals the target exactly when the badge was earned at L;
- **per key**: comrades earned with a partner exactly when that partner's count reaches 3;
  clean-sweep earned at an edition exactly when its count reaches 3;
- **the two that can close** (eternal-second, lucky-charm): out of reach means not earned;
  reachable and not earned means below the target; earned means the counter reached it;
- **argonaut**: out of reach exactly when the first edition is over and the badge is not
  earned.

## Backend

### `BadgeProgress` (migration `0039`)

`models/BadgeProgress.py`, exported from `models/__init__.py`, not in the admin (it is
recomputed at every refresh; an organiser acts on the badges, not on the bars):

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

`Badge.Codes.choices` is then shared by three fields (`Badge.code`, `UserProfile.showcase`,
`BadgeProgress.code`): a catalogue change migrates all three.

The **target** is not stored: it follows from the code and the count, so each threshold
keeps one home per side, with no copy in the table to fall out of step:

- **tiered**: the first threshold above `value` (above `best` for ever-present, since only a
  run longer than the best gives a new tier: tier 2 held from a run of 6 and a current run
  of 5 read « 5 / 8 »); past the top one the badge is at its **top tier**: `value` at 10 or
  more for veteran, `best` at 8 or more for ever-present.
- **non-tiered**: its fixed target.

On the server the thresholds stay in `VETERAN_TIERS` and the others, and the non-tiered
targets join them as `PROGRESS_TARGETS` (`{code: target}`, olympus `len(GODS)`), which the
rules then read instead of their literals (`TITLE_STREAKS` built from it, `titles ==`,
`seconds ==`, `rise ==` target + 1, `together ==`, `len(podiums) >=`, `len(wins) >=`,
`len(counted) ==`, podium-regular's run, `reign ==`); full-set keeps comparing with
`{1, 2, 3}` and a test pins its target to 3. On the front, `TIER_THRESHOLDS` is joined by
`PROGRESS_TARGETS` in `badges.js`, `badges.test.js` mirroring the server's, and
`PROGRESS_CODES` (the 20 codes, in catalogue order) lists which codes the sheet may find an
entry for and which keys they need.

Which rows exist, for every person of `h.users`:
- a **tiered** code: always (0 included), so a locked slot shows « 0 / 3 » and the top tier
  a full track;
- a **non-tiered** code: only while not earned (decision 8), with `reachable` false and no
  `value` once out of reach. "Earned" is the refresh's computed set: a revoked badge is
  still earned there, so it shows no bar, while its slot reads locked;
- **comrades**: unless it is earned and no partner is below 3 (decision 11), so a person
  without any teammate reads « 0 / 3 »;
- **argonaut**: only once out of reach (it has no counter to draw before), never once
  earned;
- no row for the 42 other codes.

An inactive edition is out of the history, as for the badges. `transfer.NOT_EXPORTED` gains
`BadgeProgress` (`test_transfer.py` fails otherwise): a real `import_edition` rebuilds it
with the badges.

### The refresh

`earned(today)` becomes one pass returning the badges **and** the progress rows from the same
`History` (`compute(today) -> (earned, progress)`; `earned()` stays as a thin wrapper for its
callers and the tests), so `BADGES_QUERIES` does not move. `refresh()` stores both in its
transaction, the progress diffed by `(user, code)`: rows no longer computed are deleted,
changed ones updated (`bulk_update`), new ones created (`bulk_create`), the others left
alone. A second run still writes nothing. `RefreshReport` gains `progress`, the progress
rows created, updated or deleted, which the command, the Edition action and
`import_edition`'s badge line print. Its own queries (`REFRESH_OWN_QUERIES`, 6 today) grow by
the read of the progress rows and one per write kind used, pinned in `test_badge_refresh.py`
as today.

`refresh_due(today)` in `badges.py` (1 query, today a Paris date as for `refresh(today)`)
says whether a refresh is due (decision 10), with `last` the Paris date of
`BadgeRefresh.refreshed_at`:
- no `BadgeRefresh` row or no `refreshed_at`: due;
- `last` at least 30 days before `today`: due (dates, not durations, so a daily cron at
  02:00 catches it on the 30th day, not the 31st);
- an active edition whose `end_date` is on or after `last` and before `today` (it finished
  since the last refresh): due; a refresh on the edition's last day leaves it due the next
  morning, and a missed cron night is caught up the next;
- otherwise not.

`refresh_badges --if-due` refreshes only when `refresh_due(paris_today())`, else prints
« Nothing to refresh (last refresh <Paris date and time>). » (the command speaks English, as
today) and writes nothing. The production crontab entry becomes daily,
`0 2 * * * … refresh_badges --if-due`, replacing the monthly one; the log gains a short line
a day. Plain `refresh_badges`, the Edition action and the import hook stay unconditional.
The command's docstring and help, `badges.py`'s module docstring, the comment on
`docker-compose.prod.example.yml`'s `server` service and CLAUDE.md drop "monthly".

A change the refresh does not see, such as deactivating or reactivating an edition, hides or
shows its badges at once (the profiles filter on it) while the bars wait for the next
refresh, which `--if-due` does not schedule for it: run the action after deactivating or
reactivating an edition, as after correcting past results.

### The payload

`GET /profile/<id>/` gains `progress`, from `badges.progress_entries(user_id)` (1 query, the
person's rows with `select_related("partner__profile")` as `_shown_rows()` does, so the
partner's photo costs nothing):

```json
"progress": [
  {"code": "eternal-second", "value": null, "best": null, "reachable": false,
   "discipline": null, "partner": null, "year": null},
  {"code": "veteran", "value": 7, "best": null, "reachable": true,
   "discipline": null, "partner": null, "year": null},
  {"code": "comrades", "value": 2, "best": null, "reachable": true, "discipline": null,
   "partner": {"id": 12, "first_name": "Léa", "last_name": "Martin", "photo": null},
   "year": null}
]
```

In catalogue order (`CATALOGUE_ORDER`), `discipline` null for an empty one, the partner as
in the badge entries (never the username). `/profiles/` rows carry no progress. The query
count of `/profile/<id>/` becomes `PROFILES_QUERIES + 1` (plus `profile_record()`'s 3 per
running edition), pinned in `test_profiles.py`; the OpenAPI schema describes the entries
with a serializer, as the badge entries are; `test_showcase.py`'s walk of the public
payloads for `PRIVATE_KEYS` covers a profile with a comrades progress row.

### Deploying

`migrate` (`0039`), then run `refresh_badges` once (or the action): the table starts empty,
and `--if-due` would otherwise leave every sheet without a bar until the next edition ends
or the month runs out. Replace the host's monthly crontab line with the daily `--if-due`
one. A person added since the last refresh (a new registration form, say) has no rows, and
their sheets keep today's lines, until the next refresh.

## Front

### The sheet

The page passes `progress={profile.progress ?? []}` to `BadgeCollection` and to the
interactive `Showcase`, which each pass it to their `BadgeSheet`. The sheet looks up the
slot's code with `progressFor(progress, code)` (`badges.js`: the entry, or null). Without an
entry (an older API, a table not yet filled, a person added since the last refresh, or one
of the 42 codes without progress) it shows exactly today's lines, `badge.first.<code>`
included, so those keys stay. With one, a progress block sits right under the status line
(« Badge obtenu » / « Badge à débloquer »):

- **A tiered badge**: one track from 0 to the top threshold, the fill at `value` capped at
  it; a tick at each threshold, lit in its tier's metal (bronze, silver, gold) once `value`
  reaches it, `--line` before (decision 9). The fill takes the metal of the highest tick
  lit, `--muted` before the first. The count line: « 7 / 10 éditions », the target being
  the first threshold above `value` (above `best` for ever-present). At the top tier the
  track is full, every tick lit and the fill gold, and the line gives the count alone with
  « Niveau maximum »: « 12 éditions · Niveau maximum » (ever-present counts its `best`:
  « 9 éditions d'affilée · Niveau maximum », with no run note). The block replaces the
  locked slot's first-goal line (`badge.first.<code>`).
- **Any other countable badge**: a track from 0 to the target, filled in the badge's metal
  (`--accent` for a plain one), and the count line « 1 / 3 éditions gagnées ».
- **A streak** (ever-present below its top tier, the title and podium runs, on-the-rise,
  reign): under the count line, « Meilleure série : 2 » when `best` is above `value`.
- **A named candidate**: the name follows the unit, « 2 / 3 victoires · Relais » (the
  discipline translated, and before « · Niveau maximum » when both are there), « 2 / 3
  éditions ensemble avec Léa Martin » (`badge.with`, their 1.5rem `Avatar`, then a quiet
  link to their profile), « 2 / 3 épreuves gagnées en 2025 ».
- **Out of reach**: no track, one muted line per code, `badge.outOfReach.<code>`:
  « Plus atteignable : déjà champion d'une édition » (eternal-second), « Plus
  atteignable : une des trois premières éditions classées hors du podium » (lucky-charm),
  « Plus atteignable : réservé aux joueurs de la première édition » (argonaut).

The track is `aria-hidden`. The count line is one key per code, `badge.count.<code>`, whose
`{fraction}` the sheet fills twice, as the collection's family counts do: once with
`badge.fraction` « {n} / {target} » in an `aria-hidden` span, once with
`badge.fractionSpoken` « {n} sur {target} » in a visually hidden one; at the top tier
`{fraction}` is the count alone and the line is spoken as seen. The discipline, the year
and the partner follow outside both spans, so the partner's link is never inside
`aria-hidden`. The keys, in both dictionaries (`parity.test.js`):

| Key | Français | English |
|---|---|---|
| `badge.fraction` | {n} / {target} | {n} / {target} |
| `badge.fractionSpoken` | {n} sur {target} | {n} of {target} |
| `badge.count.veteran` | {fraction} éditions | {fraction} editions |
| `badge.count.ever-present` | {fraction} éditions d'affilée | {fraction} editions in a row |
| `badge.count.networker` | {fraction} coéquipiers | {fraction} teammates |
| `badge.count.specialist` | {fraction} victoires | {fraction} wins |
| `badge.count.all-rounder` | {fraction} épreuves gagnées | {fraction} disciplines won |
| `badge.count.legend` | {fraction} éditions gagnées | {fraction} editions won |
| `badge.count.full-set` | {fraction} places du podium | {fraction} podium places |
| `badge.count.decathlete` | {fraction} épreuves sur le podium | {fraction} disciplines on the podium |
| `badge.count.olympus` | {fraction} dieux | {fraction} gods |
| `badge.count.back-to-back`, `threepeat`, `dynasty` | {fraction} éditions gagnées d'affilée | {fraction} editions won in a row |
| `badge.count.podium-regular` | {fraction} podiums d'affilée | {fraction} podiums in a row |
| `badge.count.on-the-rise` | {fraction} progressions d'affilée | {fraction} rises in a row |
| `badge.count.reign` | {fraction} éditions en tête d'affilée | {fraction} editions on top in a row |
| `badge.count.comrades` | {fraction} éditions ensemble | {fraction} editions together |
| `badge.count.clean-sweep` | {fraction} épreuves gagnées | {fraction} disciplines won |
| `badge.count.eternal-second` | {fraction} deuxièmes places | {fraction} second places |
| `badge.count.lucky-charm` | {fraction} podiums | {fraction} podiums |
| `badge.bestRun` | Meilleure série : {n} | Best run: {n} |
| `badge.inYear` | en {year} | in {year} |
| `badge.outOfReach.eternal-second` | Plus atteignable : déjà champion d'une édition | Out of reach: already won an edition |
| `badge.outOfReach.lucky-charm` | Plus atteignable : une des trois premières éditions classées hors du podium | Out of reach: one of the first three ranked editions was off the podium |
| `badge.outOfReach.argonaut` | Plus atteignable : réservé aux joueurs de la première édition | Out of reach: only for the players of the first edition |

`badge.with` (« avec ») and `badge.topTier` (« Niveau maximum ») already exist.
`badges.test.js` checks every code of `PROGRESS_CODES` for its keys: `badge.count.<code>` for
the 19 with a bar, `badge.outOfReach.<code>` for the three that can close (argonaut has only
that one).

Nothing changes in the collection grid or on the showcase medallions: the bars live in the
sheet only.

### Look

- The track: 0.375rem high, `--radius` corners, `--line` behind, the fill as above; ticks
  0.625rem circles on the track, ringed in `--bg-raised` so they read over the fill.
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
any CSS length), so the rem ones are passed as strings (`size="2rem"`). Hairlines, gaps and
paddings stay in `px` (the ring's inner line, borders, the showcase buttons' 3px padding and
their gaps). The pips' `max(5px, …)` floor becomes `max(0.3125rem, …)` in `Badge.svelte` and
in the copy of that formula in `Showcase.svelte`'s `--showcase-hang` margin, so a hanging row
keeps its height at any default size (`Showcase.test.js` follows). The layout arithmetic
moves with it: five header medallions below 600px now take 5 × (2.5rem + 6px) plus four 6px
gaps, so with a large default font they can outgrow the phone's line; the header's showcase
keeps `flex-wrap: wrap` and the leaderboard row's showcase gets it below 600px. Checked in
Chromium at the default font size (pixel-identical to today) and at a 24px default on the
pages these sizes reach (`/players`, a profile's two tabs with a sheet open, a team page, the
header at 375, 800 and 1280px): no horizontal scroll, wrapping allowed.

## Tests

- Server:
  - `test_badges.py`: every counter on `World` histories (the streaks' current and best
    runs, a break, on-the-rise after an unranked edition reading 0, ever-present at the top
    tier with a short current run, the closest specialist discipline and comrades partner
    with their tie-breaks, clean-sweep's best edition, the three out-of-reach cases, comrades
    after a first partner and with none left below 3, a person with no finished edition,
    argonaut's row only once out of reach), the rows `compute()` keeps, and
    `assert_counters_agree()` in `World.tearDown` over every test's data; `BADGES_QUERIES`
    unchanged.
  - `test_badge_refresh.py`: progress stored, updated, deleted by the diff, a second run
    writing nothing, `RefreshReport.progress` (`a_report()` and the admin message follow),
    `REFRESH_OWN_QUERIES`, the import hook's line, `refresh_due` (no row, no date, 29 and 30
    days, an edition ending before, on and after the last refresh date, an inactive one) and
    the command with and without `--if-due`.
  - `test_profiles.py`: the payload, its order and the query count; `test_showcase.py`: the
    private keys; `test_transfer.py`: `NOT_EXPORTED`.
- Front:
  - `badges.test.js`: `progressFor`, `PROGRESS_TARGETS` mirroring the server's, the keys of
    every progress code.
  - `BadgeSheet.test.js`: a tiered track whose ticks light by its own count, its fill metal,
    ever-present's run below its best tier, the top tier full (ever-present with a short
    run included), a plain bar, a streak's best-run note, a named discipline, partner (the
    link outside the hidden fraction) and year, out of reach, the spoken fraction, no entry
    keeping today's lines, one French rendering.
  - The profile's `page.test.js` (the sheet opened from a slot and from the showcase shows the
    bar), with a progress fixture in `src/lib/fixtures/players.js`.
  - `Avatar.test.js`, `Badge.test.js` and `Showcase.test.js` for the `rem` sizes.

## Out of scope

- Bars in the collection grid or on the showcase.
- Live progress between two refreshes (the morning-after refresh narrows the gap to a
  night).
- Progress toward earning a repeatable badge again, comrades' next partner aside.
- The hall-of-fame placements (goat, top 3, top 10): they are positions, not counts.
