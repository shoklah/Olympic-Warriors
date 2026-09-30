# Badge progress: implementation plan

Spec: `docs/superpowers/specs/2026-09-30-badge-progress-design.md` (the spec wins over this
plan wherever they differ). Two tracks run side by side: the server in the main checkout,
the front in a worktree (`../ow-front-progress`, branch `progress-front`, its own `npm ci`),
merged into `claude/player-profile-customization-f4a2l5` at the end. Each task is written
test first, reviewed, then committed.

Rules for every task:
- Read `CLAUDE.md` first; match the surrounding code (comment density, naming, idiom).
- Test first: write the failing tests, see them fail, then implement.
- Stage files by name (never `git add -A`), commit messages `[FEAT]`/`[TEST]`/`[DOCS]`
  style as in `git log`, ending with the two trailer lines given in the task prompt.
- Test fixtures never look like secrets (no realistic passwords or tokens).
- No model identifier in commits or code.
- Server checks: `cd server && ENV=dev python3 manage.py test olympic_warriors --parallel 4`
  and `ENV=dev python3 manage.py makemigrations --check --dry-run`; Postgres is local
  (`pg_ctlcluster 16 main start` if it is down). Front checks: `cd front && npm test` and
  `npm run build`.

## Server track

### S1. Counters, `compute()` and the `BadgeProgress` rows

- `badges.py`:
  - `PROGRESS_TARGETS` (the 14 non-tiered targets of the spec's table, olympus
    `len(GODS)`); the rules read it instead of their literals (`TITLE_STREAKS` built from
    it, legend, eternal-second, on-the-rise as target + 1, comrades, decathlete,
    clean-sweep, lucky-charm, podium-regular, reign); full-set keeps `{1, 2, 3}`.
  - `_counters(h)`: every person of `h.users`, their raw counters as the spec lists them
    (a frozen dataclass per person is fine): veteran's played, ever-present's run and best,
    networker's mates, specialist's {name: wins} with each name's latest win index,
    all-rounder, legend, full-set, decathlete, olympus, the title and podium runs with
    their best, on-the-rise `max(rise − 1, 0)` and best, reign from `_hall_of_fame`'s
    counter and best, comrades' {partner: shared} with the latest shared index,
    clean-sweep's {index: wins}, eternal-second's seconds and whether a title came,
    lucky-charm's podiums among the first three counted and whether one missed, argonaut's
    out-of-reach flag. Compute them next to the rules without changing what the rules earn;
    where a rule already keeps the number, share the walk rather than duplicating it only
    if that stays readable (a separate walk of the same helpers is acceptable, as long as
    `BADGES_QUERIES` does not move).
  - `Progress` (frozen dataclass keyed like a row: user_id, code, value, best, reachable,
    discipline, partner_id, year) and `compute(today) -> (earned set, progress set)`;
    `earned(today)` becomes `compute(today)[0]`. The rows follow the spec's "Which rows
    exist" and the tie-breaks of the counter bullets.
- `models/BadgeProgress.py` as the spec's code block, exported from `models/__init__.py`,
  migration `0039_badgeprogress`; `transfer.NOT_EXPORTED` gains it.
- Tests in `test_badges.py`: the counters and rows of the spec's Tests list, and
  `World.tearDown` running `assert_counters_agree()` (spec § The raw counters and the rules
  agree) over whatever each test built; `BADGES_QUERIES` unchanged. `test_transfer.py`
  passes with the new model in `NOT_EXPORTED`.

### S2. The refresh stores the progress; `--if-due`

- `refresh()` diffs `BadgeProgress` by `(user, code)` inside its transaction (delete gone,
  `bulk_update` changed, `bulk_create` new, leave the rest); `RefreshReport.progress` = rows
  created + updated + deleted.
- `refresh_due(today)` (spec § The refresh) and `refresh_badges --if-due`; the command prints
  the progress count; the Edition admin action's message and `import_edition`'s badge line
  print it too.
- Docstrings and help drop "monthly" (`badges.py` module docstring, the command);
  `docker-compose.prod.example.yml`'s comment gets the daily `--if-due` crontab line.
- Tests in `test_badge_refresh.py` (spec's Tests list), `REFRESH_OWN_QUERIES` updated and
  pinned, `a_report()` and the admin message assertion following the new field.

### S3. The payload

- `badges.progress_entries(user_id)` (1 query, `select_related("partner__profile")`,
  catalogue order, the entry shape of the spec's JSON example); `getProfile` adds
  `progress`; an OpenAPI serializer for the entries in the profile schema.
- Tests: `test_profiles.py` (payload, order, `PROFILES_QUERIES + 1`), `test_showcase.py`
  (a comrades progress row in the private-keys walk), `/profiles/` rows without progress.

## Front track (worktree)

### F1. Sizes in `rem`

- `Badge.svelte`: `--badge-size` default 3.5rem, pip floor `max(0.3125rem, …)`;
  `Showcase.svelte`: row 1.25rem, interactive 2.5rem / 3rem, the `--showcase-hang` floor
  `max(0.3125rem, …)`; `BadgeCollection.svelte` 3rem; `BadgeSheet.svelte` medallion 4rem;
  any other `--badge-size` in the tree.
- Avatars beside a name as strings: `"1.5rem"` (team roster, header pills, the sheet's
  comrades line), `"2rem"` (leaderboard rows); the profile portrait and the photo editor
  stay `px`. `Avatar`'s numeric `size` keeps meaning pixels.
- The leaderboard row's showcase wraps below 600px.
- Tests: `Badge.test.js`, `Avatar.test.js`, `Showcase.test.js` follow; the full suite green.
- Chromium: before/after screenshots at the default font size (identical) and at a 24px
  default (no horizontal scroll) on `/players`, a profile (both tabs, a sheet open), a team
  page, the header at 375, 800 and 1280px.

### F2. The progress block in the sheet

- `badges.js`: `PROGRESS_TARGETS`, `PROGRESS_CODES` (the 20 codes in catalogue order),
  `progressFor(progress, code)`, and a pure helper computing what the sheet draws from an
  entry (target, fill share, ticks and their lit state, fill metal, top tier, the fraction
  or count), so the maths is unit-tested without Svelte.
- i18n: the spec's key table in `fr.js` and `en.js`.
- `BadgeSheet.svelte`: a `progress` prop and the block of spec § The sheet and § Look;
  entries of an earned tiered badge drop « Prochain niveau » when an entry is shown, except
  specialist's; no entry keeps today's lines.
- `BadgeCollection.svelte` and `Showcase.svelte` (interactive) take and pass `progress`; the
  profile page passes `profile.progress ?? []`; a progress fixture in
  `src/lib/fixtures/players.js`.
- Tests of the spec's Tests list (`badges.test.js`, `BadgeSheet.test.js`, the profile's
  `page.test.js`), one French rendering.

## Merge, check, document

1. Merge `progress-front` into the branch; both suites, the build and `makemigrations
   --check` green.
2. End to end in Chromium: the real server (a seeded database with several finished
   editions, a streak, a comrades pair, an out-of-reach case) and the front, the bars in the
   sheet from a slot and from the showcase, dark and light, at 375 and 1280px.
3. `CLAUDE.md` (Player badges: `BadgeProgress`, `compute`, `refresh_due`, the daily cron,
   `RefreshReport.progress`, `NOT_EXPORTED`, the payload; front: the sheet's block, the rem
   sizes; the commands line) and `server/README.md` (model table, `/profile/<id>/` row).
4. Push; retitle and redescribe PR #108.
