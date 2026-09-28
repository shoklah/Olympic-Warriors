# Player profile customization: accounts, photo and badge showcase

> **Status:** shipped. The server and the front merged into `dev` together in PR #105; PR #107
> followed up (the photo editor on the shared `modal` action, one `SHOWCASE_SIZE`, the claim
> POST's unreadable body, these docs). Where this record and the code part, the notes marked
> "pinned while implementing", "as shipped" or "since shipping" say what the code does.

## Goal

Let players personalise their public profile with **a photo** and **a showcase of three
badges**. Players edit their own profile after claiming an account; organisers moderate
from the admin.

Today players cannot log in at all. Every user created by the registration import or by
`import_edition` gets a random 8-character password that nobody receives, and nothing
sends email. A token is effectively an organiser's token. This spec therefore has
three parts:

1. **Lock the API**, so a player's token can reach only what a player may see.
2. **Player accounts**, handed out by organisers through claim links.
3. **The customization**: photo and showcase.

Decisions taken while grilling (2026-09-24):
1. **Players and organisers both edit.** Players customise their own profile, and
   organisers moderate in the admin.
2. **Scope: the photo and the badge showcase.** No nickname, bio, colour, banner or
   leaderboard opt-out, so there is no free text to moderate.
3. **First access through a claim link** that an organiser creates in the admin and sends
   however they like (WhatsApp, Messenger). No email.
4. **Login is username and password.** The claim page shows the username and lets the
   player choose a password, and login goes through the existing `/auth/token/` and
   `/login`.
5. **The API becomes staff-only by default.** `IsOrganiser` is the global
   `DEFAULT_PERMISSION_CLASSES`, and the few views a player may use opt in explicitly.
6. **Staff accounts cannot be claimed.** Organisers keep their own passwords.
7. **A used claim link sets a new password and ends every session.** Links are Django
   password-reset tokens, with nothing stored.
8. **Editing happens on the player's own profile page.** There is no settings route.
9. **Photos go live at once.** Organisers can remove one and lock the person out of
   uploading.
10. **Organisers never upload a photo.** Every face on the site was put there by its owner
    (droit à l'image).
11. **The photo shows** on the profile header, the leaderboard rows, the team page
    rosters, the header account pill and the Comrades partner in the badge sheet.
    **nginx already serves `/media/` in prod.** (Since shipping: the photo URLs are
    site-relative, so it is the front's public host that must serve `/media/avatars/`; see
    Rollout.)
12. **Crop and shrink in the browser.** The server still validates and re-encodes.
13. **The showcase holds 3 badges.** It shows on the **profile header** and on the
    **leaderboard rows** (a second line under the name on phones). Pins are by **badge
    code**. Until a player pins anything, it shows their **3 rarest badges**.

## Definitions

- **Person.** As in the player profiles spec: a user with an active `Player` in an active
  edition. Only a person has a profile page, so only a person can be sent a claim link.
- **Claimable user.** A person who is `is_active` and neither `is_staff` nor
  `is_superuser`.
- **Claim link.** `<PUBLIC_URL>/claim/<uidb64>/<token>`, where `token` comes from Django's
  `default_token_generator`. The token is a hash of the user's password hash,
  `last_login`, email and the timestamp. It stops working once the password changes, expires
  after `PASSWORD_RESET_TIMEOUT` (set to **7 days**), and needs no table. Issuing a new
  link does not revoke older unused ones: they all die when any of them is used.
- **Claimed.** The user has set a password through a claim link.
  `UserProfile.claimed_at` records when, and the admin shows it.
- **Photo.** A square image in two sizes: `large`, 512 px, for the profile header, and
  `small`, 128 px, everywhere else. Both are WebP files under `mediafiles/avatars/`, named
  `<user id>-<random 12>.webp` and `…-sm.webp`. A new upload gets new names, so a URL
  never changes content and can be cached forever.
- **Earned codes.** The codes of a person's active badges of active editions, the same
  filter as `profile_badges`.
- **Showcase.**
  - **Pinned**: the stored codes (at most 3, in the player's order) that are still
    earned. When the player has pins and none of them is still earned, the showcase is
    automatic instead.
  - **Automatic**: the person's 3 rarest earned codes. Rarer means fewer holders in
    `badge_stats(...)["holders"]` over the leaderboard's people, the profile's rarity
    counts; ties go to the higher tier held, then to catalogue order.
  - Each showcase entry is drawn like a collection slot's medallion: the entry with the
    highest tier, the first one among equals. That keeps the metal, the pips and the
    discipline icon of `specialist`.

## Backend

### 1. API lock-down (can ship first, on its own)

- `settings.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'] = ['olympic_warriors.permissions.IsOrganiser']`.
- The public views keep `@permission_classes([AllowAny])` and do not change.
- The views a player uses opt in with `@permission_classes([IsAuthenticated])`:
  `/me/`, `/me/photo/` and `/me/showcase/` (all new).
- The token-only game, round and result read views that read through `_games()`,
  `_rounds()` and `_results()` also keep `IsAuthenticated` explicitly. They already apply
  the reveal rule to a player token and carry nothing the public summary does not, so
  `test_reveal.py`'s player-token cases stay as they are (decided while planning,
  2026-09-24).
- `/user/current/` becomes staff-only through the default. The front switches to `/me/`,
  so a player never needs it.
- `ThrottledObtainAuthToken` keeps DRF's `permission_classes = ()`, and the swagger
  schema keeps drf-spectacular's own `SERVE_PERMISSIONS`.
- Existing tests that call a token-only view with a non-staff user now get 403. They switch
  to a staff user. A new `test_permissions.py` walks `urls.py` and asserts that every
  routed view is one of three things: public (in an explicit allow-list), player-level
  (in an explicit allow-list), or answers 403 to a non-staff token. A new view is then
  closed unless it is deliberately opened. Pinned while implementing: the walk enters every
  `include()` but the admin's, calls every method a view handles, OPTIONS included (except
  on the Swagger page, whose OPTIONS rendering is a 500 whoever calls), checks that each
  sample URL resolves to its own view, and fails if any call creates a `UserProfile` row.
- Pinned while implementing: `_games()`, `_rounds()` and `_results()` also leave out every
  row of an inactive edition (whose summary is a 404), so the player-level reads really
  carry nothing the public summary does not.

### 2. `UserProfile` model (`models/UserProfile.py`, one migration)

```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    photo = models.ImageField(upload_to="avatars/", blank=True)        # 512 px
    photo_small = models.ImageField(upload_to="avatars/", blank=True)  # 128 px
    photo_locked = models.BooleanField(default=False)
    showcase = ArrayField(models.CharField(max_length=32, choices=Badge.Codes.choices),
                          size=3, default=list, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
```

- The row is created lazily with `get_or_create` on the first claim or edit. No signal,
  no backfill, and a missing row reads as no photo, automatic showcase, unclaimed.
- It has no `is_active`: it is a one-to-one satellite of `User`, and
  `request_only_active` would filter its changelist on a field it lacks. Its admin
  therefore does not call `request_only_active`.
- `transfer.NOT_EXPORTED` gains `"UserProfile"`. It is data about a person, not an
  edition, and it lives on prod only.
- Pillow joins `requirements.txt`, since `ImageField` needs it (so the server image is
  rebuilt).
- The migration is `0035_userprofile`. `showcase`'s choices are `Badge.Codes.choices`, so a
  catalogue change migrates this field too: dev's `master` badge (`0035_badge_master`)
  joined it through `0037_alter_userprofile_showcase`, after the merge migration `0036`.
  A migration that removes a code (as `0034` did for Badge rows) should also drop it from
  the stored pins; left there, it is harmless (the showcase shows earned codes only, and
  the admin prints an unknown code as is).

### 3. Photo processing (`olympic_warriors/avatars.py`)

`store_photo(profile, upload)` raises `PhotoError`, whose `code` is what the API answers
(the checks as shipped, pinned while implementing):
- refuses the upload unless `photo_locked` is off (`photo_locked`), checked on the profile
  given and again on the row re-read under `select_for_update`, so a lock set meanwhile
  still refuses it;
- refuses a missing file (`missing`) and anything over 2 MiB (`MAX_BYTES`, 2 × 1024 × 1024,
  `too_large`);
- lets only the JPEG, PNG and WebP parsers read the upload (`Image.open(..., formats=...)`)
  and refuses anything else, or anything they cannot read (`bad_format`); a JPEG carrying
  extra pictures, as some phone cameras write, opens as MPO and is accepted, its first
  picture used;
- refuses more than 4096 × 4096 pixels **in total** (`MAX_PIXELS`, width × height, so one
  side may exceed 4096), read from the header between `open()` and `load()`, before any
  decoding, against decompression bombs; Pillow's own bomb warning and error count as the
  same refusal (`too_many_pixels`);
- decodes a JPEG through `draft("RGB", (1024, 1024))`, the smallest DCT scale keeping both
  sides at least twice the large size, cheap on memory for a big photo;
- turns the picture upright from its EXIF orientation through its own table (`UPRIGHT`,
  what `ImageOps.exif_transpose` does, without rewriting the EXIF, which raised on some
  malformed blocks); an unreadable block or orientation means no turn, never a refusal;
- centre-crops to a square in case the browser sent something else (before turning: a
  centred square turns into the centred square of the turned image), flattens any
  transparency onto mid grey (128, 128, 128: it reads as a disc on both themes, and it is
  the grey the browser's export fills with), converts to RGB and clears `info`, so no
  EXIF (and so no GPS), ICC profile or XMP survives;
- resizes to 512 with LANCZOS, then 128 from the 512, and saves WebP at quality 82;
- writes both new files, updates the row, then deletes the old files after the
  transaction commits (`delete_on_commit`: one robust `transaction.on_commit` callback per
  file, so a file that cannot be deleted is logged and fails nothing); if its own block
  fails, it deletes the files it wrote at once.

`remove_photo(profile)` clears both fields and deletes the files the same way, locked or
not, reading the row under lock too, and returns whether there was a photo (without one it
writes nothing). Both functions live here and not in `save()`, because they touch the
filesystem, not business rules. A deleted profile, its user's cascade included, takes its
files with it: a `post_delete` receiver in `signals.py` (pinned while implementing).
`photo_urls(profile)` (`{large, small}` or `None`) and `small_photo_url(profile)` read the
URLs with no query.

### 4. Claim flow (`olympic_warriors/claims.py`, views in `views.py`)

- `claim_link(user)` returns the URL, or raises `Unclaimable` (a `ValueError` carrying
  the `reason`) for an unclaimable user. The public base URL is a new config value,
  `PUBLIC_URL` (for example `https://olympicwarriors.com`), defaulting to
  `http://localhost:5173` in `DevConfig`. It is **optional** everywhere else (empty by
  default), so a deploy never fails on it: `Dockerfile.prod` and `Dockerfile.stage` run
  `collectstatic` with `ENV=prod` against `prod.env`. Without an absolute `http(s)`
  address, `claim_link` raises `ImproperlyConfigured` and the admin action refuses (decided
  in review, 2026-09-24).
- One view serves both methods. It is `AllowAny` and ignores any token header
  (`authentication_classes([])`): the link is the credential, and a stale token forwarded
  by the front must not turn the claim page into a 401.
- `GET /claim/<uidb64>/<token>/` returns `{first_name, username}`, or 404
  `{"error": "invalid_link"}` for a bad user id, an unclaimable user, or an invalid or
  expired token. The 404 is the same in every case, so the endpoint does not reveal who
  exists. The GET is **not throttled** (decided while implementing, 2026-09-24): it
  answers only for a valid token, which cannot be guessed, and the claim page re-runs it
  after each refused POST, which would otherwise spend the login budget twice per attempt.
- `POST /claim/<uidb64>/<token>/` takes `{password}` and counts against the login
  throttle: `ClaimRateThrottle` in `throttling.py` is `LoginRateThrottle` on POST only,
  with the same scope and rate, so claim POSTs, `/auth/token/` and the admin login share
  one per-IP budget. It checks the link first (a dead link is the 404 whatever the
  password), then runs `validate_password(password, user)` with the four validators
  already configured. A failure is a 400 `{"errors": [<Django error code>, ...]}`
  (`password_too_short`, `password_too_common`, `password_entirely_numeric`,
  `password_too_similar`, or `password_missing` for an absent, blank or non-string
  password), which the front maps to dictionary keys. A body that cannot be parsed at all
  (not JSON) is the same `password_missing` 400, after the link check (fixed in #107: it
  was DRF's own `{"detail": ...}`, which the front could not map). Then, in one transaction, it:
  - re-reads the user under a row lock and re-checks the token and claimability, so two
    uses of one link racing each other set one password, and a user made staff or
    deactivated in between gets the same 404;
  - calls `set_password` and `save`;
  - deletes the user's DRF `Token` and creates a fresh one;
  - stamps `claimed_at`.

  It returns `{token, user_id}`, and the old token and every old session are gone.
- **Admin action** « Générer un lien d'activation » on `PlayerAdmin`, where organisers
  already work edition by edition. For each selected player's user (several players of
  one person make one line, users in name order) it adds one message line,
  `Léa Martin (leamartin) : <link>`, and skips with a warning line, naming why, a staff
  user or superuser, a deactivated user, or a user who is not a person. Without a usable
  `PUBLIC_URL` it makes no link and shows one error line, « Aucun lien généré : PUBLIC_URL
  (l'adresse publique du site) n'est pas configuré. ». A link lets whoever opens it set
  the person's password, so the action needs `auth.change_user` (`has_claim_permission`),
  whatever the organiser's rights on players or profiles. The same action goes on
  `UserProfileAdmin` for re-issuing links (both through the `ClaimLinksPermission` mixin).
  The links travel only in Django's messages, never logged. The action checks `PUBLIC_URL`
  (`public_url()`) before any user, so without it the one error line is all it says.

### 5. Player endpoints

- `GET /me/` (`IsAuthenticated`) answers any logged-in user, an organiser who never played
  included (`is_person` false): `{id, first_name, last_name, username, is_staff,
  is_person, photo: {large, small} | null, photo_locked, showcase: {auto, codes}}`.
  `username` goes to its owner only. `showcase` is the stored pins as the person left
  them: `codes` in order, `auto` true when there is none. The badges shown are computed on
  the profile, where a pin no longer earned drops out. The front calls `/me/` on every page,
  so it computes no badge, standing or leaderboard: after the token, one query reads the
  profile row and the person flag (`ME_QUERIES` in `test_me.py`), and a missing row is
  never created here (decided while implementing, 2026-09-24).
- `PUT /me/photo/` (`IsAuthenticated`, multipart `photo`) calls `store_photo`, creating the
  row on the first upload it stores (a refused upload leaves no row: the creation rolls back
  with the refusal), and answers 200 `{photo: {large, small}}`. It answers 404
  (`{"error": "not_a_person"}`) when the user is not a person, then 403 (`{"error":
  "photo_locked"}`) when `photo_locked` is set, and 400 `{"error": code}` for a bad upload
  (`missing`, `too_large`, `bad_format`, `too_many_pixels`). A body whose `Content-Length`
  exceeds 2 MiB plus `MULTIPART_ALLOWANCE` (64 KiB: the multipart envelope around the file
  takes a few hundred bytes, the rest leaves room for a long file name) is `too_large`
  before a byte of it is read, so nobody makes the server parse megabytes only to refuse
  them; the lock is checked before that too. It is throttled at **10/hour per user** (a
  `UserRateThrottle` scope, `PHOTO_THROTTLE_RATE`), every PUT counting, refused or not, so
  nobody can fill the volume. DRF checks throttles before the view runs, so a throttled PUT
  is a 429 before any of the answers above.
- `DELETE /me/photo/` (`IsAuthenticated`) calls `remove_photo` and answers 204 with no
  body, with or without a photo, and creates no row. It works even when the profile is
  locked, and it is never throttled: a player can always take their own face down. A user
  who is not a person gets the 404.
- `PUT /me/showcase/` (`IsAuthenticated`, JSON `{codes: [...]}`) accepts 0 to 3 distinct
  codes, each currently earned by the caller, and answers 400 `{"error":
  "invalid_showcase"}` otherwise: not a list, more than 3, a duplicate, a non-string, a code
  outside the catalogue, a code not earned, or an unreadable body. A user who is not a
  person gets the 404. `[]` means "back to automatic". The order is kept. It returns the
  new `{auto, badges}` showcase. Its rarity counts are `badge_stats` over the
  leaderboard's people, as on the profile, read through `profiles.person_ids()` (the same
  people, one query, without computing the leaderboard), so it runs in a fixed number of
  queries (`SHOWCASE_PUT_QUERIES` in `test_me.py`). It writes the showcase field alone, so a
  photo stored meanwhile survives.

### 6. Payload changes (public)

- `/profile/<id>/` gains `photo: {large, small} | null` and `showcase: {auto, badges:
  [{code, tier, discipline}]}`. It also gains `partner.photo` (the small URL or `null`)
  on `comrades` entries. The partner join rides on `profile_badges`'s existing
  `select_related` (`partner__profile`), so the query count is unchanged.
- `/profiles/` rows gain `photo` (the small URL or `null`) and `showcase: [{code, tier,
  discipline}]` (no `auto` flag, since nobody edits from the leaderboard). The badges
  come from a new bulk `badges_by_user(user_ids)` (1 query) plus the `badge_stats` the
  profile already uses (1 query). `PROFILES_QUERIES` becomes `4 + 3 × finished editions
  with players`, and `leaderboard()`'s players query gains `select_related("user__profile")`.
  Pinned while implementing (2026-09-24):
  - A row's `showcase` is exactly the `badges` of that person's profile showcase: the same
    pins, and rarity counted over the same people.
  - Both endpoints now run `PROFILES_QUERIES`: the profile already ran two queries on top
    of `leaderboard()`, and still does. `leaderboard()` alone stays at `2 + 3 × finished
    editions with players` (`LEADERBOARD_QUERIES` in `test_profiles.py`). The players query
    is `profiles._load`'s, shared with `badges.earned()`, whose count is unchanged too.
  - Since dev's all-time discipline tables (merged into this branch before PR #105),
    `/profile/<id>/` reads the leaderboard through `profiles.profile_record()`, which counts
    the person's running editions in their discipline places: the profile runs
    `PROFILES_QUERIES` plus 3 per running edition in which the person has a team, and
    `/profiles/` runs `PROFILES_QUERIES` alone.
  - `PlayerRecord` carries `photo` (`{large, small}` or `None`) and `pins` (the stored
    codes, earned or not), read from the joined profile row. Every Player row of a person
    points at the same user, so it does not matter which one stands for an edition.
  - With nobody on the leaderboard, `/profiles/` runs no badge or rarity query.
- The summary's roster players gain `photo` (the small URL or `null`) through
  `select_related("user__profile")` on the existing players query, so `SUMMARY_QUERIES`
  is unchanged.
- The keys are always there, so an older client reads one shape: `photo` is `null` without
  a profile row or a photo, a row's `showcase` is `[]` and the profile's is `{auto: true,
  badges: []}` without a badge.
- URLs are site-relative (`/media/avatars/…`), so they resolve against the front's public
  host, where nginx must serve them (see Rollout). In dev, `vite.config.js` proxies
  `/media` to `API_URL` (`changeOrigin`, since the API's `ALLOWED_HOSTS` knows its own
  host).
- No payload carries `photo_locked`, `claimed_at` or `username`, except `/me/`. The stored
  pins as such (`codes`) go to `/me/` only: a pin no longer earned never shows elsewhere.
  `test_showcase.py` walks the public payloads for these keys and for the email:
  `/profiles/`, two `/profile/<id>/`, a summary, and dev's `/discipline/<id>/all-time/`,
  which lists people too.

### 7. Admin (`UserProfileAdmin`)

- **Columns:** name, a thumbnail (`format_html` of the small URL), `photo_locked`
  (editable in the list), `claimed_at` and `updated_at`.
- **Search** by name (and username). **Filters:** `photo_locked`, has a photo, claimed.
- **No add:** rows come from the claim and edit flows only. The changelist does not go
  through `request_only_active` (no `is_active`).
- **Actions:**
  - « Retirer la photo » calls `remove_photo` for the selection.
  - « Retirer et verrouiller » sets `photo_locked`, then removes the photo, in one
    transaction per profile, so an upload waiting on the row finds the lock.
  - « Générer un lien d'activation » (see above).
  - Pinned while implementing: the stock bulk delete is removed (`get_actions`), since next
    to « Retirer la photo » it would drop whole rows, pins and claim date with them; a
    profile can still be deleted from its own page, its files going with it.
- **Change form:** the photo fields are read-only (the thumbnail and a link to the full
  size), with no upload widget, per decision 10. `showcase` is read-only too (the pins by
  name), since badges are earned and there is nothing to moderate. Only the lock is edited.
  Without a photo or pins it shows the admin's empty value, not "None" (fixed before the
  merge: the change form prints a read-only method's `None` as is).

## Front

### Session

- The root `+layout.server.js` replaces `resolveOrganiser` with `resolveViewer`, which
  calls `/me/` and returns `organiser` (`is_staff`) and `me` (`{id, first_name, last_name,
  photo, is_person, photo_locked}` or `null`: `last_name` for the initials of an avatar
  without a photo, `photo_locked` for the owner's photo editor; the username and the pins
  stay on the server, since layout data is serialised into every page). The
  drop-on-401/403 and keep-on-outage rules stay as they are, and a body without an `id`
  counts as a visitor too.
- As shipped, there is no `ME` context and no `useMe()` (both were planned, then dropped in
  #107 with no reader left): `+layout.svelte` hands `me` to `Header` as a prop, and the
  profile page reads `data.me` (the root layout's data merged into its own). A prop
  follows `invalidateAll()` after a new photo, where a context set at init would not.
  `ORGANISER` stays a context.
- **Header pill slot:**
  - A visitor keeps `Connexion`.
  - An organiser keeps the `ORGA` pill.
  - A logged-in person gets an **account pill**: `Avatar` plus first name, linking to
    `/players/<me.id>`, with « Se déconnecter » beside it (from 600px a round icon button
    carrying the words as its name and `title`). Below 600px the pill folds into the menu
    panel, as the ORGA row does: the profile link on the left, the logout as a pill on the
    right.
  - Someone logged in who is no longer a person (no active player row) gets the avatar and
    first name as plain text, with no link, beside the same logout.
  - An organiser who is also a person keeps `ORGA` and gets their avatar in it.

### Claim page `/claim/[uid]/[token]`

- `+page.server.js` loads `GET /claim/…/`, forwarding the visitor's address
  (`$lib/server/forwarded-for.js`, shared with `/login`). A 404 renders « Ce lien n'est plus
  valide : demandez-en un nouveau à un organisateur »; a 429 renders the login's throttle
  line.
- Pinned while implementing: the load sets `cache-control: private, no-store` (the URL is a
  live credential and the page shows the username), the page sets `<meta name="referrer"
  content="same-origin">`, and both link parts must match `^[A-Za-z0-9_-]{1,128}$` before
  they are spliced into an API path, anything else being the invalid state with no API
  call.
- The page reads « Bonjour Léa », then « Votre identifiant : **leamartin** » (with a copy
  button, which selects the name when the Clipboard API fails), then the password and
  confirmation fields and « Activer mon compte ». A hidden `username` field tells a
  password manager which account the password belongs to.
- The `claim` action checks that both fields are filled and the two passwords match,
  posts to the API and maps the validator codes to the dictionary (`err.body.errors`; an
  unknown code, or none, is one generic refusal). On success it stores the token cookie
  (`tokenCookieOptions`) and redirects 303 to `/players/<user_id>`. The form is a plain
  POST, never `use:enhance`, so the redirect reloads the whole page and the root layout
  reads the new cookie, as after `/login`; after a refused submit the page focuses the
  first field in error.
- `+layout.svelte` gives the route no tab bar (`NO_TAB_BAR`), as for `/login`.

### `Avatar.svelte`

- Props: `photo` (a URL or `null`), `name`, `size` (a number of pixels or a CSS length;
  it sets `--avatar-size`, which the page sets instead when it is left out) and `lazy`
  (`loading="lazy"`, for the leaderboard's long list). As shipped, `name` is the person
  object every payload carries, `{ first_name, last_name }`, and `initials(first, last)`
  in `avatar.js` reads it (`LM` for Léa Martin, accents kept, `?` for no name).
- It renders a round `<img alt="">` (the name is always printed next to it), or the
  initials in `--muted` on `--bg-sunken` with a `--line` ring, the whole `aria-hidden`.
  Tokens only.
- It is used on the profile header (large, 96 px on phones and 128 px from 600px), the
  leaderboard rows (small, 32 px, lazy), the team roster (small, 24 px), the account pill
  and the ORGA pill (small, 24 px), the Comrades line of `BadgeSheet` (small, 24 px) and
  the photo editor before a file is chosen (large, 160 px).

### Profile page, owner view

`owner = data.me?.id === profile.id` (as shipped, from `data.me`: there is no `me`
context), derived reactively in the page, which stays mounted from one profile to the
next. Nothing else changes for a visitor.

- **Photo.** A camera button overlays the header avatar (« Changer ma photo »). It opens
  `PhotoEditor`, a dialog on the `modal` action of `$lib/modal.js` that `BadgeSheet` and
  `ScoreSheet` share (#107; it first carried its own copy): a bottom sheet below 1000px,
  focus trapped, the page scroll locked, Escape and the backdrop ignored while a save or a
  delete is on its way, focus returned to the button afterwards. Inside:
  - a file input (`accept="image/jpeg,image/png,image/webp"`; iOS hands HEIC over as
    JPEG);
  - a circular crop on a `<canvas>`: drag to move, a zoom slider, and arrow keys (Shift for
    five times the step) and `+`/`-` for the keyboard. Pinned while implementing: the
    crop maths are pure functions in `$lib/crop.js` (`{zoom, cx, cy}` in source pixels,
    zoom 1 to 4), the picture is decoded at `decodeSize` (its shorter side at most 2048,
    512 × the highest zoom) rather than kept whole, and a decode that finishes after a
    newer pick is discarded;
  - « Enregistrer », which exports a 512 px square JPEG (quality 0.9), drawn on the same
    mid grey the server flattens transparency onto (`EXPORT_BACKGROUND`), and posts it as
    `FormData` to the page's `photo` action, by `fetch` with `x-sveltekit-action` (the
    way `use:enhance` does, since the file is a Blob made in the page, not a form field);
  - « Supprimer ma photo » when there is one;
  - the line « Votre photo sera visible publiquement sur le site. ».

  When `photo_locked` is set, the dialog shows « L'ajout de photo a été désactivé par un
  organisateur » and only the delete button. The `photo` and `removePhoto` actions in
  `players/[id]/+page.server.js` read the token cookie, refuse when the id is not the
  caller's, forward to the API and return `fail(status, {action, error})` with a
  dictionary key. The page then re-runs the loads (`invalidateAll`). As shipped, the
  owner check is `asOwner`, shared with the `showcase` action: it asks `/me/` and refuses
  with a 403 unless its id is the page's id as a canonical string, since the API's
  `/me/…` writes touch the caller's own profile whatever page posts. A 413 (a proxy's
  body limit) and a 429 map to their keys by status.
- **Showcase editing.** The Badges tab gains « Choisir ma vitrine ». In selection mode:
  - earned slots become toggle buttons with `aria-pressed` and a 1–3 order chip;
  - locked slots are disabled;
  - a fourth pick is refused with a status line (« 3 badges maximum »);
  - « Enregistrer », « Annuler » and « Revenir à l'automatique » close the mode.

  The `showcase` action posts the codes, after checking there are at most `SHOWCASE_SIZE`
  distinct known ones. Pinned while implementing: `BadgeCollection` takes `editable` and
  `showcase` props; « Annuler » and « Enregistrer » sit in a bar sticky at the bottom of
  the screen (above the tab bar on phones), whose `reserveRoom` action keeps its measured
  height as the page's `scroll-padding-bottom`, so a slot reached by Tab never hides
  behind it; « Revenir à l'automatique » sits under the intro while pins are stored.

### `Showcase.svelte`

- Three `Badge` medallions in pin order.
- **Profile header** (every visitor): under the name, above the tabs. Each medallion is a
  button that opens the existing `BadgeSheet` for its slot. When the showcase is
  automatic and the viewer is the owner, a quiet hint reads « Automatique : vos badges
  les plus rares ».
- **Leaderboard rows:** `aria-hidden` medallions at 20 px, on a second line under the
  name below 600px and inline after the name from 600px. Their names join the row's
  hidden sentence (« … vitrine : Champion, Marathonien, Réseauteur »), because the row is
  a single link and cannot hold buttons.
- A person with no badge shows no showcase line at all.

### i18n and tests

- **Keys** under `account.*`, `claim.*`, `photo.*` and `showcase.*`, in `fr.js` and `en.js`
  (`parity.test.js`).
- **Helpers:** `showcaseLabel` (the spoken sentence) goes in `players.js`, and
  `initials(first, last)` in a new `avatar.js`, both unit-tested. As shipped, the badge
  codes and `SHOWCASE_SIZE` (defined once) live in a glyph-free `badge-codes.js`, which
  `badges.js` re-exports: `badges.js` bundles every badge glyph, and `players.js`, which
  the ranking and team pages load, checks codes without pulling the glyphs into their
  chunks (`badge-codes.test.js`). `slotLabel` in `badges.js` names both a collection slot
  and a showcase medallion.
- **Text shapes** to update in the same commit:
  - the leaderboard row gains the showcase names in its link name (`…, average rank 1.5,
    showcase: Champion, Veteran, Networker`); an avatar's initials are `aria-hidden`, so a
    row or roster chip without a photo shows them (`BM Bob Martin`) but its link name does
    not;
  - the profile header gains the showcase buttons, named like the collection slots.
- **New tests:**
  - `claim/page.server.test.js`: the 404, a password mismatch, the validator errors and
    the cookie on success.
  - `PhotoEditor.test.js`: the locked state, the delete button, and the export called
    with 512 px.
  - `Showcase.test.js`: the pin order, and `aria-hidden` on rows.
  - The profile's `page.test.js`: the owner sees the camera and « Choisir ma vitrine »,
    a visitor does not, plus one French rendering.
  - `layout.server.test.js`: `/me/` replaces `/user/current/`.
  - As shipped, also `Avatar.test.js`, `avatar.test.js`, `crop.test.js`,
    `badge-codes.test.js`, `Header.test.js` (the account pill, the avatar in the ORGA pill,
    the menu row), `layout.test.js` (no tab bar on the claim page) and the claim page's
    `page.test.js`. Password and token fixtures stay plainly fake (`x`, `y`,
    `claim-token-demo`): GitGuardian flagged realistic ones in the claim tests.
- **Server:**
  - `test_permissions.py` (the walk above);
  - `test_claims.py`: the token lifecycle, staff refused, the old token deleted, the
    validators, the throttle;
  - `test_avatars.py`: EXIF rotation and stripping, the size and format refusals, the
    bomb guard, old files deleted on commit, the lock;
  - `test_showcase.py`: the pins filtered to earned codes, the fallback to automatic,
    the rarity order, `badges_by_user`, and `person_ids` against the leaderboard;
  - `test_me.py`: `/me/` and `ME_QUERIES`, the photo upload and its refusals (the body
    refused unread included), the delete, the photo throttle, the showcase's 400s and
    round trip;
  - `test_user_profile_admin.py`: the changelist, the lock, the filters, the actions, the
    change form, and the files deleted with a person (pinned while implementing);
  - the query-count constants (`ME_QUERIES = 2`, `SHOWCASE_PUT_QUERIES = 7`,
    `LEADERBOARD_QUERIES`, `PROFILES_QUERIES`; `SUMMARY_QUERIES` unchanged).

## Rollout

As planned:

1. **The API lock-down alone** (§1): a server-only PR, safe today because the front reads
   only public views and `/user/current/`, which organisers still pass.
2. **Server:** `UserProfile`, photos, showcase, claims and the new payload fields.
   Additive, so an older front ignores them.
3. **Front:** `/me/`, the claim page, `Avatar`, `PhotoEditor` and `Showcase`.
4. **Prod:**
   - `PUBLIC_URL` in the `prod.env` of both prod and stage (each its own public
     address); without it the site runs, but the admin makes no claim link;
   - rebuild the server image (Pillow);
   - optionally, `location /media/avatars/ { expires max; }` in the host nginx, since the
     names are immutable;
   - `client_max_body_size` stays at its default (uploads are about 60 KB);
   - add `mediafiles` to the host's backup, if it isn't there already, now that it holds
     data players cannot re-create from the admin.

As shipped: steps 1 to 3 went out together, the server and the front merged into `dev` in
PR #105, and PR #107 followed up (the photo editor on the shared `modal` action, one
`SHOWCASE_SIZE`, the claim POST's unreadable body, the docs). Deploying it:

- **Migrate:** `0035_userprofile`, the merge `0036_merge_20260924_2300` (with dev's
  `0035_badge_master`) and `0037_alter_userprofile_showcase`. Nothing runs migrations in
  production. Rebuild the server image first (Pillow).
- **Server before front.** A new front calls `/me/` on every page with a token; an old
  server answers it 404, which the front counts as a visitor, so organisers would lose
  their tools until the server catches up.
- **`PUBLIC_URL`** in the `prod.env` of prod and of stage, as planned.
- **nginx must serve `/media/avatars/` on the front's public host**, not only wherever
  `/media/` was served before: the photo URLs are site-relative, so the browser asks the
  front's host. For example `location /media/avatars/ { alias
  /home/app/web/mediafiles/avatars/; expires max; }` (where `docker-compose.prod.example.yml`
  mounts the media volume in the nginx container; stage's is under `/home/stage/web/`).
  Serve only public folders: `registration_forms/`, in the same volume, holds the
  registration CSVs with names and emails.
- **Upload limits:** adapter-node's default `BODY_SIZE_LIMIT` (512K) and nginx's
  `client_max_body_size` both clear the 512 px JPEG the editor sends.
- **Stage:** the template's `front-stage` has no `ORIGIN` (it was so before this feature),
  so SvelteKit refuses its form POSTs, now the claim, the photo and the showcase too, with
  a 403 until it gets one.
- **Backups:** add the `mediafiles` volume, as planned.

## Out of scope

- Changing a password while logged in: a new claim link covers a forgotten one.
- Email of any kind.
- A nickname, a bio, profile colours or a banner.
- Hiding yourself from the leaderboard.
- Organisers uploading photos or editing someone's showcase.
- An approval queue.
- Self-service account deletion: erasure goes through the organisers, and a player can
  always delete their own photo.
- Merging duplicate users (the same person under two usernames across editions).
