# Player profile customization: accounts, photo and badge showcase

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
    **nginx already serves `/media/` in prod.**
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
    `badge_stats(...)["holders"]`; ties go to the higher tier held, then to catalogue
    order.
  - Each showcase entry is drawn like a collection slot's medallion: the entry with the
    highest tier, else the first entry. That keeps the metal, the pips and the discipline
    icon of `specialist`.

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
  closed unless it is deliberately opened.

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
- Pillow joins `requirements.txt`, since `ImageField` needs it.

### 3. Photo processing (`olympic_warriors/avatars.py`)

`store_photo(profile, upload)`:
- refuses the upload unless `photo_locked` is off;
- refuses anything over 2 MB, or anything whose Pillow format is not JPEG, PNG or WebP;
- refuses anything over 4096 × 4096 before decoding, guarding against decompression
  bombs;
- applies `ImageOps.exif_transpose`, converts to RGB, centre-crops to a square in case
  the browser sent something else, and resizes to 512 and 128 with LANCZOS;
- saves WebP at quality 82, which leaves no EXIF (and so no GPS) behind;
- writes both new files, updates the row, then deletes the old files after the
  transaction commits (`transaction.on_commit`).

`remove_photo(profile)` clears both fields and deletes the files the same way. Both
functions live here and not in `save()`, because they touch the filesystem, not business
rules.

### 4. Claim flow (`olympic_warriors/claims.py`, views in `views.py`)

- `claim_link(user)` returns the URL, or raises for an unclaimable user. The public base
  URL is a new config value, `PUBLIC_URL` (for example
  `https://olympicwarriors.com`), required in `ProdConfig` and defaulting to
  `http://localhost:5173` in `DevConfig`.
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
  password), which the front maps to dictionary keys. Then, in one transaction, it:
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
  user or superuser, a deactivated user, or a user who is not a person. The same action
  goes on `UserProfileAdmin` for re-issuing links.

### 5. Player endpoints

- `GET /me/` (`IsAuthenticated`) returns `{id, first_name, last_name, username,
  is_staff, is_person, photo: {large, small} | null, photo_locked, showcase:
  {auto, codes}}`. `username` goes to its owner only.
- `PUT /me/photo/` (`IsAuthenticated`, multipart `photo`) calls `store_photo`. It answers
  403 (`{"error": "photo_locked"}`) when `photo_locked` is set, 400 `{"error": code}`
  for a bad upload (`missing`, `too_large`, `bad_format`, `too_many_pixels`), and 404 when the user is not
  a person. It is throttled at **10/hour per user** (a `UserRateThrottle` scope,
  `PHOTO_THROTTLE_RATE`) so nobody can fill the volume.
- `DELETE /me/photo/` (`IsAuthenticated`) calls `remove_photo`. It works even when the
  profile is locked: a player can always take their own face down.
- `PUT /me/showcase/` (`IsAuthenticated`, `{codes: [...]}`) accepts 0 to 3 distinct
  codes, each currently earned by the caller, and answers 400 `{"error":
  "invalid_showcase"}` otherwise (404 for a user who is not a person). `[]` means "back
  to automatic". The order is kept. It returns the new `{auto, badges}` showcase.

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
- The summary's roster players gain `photo` (the small URL or `null`) through
  `select_related("user__profile")` on the existing players query, so `SUMMARY_QUERIES`
  is unchanged.
- URLs are site-relative (`/media/avatars/…`). nginx serves them on the public host. In
  dev, `vite.config.js` proxies `/media` to `API_URL`.
- No payload carries `photo_locked`, `claimed_at` or `username`, except `/me/`.

### 7. Admin (`UserProfileAdmin`)

- **Columns:** name, a thumbnail (`format_html` of the small URL), `photo_locked`
  (editable in the list), `claimed_at` and `updated_at`.
- **Search** by name. **Filters:** `photo_locked`, has a photo, claimed.
- **Actions:**
  - « Retirer la photo » calls `remove_photo` for the selection.
  - « Retirer et verrouiller » removes the photo and sets `photo_locked`.
  - « Générer un lien d'activation » (see above).
- **Change form:** the photo fields are read-only (the thumbnail and a link to the full
  size), with no upload widget, per decision 10. `showcase` is read-only too, since
  badges are earned and there is nothing to moderate.

## Front

### Session

- The root `+layout.server.js` replaces `resolveOrganiser` with `resolveViewer`, which
  calls `/me/` and returns `organiser` (`is_staff`) and `me` (`{id, first_name, photo,
  is_person}` or `null`). The drop-on-401/403 and keep-on-outage rules stay as they are.
  `+layout.svelte` puts `me` in context under `ME` (`useMe()`, init only), next to
  `ORGANISER`.
- **Header pill slot:**
  - A visitor keeps `Connexion`.
  - An organiser keeps the `ORGA` pill.
  - A logged-in person gets an **account pill**: `Avatar` plus first name, linking to
    `/players/<me.id>`, with « Se déconnecter » beside it. Below 600px the pill folds into
    the menu panel, as the ORGA row does.
  - An organiser who is also a person keeps `ORGA` and gets their avatar in it.

### Claim page `/claim/[uid]/[token]`

- `+page.server.js` loads `GET /claim/…/`. A 404 renders « Ce lien n'est plus valide :
  demandez-en un nouveau à un organisateur ».
- The page reads « Bonjour Léa », then « Votre identifiant : **leamartin** » (with a copy
  button), then the password and confirmation fields and « Activer mon compte ».
- The `claim` action checks that the two passwords match, posts to the API and maps the
  validator messages to the dictionary. On success it stores the token cookie
  (`tokenCookieOptions`) and redirects 303 to `/players/<user_id>`.
- `+layout.svelte` gives the route no tab bar, as for `/login`.

### `Avatar.svelte`

- Props: `photo` (a URL or `null`), `name` and `size` (it sets `--avatar-size`).
- It renders a round `<img alt="">` (the name is always printed next to it), or the
  initials in `--muted` on `--bg-sunken` with a `--line` ring. Tokens only.
- It is used on the profile header (large, 96 px on phones and 128 px from 600px), the
  leaderboard rows (small, 32 px), the team roster (small, 24 px), the account pill
  (small, 24 px) and the Comrades line of `BadgeSheet` (small, 24 px).

### Profile page, owner view

`owner = me?.id === profile.id`, derived in the page. Nothing else changes for a
visitor.

- **Photo.** A camera button overlays the header avatar (« Changer ma photo »). It opens
  `PhotoEditor`, a dialog built like `BadgeSheet`: a bottom sheet below 1000px, focus
  trapped, focus returned to the button afterwards. Inside:
  - a file input (`accept="image/jpeg,image/png,image/webp"`; iOS hands HEIC over as
    JPEG);
  - a circular crop on a `<canvas>`: drag to move, a zoom slider, and arrow keys and
    `+`/`-` for the keyboard;
  - « Enregistrer », which exports a 512 px square JPEG (quality 0.9) and posts it as
    `FormData` to the page's `photo` action;
  - « Supprimer ma photo » when there is one;
  - the line « Votre photo sera visible publiquement sur le site. ».

  When `photo_locked` is set, the dialog shows « L'ajout de photo a été désactivé par un
  organisateur » and only the delete button. The `photo` and `removePhoto` actions in
  `players/[id]/+page.server.js` read the token cookie, refuse when the id is not the
  caller's, forward to the API and return `fail(status, {action, error})` with a
  dictionary key. The page then re-runs the loads (`invalidateAll`).
- **Showcase editing.** The Badges tab gains « Choisir ma vitrine ». In selection mode:
  - earned slots become toggle buttons with `aria-pressed` and a 1–3 order chip;
  - locked slots are disabled;
  - a fourth pick is refused with a status line (« 3 badges maximum »);
  - « Enregistrer », « Annuler » and « Revenir à l'automatique » close the mode.

  The `showcase` action posts the codes.

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
  `initials(name)` in a new `avatar.js`, both unit-tested.
- **Text shapes** to update in the same commit:
  - the leaderboard row gains the showcase names in its link name;
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
- **Server:**
  - `test_permissions.py` (the walk above);
  - `test_claims.py`: the token lifecycle, staff refused, the old token deleted, the
    validators, the throttle;
  - `test_avatars.py`: EXIF rotation and stripping, the size and format refusals, the
    bomb guard, old files deleted on commit, the lock;
  - `test_showcase.py`: the pins filtered to earned codes, the fallback to automatic,
    the rarity order, the 400s;
  - the query-count constants.

## Rollout

1. **The API lock-down alone** (§1): a server-only PR, safe today because the front reads
   only public views and `/user/current/`, which organisers still pass.
2. **Server:** `UserProfile`, photos, showcase, claims and the new payload fields.
   Additive, so an older front ignores them.
3. **Front:** `/me/`, the claim page, `Avatar`, `PhotoEditor` and `Showcase`.
4. **Prod:**
   - `PUBLIC_URL` in `prod.env`;
   - rebuild the server image (Pillow);
   - optionally, `location /media/avatars/ { expires max; }` in the host nginx, since the
     names are immutable;
   - `client_max_body_size` stays at its default (uploads are about 60 KB);
   - add `mediafiles` to the host's backup, if it isn't there already, now that it holds
     data players cannot re-create from the admin.

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
