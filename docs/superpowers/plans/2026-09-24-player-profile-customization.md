# Player Profile Customization Implementation Plan

> **For agentic workers:** executed subagent-driven: one implementer per task, then a
> review of that task, before the next task starts. Steps use checkbox (`- [ ]`) syntax.

**Goal:** players claim an account through an organiser's link, then add a photo and pin
a showcase of three badges to their public profile; organisers moderate from the admin;
the API becomes staff-only by default.

**Spec:** `docs/superpowers/specs/2026-09-24-player-profile-customization-design.md` is
the source of truth for rules, payload shapes, error codes and wording. Read it in full
before starting a task.

**Tech stack:** Django 4.2 + DRF 3.15 (PostgreSQL), SvelteKit 2 / Svelte 4 (plain JS),
Vitest + @testing-library/svelte.

---

## Rules for whoever executes a task

- **Two tracks run in parallel in two checkouts of the same repository.**
  - **Server track** (Tasks 1–5): `/home/user/Olympic-Warriors`, branch
    `claude/player-profile-customization-f4a2l5`. Touch only `server/` (and
    `.github/` if CI needs it).
  - **Front track** (Tasks 6–10): the worktree `/home/user/ow-front`, local branch
    `claude/ppc-front`. Touch only `front/`.

  Never switch branches, never `git stash`, never push, never `git add -A` or
  `git add .`: stage your own paths by name. `CLAUDE.md` is updated in Task 11 only, after
  the tracks merge.
- **Server tests:** a local PostgreSQL is running and `server/dev.env` points at it.
  - One module: `cd server && ENV=dev python3 manage.py test olympic_warriors.tests.test_x`.
  - The whole suite: `ENV=dev python3 manage.py test olympic_warriors --parallel 4`. The
    baseline is 569 tests, all green.
  - Migrations: `ENV=dev python3 manage.py makemigrations olympic_warriors`, and check that
    it produced one migration.
  - Pylint (advisory): `pylint --load-plugins pylint_django --ignore=lib server/`. Do not
    make it worse on the files you touch.
- **Front tests:** `cd front && npx vitest run <paths>`, the whole suite with `npm test`
  (baseline 491, all green), and the build with `npm run build`. Both gate CI.
- **Test-first:** write the tests, see them fail, implement, see them pass, run the whole
  suite of your track, then commit. One or more commits per task. Messages look like
  `[FEAT] server: …` or `[FEAT] front: …` (the repo also uses `[FIX]`, `[TEST]`,
  `[REFACTOR]`) and end with these two lines:

  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01W2budnwnP64zHCZfAn9BB9
  ```

  Never put a model name anywhere else: not in code, comments or other commit text.
- **Server conventions** (CLAUDE.md, "Backend architecture"):
  - flat `@api_view` functions in `views.py`, wired in `urls.py`, with any
    `@permission_classes` / `@throttle_classes` / `@parser_classes` **below** `@api_view`;
  - `@extend_schema` on every view, like its neighbours;
  - `test_routes.py` checks that route converter names match view parameters;
  - query counts are pinned in tests (`SUMMARY_QUERIES`, `PROFILES_QUERIES`,
    `BADGES_QUERIES`, …): update a constant only when the spec says the count changes;
  - comments explain *why*, in the dense docstring style of `profiles.py` and
    `badges.py`.
- **Front conventions** (CLAUDE.md, "Frontend architecture"):
  - Scoreboard tokens only, no hard-coded colours;
  - uppercase only through CSS;
  - every string through `t`, with `fr.js` and `en.js` at parity (`parity.test.js`);
  - `useT()`, `useLocale()`, `useOrganiser()` and the new `useMe()` at init only;
  - page tests assert on text shapes and render through `renderWith`;
  - every translated surface keeps one French test;
  - a white SVG `<img>` on a page surface needs its `filter` rule (`styles.test.js`);
  - `.quiet-link` on links among text;
  - never `use:enhance` the `/lang` or `/theme` forms.

  The site speaks to players as « vous ».
- **Stay in scope.** Build exactly what the task and the spec say. If the spec is wrong
  or silent on something that blocks you, choose the smallest reasonable option, say so
  in your report, and note it as a spec gap. Don't widen the task.
- **Report** at the end:
  - the commits (hash and subject);
  - the test counts before and after;
  - every deviation from the spec or the plan, and why;
  - anything left open.

---

## Server track

### Task 1: API lock-down

**Spec:** §1.

- [ ] `settings.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']` becomes
  `['olympic_warriors.permissions.IsOrganiser']`.
- [ ] The reveal-aware read views (`/game/<id>/`, `/games/...`, `/round/<id>/`,
  `/rounds/...`, `/result/<id>/`, `/results/...`, meaning the views that read through
  `_games()`, `_rounds()` and `_results()`) get `@permission_classes([IsAuthenticated])`
  below `@api_view`, with a one-line comment saying why: they apply the reveal rule and
  carry no more than the public summary.
- [ ] The public views keep `AllowAny`. `ThrottledObtainAuthToken` and the swagger schema
  keep working without a token: check it.
- [ ] New `tests/test_permissions.py` walks `urls.py` (reuse whatever `test_routes.py`
  does to enumerate the routed views) and asserts, for every route, one of:
  - the view is in the explicit `PUBLIC` allow-list and answers without a token (not
    401/403);
  - it is in the explicit `PLAYER` allow-list and answers a non-staff token (not 403) but
    refuses an anonymous request with 401;
  - it refuses a non-staff token with 403.

  Build URL arguments from the converters (any id works, since a 404 is fine: only
  401/403 matter). Use every HTTP method the view allows, but avoid side effects: a
  write with a non-staff token must be refused before it runs. The file explains that a
  new view is closed until it is added to a list on purpose.
- [ ] Existing tests that used a non-staff token on a view that is now staff-only switch
  to a staff user, or assert the new 403 where the test is about access. Don't weaken any
  assertion.
- [ ] The whole server suite passes.

### Task 2: `UserProfile`, photo storage and its admin

**Spec:** §2, §3, §7 (without the claim action, which is Task 3).

- [ ] Add `Pillow` to `server/requirements.txt`, pinned to the current release
  (`pip install Pillow` then `pip show Pillow`).
- [ ] `models/UserProfile.py`, exported from `models/__init__.py`, with one migration.
  `showcase` is `ArrayField(models.CharField(max_length=32, choices=Badge.Codes.choices),
  size=3, default=list, blank=True)`, and the one-to-one uses `related_name="profile"`.
- [ ] `transfer.NOT_EXPORTED` gains `"UserProfile"`, so `test_transfer.py` stays green.
- [ ] `olympic_warriors/avatars.py`: `PhotoError(code)`, `store_photo(profile, upload)`
  and `remove_photo(profile)`, exactly as in §3. The size limit, the formats, the pixel
  limit and the output sizes are module constants.
  - The random names come from `secrets.token_hex(6)`.
  - Save through the fields' storage, so `MEDIA_ROOT` and a test `override_settings`
    work.
  - Old files are deleted in `transaction.on_commit`.
- [ ] `tests/test_avatars.py`, with images generated by Pillow in memory and
  `MEDIA_ROOT` overridden to a temp dir cleaned in `tearDown`. Cover:
  - an EXIF-rotated JPEG comes out upright with no EXIF;
  - PNG and WebP are accepted, and a GIF or a text file is refused (`bad_format`);
  - more than 2 MB is refused (`too_large`);
  - more than 4096² pixels is refused (`too_many_pixels`) without a full decode;
  - a non-square image is centre-cropped;
  - the output sizes are 512 and 128;
  - replacing deletes the old files on commit (use `captureOnCommitCallbacks(execute=True)`);
  - `remove_photo` clears both fields and the files;
  - a locked profile refuses `store_photo` with `photo_locked`.
- [ ] `UserProfileAdmin` in `admin.py`, per §7: the thumbnail column, `photo_locked`
  editable in the list, `claimed_at` and `updated_at`, search by the user's name, the
  filters, and the actions « Retirer la photo » and « Retirer et verrouiller ».
  - The photo fields and `showcase` are read-only, with no upload widget.
  - No `request_only_active` (the model has no `is_active`).
  - Tests go in a new `tests/test_user_profile_admin.py`: the changelist renders, both
    actions work, and the change form has no file input.
- [ ] The whole server suite passes.

### Task 3: Claim links

**Spec:** §4, plus the claim action of §7.

- [ ] `config.py`: `PUBLIC_URL`, required in `ProdConfig` and defaulting to
  `http://localhost:5173` in `DevConfig`, following how the other settings are declared.
  Add it to `server/.env.example` with a comment. `settings.PASSWORD_RESET_TIMEOUT = 7 *
  24 * 3600`, with a comment.
- [ ] `olympic_warriors/claims.py`:
  - `is_claimable(user)`: a person (an active `Player` in an active edition), `is_active`,
    not `is_staff`;
  - `claim_link(user)`: raises `ValueError` when the user is not claimable;
  - `check_claim(uidb64, token)`: returns the user or `None`, with every failure looking
    the same;
  - `complete_claim(user, password)`: `validate_password`, then one transaction that sets
    the password, deletes the DRF token and creates a fresh one, and stamps
    `UserProfile.claimed_at` (`get_or_create`). It returns the new token key.
- [ ] Views: `GET` and `POST` `claim/<str:uidb64>/<str:token>/` (one view, both methods),
  with `AllowAny` and `@throttle_classes([LoginRateThrottle])`. The shapes and error
  codes are in §4.
- [ ] Admin: the action « Générer un lien d'activation » on `PlayerAdmin` and on
  `UserProfileAdmin`. It adds one `messages.info` line per claimable user, `Léa Martin
  (leamartin) : <link>`, and a `messages.warning` for each skipped user (staff, or not a
  person).
- [ ] `tests/test_claims.py`. Cover:
  - GET: a valid link gives `first_name` and `username`; the 404s for a bad uid, a bad
    token, an expired token (`override_settings(PASSWORD_RESET_TIMEOUT=...)`, or a
    patched clock), a staff user, a non-person and an inactive user;
  - POST: a weak password gives a 400 with its codes;
  - POST success: returns the new token and `user_id`, the old token no longer
    authenticates, the new one does, the link cannot be used twice, and `claimed_at` is
    set;
  - the throttle gives a 429 (swap in a private local-memory cache the way
    `test_auth_token.py` does);
  - the admin action's messages on both admins.
- [ ] The whole server suite passes.

### Task 4: `/me/`, photo endpoints and the showcase

**Spec:** §5, and "Showcase" under Definitions.

- [ ] `badges.py`:
  - `badges_by_user(user_ids)`: 1 query, `{user_id: [entries]}` in exactly the shape
    `profile_badges` returns. Refactor so both share one grouping function, and
    `profile_badges(user_id)` keeps its signature and its 1 query.
  - `showcase(entries, pins, holders)`: pure, no query. It returns `{"auto": bool,
    "badges": [{"code", "tier", "discipline"}]}` per the spec:
    - the pins filtered to earned codes, in pin order; if none survive, automatic;
    - automatic is the 3 rarest earned codes (fewest holders, then higher tier, then
      catalogue order);
    - each code is drawn from its entry with the highest tier, else the first entry.
- [ ] Views, all with `IsAuthenticated`:
  - `GET me/`: the §5 shape. `photo` is `null` or `{large, small}` URLs, and `showcase`
    is `{auto, codes}` (the stored pins).
  - `PUT` and `DELETE` `me/photo/` (one view): `MultiPartParser`, and a
    `UserRateThrottle` subclass with scope `photo` whose rate comes from a new config
    value `PHOTO_THROTTLE_RATE` (default `10/hour`), throttling `PUT` only. The error
    codes are in §5. A user who is not a person gets 404.
  - `PUT me/showcase/`: the validation in §5, returning the new `{auto, badges}`.
- [ ] Every new view goes into the `PLAYER` list of `test_permissions.py`.
- [ ] `tests/test_me.py` and `tests/test_showcase.py`:
  - every rule of `showcase()` on hand-built entries (pure);
  - `badges_by_user` query count and shape;
  - the endpoints: auth, 404 for a non-person, photo PUT and DELETE (DELETE works when
    locked, PUT answers 403 `photo_locked`), the throttle, and the showcase 400s (unknown
    code, unearned code, duplicates, more than 3) and a round trip.
- [ ] The whole server suite passes.

### Task 5: Public payloads carry photos and showcases

**Spec:** §6.

- [ ] `leaderboard()`'s players query gains `select_related("user__profile")`.
  `PlayerRecord` carries the photo (the small and large URLs, or `None`) without extra
  queries.
- [ ] `/profiles/` rows gain `photo` (small URL or `null`) and `showcase` (the `badges`
  list of `showcase()`), through `badges_by_user` plus `badge_stats` over the
  leaderboard's user ids. `PROFILES_QUERIES` becomes `4 + 3 × finished editions with
  players`: update the constant and its comment.
- [ ] `/profile/<id>/` gains `photo` (`{large, small}` or `null`) and `showcase` (`{auto,
  badges}`, the pins from the person's `UserProfile`). It reuses the `profile_badges` and
  `badge_stats` it already loads. `comrades` partners gain `photo` (small or `null`)
  through `select_related("partner__profile")`. The query count is unchanged: prove it
  with the existing assertion, or add one.
- [ ] Summary roster players gain `photo` (small or `null`). `SUMMARY_QUERIES` is
  unchanged.
- [ ] Tests extend `test_profiles.py`, `test_summary.py` and `test_badges.py` (or wherever
  `profile_badges` is tested). Pin the new keys and the unchanged or new counts, and check
  that `photo_locked`, `claimed_at` and `username` never appear in these payloads.
- [ ] The whole server suite passes.

---

## Front track (worktree `/home/user/ow-front`)

### Task 6: Viewer session, `Avatar`, header account pill

**Spec:** Front → Session and `Avatar.svelte`.

- [ ] The root `+layout.server.js`: `resolveViewer` calls `/me/` (instead of
  `/user/current/`) and returns `organiser` (`is_staff`) and `me` (`{id, first_name,
  photo, is_person}` or `null`). Keep the drop-on-401/403 and keep-on-outage rules, and
  update `layout.server.test.js`.
- [ ] `+layout.svelte` puts `me` in context under `ME`. Add `useMe()` next to
  `useOrganiser()` (find where that lives), and give `renderWith` in `src/lib/test-utils.js`
  a way to pass `me`, keeping every existing call working.
- [ ] `src/lib/avatar.js`: `initials(first, last)` (letters with accents kept, uppercase
  through JS here, since these are initials and not text; a missing part gives one
  letter; nothing at all gives `?`), with unit tests.
- [ ] `src/lib/components/Avatar.svelte`, per the spec: the `photo`, `name` and `size`
  props, `--avatar-size`, and a round `<img alt="">` or the initials. Tokens only, and
  `Avatar.test.js`.
- [ ] `Header.svelte`: the account pill for a logged-in person who is not staff (avatar,
  first name, a link to `/players/<id>`, and « Se déconnecter » using the same logout
  form as the ORGA pill), and the avatar inside the ORGA pill when the organiser is a
  person. Below 600px it goes into the menu panel, as the ORGA row does. Add the new keys
  to `fr.js` and `en.js` under `account.*`, and cover it in the header tests with one
  French assertion.
- [ ] `vite.config.js`: `server.proxy['/media']` to `API_URL`, read the way Vite config
  can (`loadEnv`), falling back to `http://localhost:3003`.
- [ ] The whole front suite and the build pass.

### Task 7: Claim page

**Spec:** Front → Claim page.

- [ ] `src/routes/claim/[uid]/[token]/+page.server.js`:
  - `load` calls `GET /claim/<uid>/<token>/`. A 404 renders the invalid-link state (not
    an error page), and any other failure throws.
  - The `claim` action checks the confirmation, posts the password and maps the error
    codes to `claim.error.<code>` (an unknown code gives `claim.error.invalid`). On
    success it sets the token cookie (`TOKEN_COOKIE`, `tokenCookieOptions()`) and
    redirects 303 to `/players/<user_id>`.
  - It forwards `X-Forwarded-For` the way the login action does, since the API throttles
    this view per IP. Share the helper instead of copying it.
- [ ] `+page.svelte`: the greeting, the username with a copy button, the two password
  fields, and the invalid-link state, per the spec, all through `t` with the `claim.*`
  keys. No tab bar on this route (`+layout.svelte`, as for `/login`).
- [ ] `page.server.test.js` (the 404 state, a mismatch, the mapped codes, the cookie and
  redirect, a 429) and `page.test.js` (both states, and one French rendering).
- [ ] The whole front suite and the build pass.

### Task 8: Avatars and showcase on public pages

**Spec:** Front → `Avatar.svelte` (placements) and `Showcase.svelte`.

- [ ] The fixtures (`src/lib/fixtures/players.js`, `summary.js`) gain `photo` and
  `showcase` in the server shapes of §6: some with a photo, some without.
- [ ] `src/lib/components/Showcase.svelte`, with two modes:
  - `interactive`: each medallion is a button that opens `BadgeSheet` for its slot, reusing
    how `BadgeCollection` opens it;
  - `row`: `aria-hidden` medallions at 20px.
- [ ] Profile page: the header avatar (`large`) and the showcase under the name, above
  the tabs, shown to every visitor. The owner hint for an automatic showcase comes in
  Task 10.
- [ ] Leaderboard rows (`/players`): the avatar (32px) before the name, and the showcase
  on a second line under the name below 600px, inline after it from 600px. A new
  `showcaseLabel` helper in `players.js` builds the showcase part of the row's hidden
  sentence (« vitrine : Champion, … »), with unit tests.
- [ ] Team page roster: the avatar (24px) next to each name. `BadgeSheet`'s Comrades
  line: the partner's avatar (24px).
- [ ] Update the text-shape assertions this changes in the same commit, and add French
  tests for the new sentence.
- [ ] The whole front suite and the build pass.

### Task 9: Photo editor (owner)

**Spec:** Front → Profile page, owner view, "Photo".

- [ ] `players/[id]/+page.server.js` gains the `photo` and `removePhoto` actions:
  - read the token cookie, and refuse when there is none or `params.id` is not the
    caller's (check against `/me/`);
  - forward the upload to `PUT /me/photo/` as multipart, or send `DELETE`;
  - map the §5 error codes to `photo.error.<code>`, return `fail(status, {action, error})`
    or `{ok, action}`.

  Add a multipart-capable helper to `src/lib/api.js` (or extend the existing one) with
  tests. `apiGet` and `apiPost` must behave exactly as before.
- [ ] `src/lib/components/PhotoEditor.svelte`, a dialog built like `BadgeSheet`: a bottom
  sheet below 1000px, focus trapped, focus returned to the opener, scroll locked.
  - A file input (`accept="image/jpeg,image/png,image/webp"`).
  - A circular crop on `<canvas>`: drag to pan, a zoom slider, and the arrow keys and
    `+`/`-`.
  - « Enregistrer » exports a 512 × 512 JPEG (`toBlob`, quality 0.9) and submits it as
    `FormData` to `?/photo`, then runs `invalidateAll()` on success.
  - « Supprimer ma photo » appears when there is a photo.
  - The public-visibility line.
  - The locked state per the spec.

  Put the crop maths (the cover scale, pan clamping, the source rectangle) in a pure helper
  (`src/lib/crop.js`) with unit tests. jsdom has no canvas, so component tests stub
  `HTMLCanvasElement.prototype.getContext` and `toBlob`.
- [ ] Profile page: the camera button on the header avatar, shown only when `me?.id ===
  profile.id`. Test that the owner sees it and a visitor doesn't, plus a French test.
- [ ] The whole front suite and the build pass.

### Task 10: Showcase editing (owner)

**Spec:** Front → Profile page, owner view, "Showcase editing", and the automatic hint.

- [ ] The `showcase` action in `players/[id]/+page.server.js` has the same owner check and
  posts `{codes}` to `PUT /me/showcase/`. « Revenir à l'automatique » posts `[]`.
- [ ] `BadgeCollection` gains a selection mode, used only by the owner. Earned slots
  become `aria-pressed` toggle buttons with a 1–3 order chip, locked slots are disabled,
  and a 4th pick shows « 3 badges maximum » in a status line. « Enregistrer », « Annuler »
  and « Revenir à l'automatique » close the mode. It starts from the current pins, or
  from none when the showcase is automatic.
- [ ] The owner hint « Automatique : vos badges les plus rares » under an automatic
  showcase.
- [ ] Tests: the selection mode (order chips, the limit, cancel), the action (the owner
  check, the codes posted), the hint shown only to the owner, and one French test.
- [ ] The whole front suite and the build pass.

---

## Task 11: Merge, docs, final review (controller)

- [ ] Merge `claude/ppc-front` into `claude/player-profile-customization-f4a2l5`. Run
  both suites and the build.
- [ ] Update `CLAUDE.md` for the new model, endpoints, permission default, config values,
  front components and routes, in its existing voice.
- [ ] Review the whole branch against the spec, then push.
