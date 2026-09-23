# Player badges

## Goal

Step 3 of the player profiles roadmap (see the player profiles design spec): badges that
people earn from their editions, their streaks, their teammates, their discipline and game
results and their place in the all-time table. The badges are stored, shown on the profile,
and organisers can give a few by hand.

Decisions taken while brainstorming (2026-09-23):

1. **Streaks run over consecutive editions** of the event. A calendar year without an
   edition does not break a streak, but an edition the person missed does.
2. **The teasing badges stay**: wooden spoon, Icarus and Janus.
3. **Hand-ranked editions** have a final order but no results and no games, so for now
   they only give the edition, streak, loyalty, teammate and hall of fame badges.
4. **Badges are stored**, not computed per request. Earning them reads the standings, games
   and blindtest guesses of every finished edition, and replays the all-time table after
   each edition. A profile request should not repeat that work: today the rankings pay a
   similar cost on every access.
5. **The global ranking badges** read the all-time table of `/players`, not an edition's
   team ranking, which the place badges already cover.
6. **A nightly cron job refreshes the badges**, not a page view: reading a profile never
   writes. The thresholds of the tiered badges will be tuned later.

## Definitions

- **Person, participation, finished, counted participation, places.** As in the player
  profiles spec and `profiles.py`. A participation belongs to one person and one edition,
  it counts when finished and ranked in an edition of at least 2 teams, and a rank of 1
  can be shared.
- **Sequence.** The finished active editions that have at least one active player, ordered
  by year. **Consecutive** means adjacent in the sequence, so a year without an edition is
  skipped. An edition without any roster says nothing about anyone, so it is left out too
  (decided while planning, 2026-09-23): missing data never breaks a streak. An unfinished
  edition is not in the sequence yet, so it can neither extend nor break a streak.
- **Place streak.** A run of consecutive editions that all meet a place condition. An
  edition where the person has no rank (no team, or nothing ranked) breaks every place
  streak, because missing data never counts. It does not break attendance streaks, which
  only need a participation.
- **Earned at.** Each rule is evaluated over the history up to each edition of the
  sequence in turn. A one-time badge is earned at the first edition where its rule holds.
  A repeatable badge is earned at every edition that completes a new occurrence. Playing
  more editions never takes a badge away. Only a correction of past data can, since the
  refresh rebuilds from the current data.
- **Title**: rank 1. **Podium**: rank 1 to 3.
- **Last place**: every active team of the edition has a rank and none has a worse one,
  in an edition of at least 4 teams, and that worst rank is 4th or below. So a last place
  is never also a podium place, even when the bottom teams tie (ranks 1, 2, 3, 3).
- **Relative rank**: `(rank − 1) / (teams − 1)`, from 0 for first to 1 for last, so that
  editions of different sizes compare.
- **Teammate**: another person whose participation in the same edition has the same
  valid team.
- **Discipline win, discipline podium**: a `ResultStanding.ranking` of 1, or of 1 to 3, in
  `compute_standings(edition)`, so only for revealed, scored results. A discipline is
  matched across editions by its `name`, as the rest of the app does.
- **Game**: an active, played game of an active round of an active discipline, the filter
  `compute_standings` uses. A game gives a badge only when its discipline is revealed, so
  a badge never leaks a hidden score. Refereeing a game leaks nothing, so every such game
  counts for the golden whistle.
- **All-time table after E**: the `/players` leaderboard built only from the
  participations of the editions up to E in the sequence, using the same `_record` and
  `_place` as `profiles.py`. Positions are shared as on the page, and someone with nothing
  counted yet has no position. The hall of fame badges read these tables from the first
  edition at which at least two editions of the sequence have counted participations. The
  table after a single edition is only that edition's ranking, and the place badges already
  cover that.
- **Metal**: the frame colour of a badge: `gold`, `silver`, `bronze`, or `plain` (the
  `--accent` colour). A tiered badge climbs from bronze (tier 1) to silver (2) to gold (3).
  Other badges have a fixed metal, listed in the catalogue.

## Catalogue

The codes are kebab-case. They serve as the database value, the glyph file stem and the
i18n key. The "Repeat" column says how often a badge can be earned:
- `once`: one time only;
- `each`: at every edition that completes a new occurrence;
- `streak`: once per streak;
- `tiers`: at each tier reached;
- one badge per discipline, per god or per partner, where the row says so.

The icon is a white glyph drawn inside the frame (see "Glyphs"). A ✓ marks the glyphs in
this commit's first batch.

### Edition places

Every place badge needs a counted participation.

| Code | FR | EN | Rule | Repeat | Metal | Icon |
|---|---|---|---|---|---|---|
| `champion` | Champion | Champion | Title in a counted participation | each | gold | Laurel wreath around a 1 ✓ |
| `runner-up` | Dauphin | Runner-up | Rank 2 | each | silver | A dolphin (*dauphin*) leaping over a wave ✓ |
| `bronze` | Bronze | Bronze | Rank 3 | each | bronze | Medal on a ribbon with a 3 |
| `chocolate` | Médaille en chocolat | Chocolate medal | Rank 4, in an edition of at least 5 teams (so never the last place) | each | plain | A bitten medal with a 4 ✓ |
| `wooden-spoon` | Cuillère de bois | Wooden spoon | Last place | each | plain | Wooden spoon ✓ |

### Streaks and career

| Code | FR | EN | Rule | Repeat | Metal | Icon |
|---|---|---|---|---|---|---|
| `back-to-back` | Doublé | Back-to-back | Titles in 2 consecutive editions | streak | gold | The wreath around II ✓ |
| `threepeat` | Triplé | Threepeat | Titles in 3 consecutive editions | streak | gold | The wreath around III ✓ |
| `dynasty` | Dynastie | Dynasty | Titles in 4 consecutive editions | streak | gold | Crown ✓ |
| `phoenix` | Phénix | Phoenix | A title in an edition whose previous edition in the sequence gave the person no title, when they already had one before | each | gold | Phoenix rising from a flame ✓ |
| `legend` | Légende | Legend | 3 titles in total | once | gold | Zeus' thunderbolt |
| `podium-regular` | Abonné au podium | Podium regular | Podium in 3 consecutive editions | streak | silver | A podium with a loop arrow |
| `full-set` | Collection complète | Full set | At least one 1st, one 2nd and one 3rd place | once | gold | Three medals hanging from one bar |
| `eternal-second` | Poulidor | Eternal second | A second 2nd place while still without a title | once | silver | A bicycle wheel hanging from a medal ribbon |
| `janus` | Janus | Janus | A title and a last place | once | plain | Two-faced head |
| `comeback` | Remontada | Comeback | Last place, then podium in the next edition | each | silver | An arrow rising from the floor |
| `on-the-rise` | Ascension | On the rise | Three consecutive editions, each with a strictly better relative rank than the one before (two climbs) | streak | bronze | Stairs with an arrow |
| `icarus` | Icare | Icarus | A title, then the bottom half (rank above `teams / 2`) in the next edition | each | plain | A wing losing its feathers ✓ |
| `lucky-charm` | Porte-bonheur | Lucky charm | First three counted participations all on the podium | once | silver | Four-leaf clover |

A title streak of 4 earns `back-to-back` at its second edition, `threepeat` at its third
and `dynasty` at its fourth. A longer streak earns nothing more, and a later streak starts
over.

### Loyalty

These need only a participation in a finished edition, not a rank.

| Code | FR | EN | Rule | Repeat | Metal | Icon |
|---|---|---|---|---|---|---|
| `rookie` | Bizut | Rookie | First participation | once | plain | Olive sprout |
| `veteran` | Vétéran | Veteran | 3 / 5 / 10 participations | tiers | tiers | Three chevrons ✓ |
| `argonaut` | Argonaute | Argonaut | Played the first finished edition, roster or not (when that edition has no roster, nobody earns it) | once | gold | The Argo's prow and oars |
| `ever-present` | Pénélope | Ever-present | 4 / 6 / 8 consecutive editions played | tiers | tiers | An unbroken chain |
| `homecoming` | Ulysse | Homecoming | Plays again after missing at least 2 consecutive editions | each | plain | Ulysses' ship under sail ✓ |
| `globetrotter` | Globe-trotteur | Globetrotter | Editions in 3 different `Edition.host` values (trimmed, case- and accent-insensitive) | once | bronze | Map pin on a globe |

### Teammates

| Code | FR | EN | Rule | Repeat | Metal | Icon |
|---|---|---|---|---|---|---|
| `comrades` | Compagnons d'armes | Comrades in arms | On the same team as the same person in 3 editions. Both people earn it, each with the other as `partner` | once per partner | silver | Two shields side by side ✓ |
| `networker` | Rassembleur | Networker | 20 / 40 / 60 different teammates | tiers | tiers | Linked dots |

### Hall of fame (the all-time table)

| Code | FR | EN | Rule | Repeat | Metal | Icon |
|---|---|---|---|---|---|---|
| `goat` | G.O.A.T | G.O.A.T | 1st in an all-time table, shared or not | once | gold | A goat's head under a crown ✓ |
| `alone-at-the-top` | Seul au sommet | Alone at the top | 1st in an all-time table, with the position held alone | once | gold | A mountain peak with a flag |
| `hall-of-fame-podium` | Podium du panthéon | Hall of fame podium | Top 3 | once | silver | A temple with three columns ✓ |
| `hall-of-famer` | Entrée au panthéon | Hall of famer | Top 10 | once | bronze | A single column |
| `reign` | Règne | Reign | 1st in 3 consecutive tables | streak | gold | Throne |
| `kingslayer` | Régicide | Kingslayer | 1st in a table after not being 1st in the previous one | each | gold | A toppled crown |
| `rocket` | Fusée | Rocket | The biggest climb between two consecutive tables (both positions known, at least one place, ties share it) | each | bronze | Rocket ✓ |

`kingslayer` and `rocket` compare two tables, so they start with the second table the hall
of fame reads.

### Disciplines

| Code | FR | EN | Rule | Repeat | Metal | Icon |
|---|---|---|---|---|---|---|
| `specialist` | Spécialiste | Specialist | Won the same discipline in 2 / 3 / 4 editions | tiers, one per discipline | tiers | That discipline's own icon, so there is no new glyph |
| `all-rounder` | Touche-à-tout | All-rounder | Won 3 / 5 / 8 different disciplines | tiers | tiers | A multi-tool |
| `decathlete` | Décathlonien | Decathlete | Podium in 10 different disciplines | once | gold | A ten-pointed star |
| `brains-and-brawn` | Tête et jambes | Brains and brawn | In one edition, won a mind discipline and a physical one | each | silver | A brain and a flexed arm |
| `clean-sweep` | Razzia | Clean sweep | Won at least 3 disciplines in one edition | each | gold | A broom ✓ |
| `metronome` | Métronome | Metronome | Podium in every ranked discipline of an edition, with at least 4 of them | each | gold | A metronome |
| `uncrowned` | Sans couronne | Uncrowned | The most discipline wins of the edition (at least 2, no team with more) without the title | each | plain | A cracked crown |
| `photo-finish` | Photo-finish | Photo finish | Won a points discipline on the points-difference tie-breaker (same points as a rank-2 result), or won a computed edition alone by 1 total point | once per edition | silver | Stopwatch ✓ |

**The gods.** Winning any discipline of a family earns its god, once per god and person,
at the first such win. All nine earn `olympus`.

| Code | FR | EN | Disciplines | Metal | Icon |
|---|---|---|---|---|---|
| `athena` | Athéna | Athena | General Culture Quizz, Geography Quizz, Geoguessr, Burger Quizz | bronze | Owl ✓ |
| `apollo` | Apollon | Apollo | Blindtest, Dance | bronze | Lyre |
| `artemis` | Artémis | Artemis | Darts, Petanque, Disc Throw, Frisbee | bronze | Bow and arrow ✓ |
| `hermes` | Hermès | Hermes | Relay, Jumping Rope, Obstacle Course, Blindfolded Obstacle Course | bronze | Winged sandal |
| `heracles` | Héraclès | Heracles | Crossfit | bronze | Club |
| `theseus` | Thésée | Theseus | Orienteering | bronze | Labyrinth |
| `ares` | Arès | Ares | Rugby, Football, Handball, Basketball, Volleyball, Dodgeball | bronze | Crested helmet |
| `hades` | Hadès | Hades | Hide and Seek | bronze | The same helmet drawn in dashes (the helm of invisibility) |
| `dionysus` | Dionysos | Dionysus | Fair | bronze | A bunch of grapes |
| `olympus` | Olympe | Mount Olympus | All nine gods | gold | A mountain topped by a temple |

**Kinds**, for `brains-and-brawn`: the mind disciplines are the four Athena ones and
Blindtest, and every other discipline except Fair is physical.

Both maps live in `badges.py` and match on the discipline name. A test fails when a
`Discipline` subclass is missing from them, as `icons.test.js` does for icons. So adding a
discipline means picking its god and its kind.

### Games

| Code | FR | EN | Rule | Repeat | Metal | Icon |
|---|---|---|---|---|---|---|
| `unbeaten` | Invaincu | Unbeaten | No loss in a discipline's games, at least 3 played, not all won | each, per discipline | silver | Shield |
| `perfect-run` | Sans faute | Perfect run | Won every game of a discipline, at least 3 played. Replaces `unbeaten` for that discipline and edition | each, per discipline | gold | Shield with a star |
| `shutout` | Cadenas | Shutout | Won a game without conceding a point | once per edition | bronze | Padlock |
| `steamroller` | Rouleau compresseur | Steamroller | The biggest winning margin of the edition's games (ties share it) | once per edition | silver | Road roller |
| `golden-whistle` | Sifflet d'or | Golden whistle | The person's teams refereed 5 / 10 / 20 games in total | tiers | tiers | Whistle ✓ |
| `perfect-pitch` | Oreille absolue | Perfect pitch | Artist and song both right on every active round of the edition's blindtest, which must be revealed | once per edition | gold | Tuning fork |

### Given by hand

Organisers add these in the admin (see "Admin"), with an edition.

| Code | FR | EN | Metal | Icon |
|---|---|---|---|---|
| `mvp` | MVP | MVP | gold | A star under a crown |
| `fair-play` | Fair-play | Fair play | silver | Handshake |
| `hype` | Ambianceur | Hype squad | plain | Megaphone |
| `costume` | Plus beau déguisement | Best costume | plain | Theatre mask |
| `wounded` | Blessé de guerre | Walking wounded | plain | Adhesive bandage |
| `torchbearer` | Porteur de flamme | Torchbearer (organised the edition) | gold | Torch |

## Backend

### Model `Badge` (`models/Badge.py`)

```python
class Badge(models.Model):
    """A badge a person earned, computed by badges.py or given by hand."""

    class Codes(models.TextChoices): ...       # the catalogue, in catalogue order

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    code = models.CharField(max_length=32, choices=Codes.choices)
    edition = models.ForeignKey("Edition", on_delete=models.CASCADE)  # earned at
    tier = models.PositiveSmallIntegerField(default=0)                # 0 untiered, 1 to 3
    discipline = models.CharField(max_length=100, blank=True, default="")  # specialist, unbeaten, perfect-run
    partner = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name="+")  # comrades
    is_manual = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True)  # organiser memo, never public
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

- **Key.** A computed row is identified by `(user, code, edition, tier, discipline, partner)`.
  A partial unique constraint on it covers the computed rows (`condition=Q(is_manual=False)`).
  Django 4.2 has no `nulls_distinct`, so for rows without a partner the refresh's diff is
  what keeps them unique.
- **`is_active`** is the soft delete every model has, and `request_only_active` needs it.
  An organiser can revoke a computed badge by deactivating it, and the refresh keeps that
  row inactive for as long as the badge is earned.
- **`created_at`** records when a row was first stored. It is kept for a later "new"
  marker.
- Migration `0033` creates the table, plus `BadgeRefresh` (below) with its single row.
- `Badge` has no `save()` logic, so the refresh's `bulk_create` and queryset `delete()`
  skip nothing.

### `olympic_warriors/badges.py`

This module is built like `profiles.py`: pure computation over a few queries.

```python
@dataclass(frozen=True)
class Earned:
    user_id: int
    code: str
    edition_id: int
    tier: int = 0
    discipline: str = ""
    partner_id: int | None = None

def earned(today=None) -> set[Earned]   # every computed badge, from the current data
def refresh(today=None) -> RefreshReport   # store earned(), see below
```

`profiles.participations()` is split: a `_load(today)` step returns the editions, the
chosen player rows and the standings, and both `participations()` and `earned()` build on
it, so the two can never disagree on who played where. `earned()` then adds:
- the active results of the finished editions with their team and discipline name (1
  query). If the per-discipline ranking work lands first and already exposes each result's
  team and discipline, `earned()` reuses that instead;
- the games of the finished editions (1);
- the blindtest guesses of the finished editions (1).

That makes a fixed number of queries plus three per finished edition with players,
pinned as `BADGES_QUERIES` in the tests like `PROFILES_QUERIES`. The all-time tables are
replayed in memory from the participations, with no query per table.

**`refresh(today)`**, in one transaction:
1. lock the `BadgeRefresh` row (`select_for_update()`, after a `get_or_create` in case a
   flushed test database lost the row the migration made);
2. compute `earned(today)`;
3. diff it against the stored computed rows, keyed as above:
   - delete the rows no longer earned, active or not;
   - `bulk_create` the new ones;
   - leave the others alone, so `created_at` and a revoked row's `is_active` survive;
4. set `BadgeRefresh.refreshed_at` to now, and return how many rows were added and
   removed (`RefreshReport`).

Manual rows are never read or written. Running it twice in a row writes nothing the
second time.

**`BadgeRefresh`** is a one-row model (`refreshed_at`, a nullable datetime), created by
the migration and not registered in the admin. Its row lock makes a cron run and an admin
action that start together run one after the other, and `refreshed_at` shows when the last
run finished, so anyone can check that the cron job is running.

### When the badges refresh

- **Every night, by cron.** A crontab entry on the production host runs the command
  below at 02:00 UTC, which is 03:00 or 04:00 in Paris. That is always after midnight
  Paris time, so an edition whose `end_date` was the day before counts as finished:
  ```
  # host clock in UTC
  0 2 * * * cd <repo> && docker compose -f <compose file> exec -T server python manage.py refresh_badges >> /var/log/olympic-warriors-badges.log 2>&1
  ```
  `-T` because cron has no terminal. The refresh rebuilds everything, so a correction to
  a past edition also shows after the next night. The profile view only reads.
- **On demand.** An Edition changelist action, « Recalculer les badges (toutes les
  éditions) », runs `refresh()`. The selection does not matter, because streaks and tables
  span editions.
- **After an import.** `import_edition` runs `refresh()` after a real (not `--dry-run`)
  import.
- **From the command line.** The `refresh_badges` management command, which the cron
  job calls, runs `refresh()` and prints the rows added and removed and `refreshed_at`.

### Endpoint

`GET /profile/<user_id>/` gains `badges`, in catalogue order, with the active rows of
active editions grouped by `(code, discipline, partner)`:

```json
"badges": [
  {"code": "champion", "tier": 0, "years": [2024, 2026], "discipline": null, "partner": null},
  {"code": "veteran", "tier": 2, "years": [2024, 2026], "discipline": null, "partner": null},
  {"code": "specialist", "tier": 1, "years": [2026], "discipline": "Rugby", "partner": null},
  {"code": "comrades", "tier": 0, "years": [2026], "discipline": null,
   "partner": {"id": 12, "first_name": "Léa", "last_name": "Martin"}}
]
```

- **`years`** are the editions of the grouped rows, oldest first. For a repeatable badge,
  their count is the number of times it was earned. For a tiered badge, the last year is
  when the current tier was reached.
- **`tier`** is the highest tier among the grouped rows.
- **`discipline`** is the database name, which the front translates.
- **`partner`** carries names only, like the rest of the profile payloads: never a
  username or an email.
- **Private fields** (`note`, `is_manual`, `created_at`) stay out of the payload.

The leaderboard (`/profiles/`) does not change in this step.

## Admin

- **`BadgeAdmin`** lists `user`, `code`, `edition`, `tier`, `discipline`, `partner`,
  `is_manual` and `is_active`, filters on `code`, `edition` and `is_manual`, and goes
  through `request_only_active` like every changelist.
- **Adding** offers only the "given by hand" codes, and sets `is_manual`. The form's
  `code` choices are restricted, so this is not `save()` logic.
- **A computed row** is read-only except for `is_active` (`get_readonly_fields`).
- **The Edition changelist** gets the refresh action above.

## Front

### Glyphs

The glyph files are `front/src/lib/img/badges/<code>.svg`, in the discipline icons'
house style:
- a 2000×2000 viewBox;
- white strokes, main outlines 110 to 150 units wide and details down to 50, with round
  caps and joins;
- white fills for small solid parts;
- no background and no frame, since the frame belongs to the component.

`specialist` reuses the discipline's icon through `iconFor`. No glyph uses the five
Olympic rings, a protected symbol.

This commit brings the first 20 glyphs, the ✓ rows above, to settle the style. The rest
come with the phase that needs them (see "Phases").

### `src/lib/badges.js`

The front catalogue: for each code, its glyph URL (`import.meta.glob` over
`img/badges/*.svg`, as `icons.js` does), its metal and whether it is tiered.
`badgeGlyph(badge)` returns the discipline icon for `specialist`.

### `Badge.svelte`

A medallion sized by `--badge-size`, so pages scale it the way `MedalRank` is scaled.
It is purely visual (`aria-hidden`): the tile around it writes the name and the tier.
- a circle, transparent inside, with a ring about 4% of the size wide in the metal
  colour (`--gold`, `--silver`, `--bronze`, or `--accent` for plain);
- a hairline inner ring in the same colour at 35% opacity (the board drops it below
  40px; the profile's 56px is the only size used for now);
- the glyph at 60% of the size, as an `<img alt="">`;
- for a tiered badge, three pips under the medallion: the first `tier` filled in the
  metal colour and the rest in `--line`. The tile's detail line also says « Niveau 2 » /
  "Tier 2", so colour alone never carries the tier.

There is a locked style, a dashed `--ghost` ring with the glyph at 0.35 opacity, but it
goes unused until a catalogue page exists.

The style board for this step, with the first batch in its frames, the metals, tiers and
sizes, and the section on a phone profile, is a private claude.ai canvas that the
brainstorm linked.

### Profile page

A « Badges » / "Badges" section between the counts line and the Editions section, left out
when the person has none. It is a grid of tiles (`repeat(auto-fill, minmax(9rem, 1fr))`),
and each tile shows:
- the medallion, 56px;
- the name, `badge.<code>.name`, in `.label` style;
- a detail line in `--muted`, its parts joined by ` · `, starting with the translated
  discipline name whenever the badge has one (`specialist`, `unbeaten`, `perfect-run`), so
  two tiles of one code tell their disciplines apart:
  - a tiered badge: « Niveau 2 » / "Tier 2", then the year that tier was reached
    (`Rugby · Tier 1 · 2026`);
  - `comrades`: « avec » / "with" and the partner as a link to their profile, then the
    year (`with Léa Martin · 2026`);
  - any other badge: `×2` when earned more than once, then the years
    (`×2 · 2024 · 2026`, `Dodgeball · ×2 · 2025 · 2026`);
- the rule, `badge.<code>.rule`, as a small `--muted` line, so nothing hides behind a
  hover.

A code the front does not know (a newer server) is left out of the section.

Text shape for the tests: `Champion ×2 · 2024 · 2026 Win an edition`.

### i18n

- `badge.<code>.name` and `badge.<code>.rule` for every code, in `fr.js` and `en.js`
  (`parity.test.js` covers them). The thresholds are written into the rule text, so
  tuning one means changing `badges.py` and both dictionaries (decided while planning).
- `profile.badges` for the heading, `badge.level` (« Niveau {tier} » / "Tier {tier}"),
  `badge.times` (`×{n}`) and `badge.with` (« avec » / "with").

## Phases

1. The model, the refresh, the edition places, streaks and career, loyalty, teammates and
   hall of fame, and the profile section.
2. The discipline badges and the gods. They need each result's team and discipline, which
   the per-discipline ranking work provides.
3. The game badges.
4. The badges given by hand, with their admin.

Each phase draws its own glyphs and adds its codes, dictionary keys and tests.

## Testing

Server (`tests/test_badges.py`), with an injected `today`:
- one test per rule, on the smallest history that earns the badge and one that barely
  misses it;
- a streak holds across a calendar year without an edition and breaks on a missed
  edition. An unranked edition breaks place streaks but not attendance ones;
- a streak of 4 earns each streak badge once, and a later streak earns them again;
- playing more never removes a badge: `eternal-second` stays after a later title;
- a hidden discipline gives no discipline or game badge, and a hand-ranked edition gives
  places but no photo finish on totals;
- the hall of fame starts at the second edition with counted places. `kingslayer` and
  `rocket` start one table later;
- `refresh()`:
  - a second run writes nothing;
  - a badge no longer earned is deleted;
  - a revoked row stays inactive;
  - manual rows are untouched;
  - `refresh_badges` calls it and prints the rows added and removed, and
    `refreshed_at` is set;
- the query count (`BADGES_QUERIES`);
- the family and kind maps cover every `Discipline` subclass;
- the profile payload: grouping, catalogue order, `years`, `tier`, the partner's shape,
  and no username or email.

Front:
- `src/lib/badges.test.js` lists every code (`BADGE_CODES`, mirroring `Badge.Codes` as
  `DISCIPLINE_NAMES` mirrors the models). It fails when a code lacks a glyph, a metal, or
  a name or rule in either dictionary;
- `Badge.svelte`: the metal, the pips, and that it is `aria-hidden`;
- the profile page: the tile text shapes, the partner link, the section left out when
  empty, and one French test.

## Known limitations

- Badges are only as complete as the rosters, as with the profiles: early editions
  without `Player` rows give nobody anything.
- Two people with the same full name share a user, and so share their badges.
- A correction to a finished edition shows after the next nightly run, or at once
  through the admin action.
- The cron entry lives on the host, outside the repository. Without it, a finished
  edition's badges wait for the admin action or an `import_edition`.
- The thresholds (networker, golden whistle, veteran, ever-present) are first guesses, to
  tune once the real data is in.
- `created_at` restarts when a correction removes a badge and a later one earns it back.
- Manual badges are not part of the edition export and import (`transfer.NOT_EXPORTED`),
  and `import_edition --replace` cascade-deletes the replaced edition's badges.

## Out of scope

- Player-level badges from game events (a try hunter, the most tackles, the most
  dodgeball catches). `RugbyEvent` and `DodgeballEvent` are not logged today.
- A public catalogue page showing locked badges.
- Badges on the leaderboard rows.
- Notifications, and a per-person opt-out.

## Documentation

The implementation updates `CLAUDE.md` with:
- the `Badge` model and `badges.py` with its rules;
- when the badges refresh, with the crontab line; a comment on the `server` service of
  `docker-compose.prod.example.yml` points to it;
- the `badges` field of `/profile/<id>/`;
- the glyph folder and its house style;
- the new tests.
