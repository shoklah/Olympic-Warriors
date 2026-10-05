# Team builder

Status: design, approved section by section in conversation on 2026-10-05. Builds on the in-app registration (`2026-10-04-in-app-registration-design.md`, `2026-10-05-registration-wizard-design.md`): the builder reads what registrants answered, including the two team-preference fields the wizard introduced for it.

## Goal

Give the organisers a page to turn the registered players of the latest edition into teams: propose balanced teams, honour the « avec » and « à éviter » requests where possible, let the organisers adjust by hand, and only then create the teams.

## Decisions

- **Auto-suggest, then adjust.** One click proposes teams; the organisers drag players between teams and re-roll. Nothing is fully automatic.
- **Front, organiser-only page** (`/<year>/builder`) with new staff-only API endpoints. Not a Django admin view.
- **Draft, then Apply.** Nothing touches `Team` or `Player.team` until an explicit « Créer les équipes ». The draft is **stored on the server** (one per edition), so a reload, another laptop or another organiser continues the same work.
- **The builder creates the teams.** The organiser picks the number of players per team (default 3); the team count follows. Team rows are created on Apply with placeholder names (« Équipe 1 »…), renamed later in the admin.
- **What is balanced:** the overall rating, each skill's total across teams, and the spread of experienced players (high sport frequency, competition-level sport history). Returning versus new players is **not** balanced.
- **Requests are soft.** They are weighed against balance, never break team sizes, and every unmet one is listed. Mutual « avec » count more than one-sided ones.
- **Free text becomes constraints through the organiser.** Names are fuzzy-matched to registrants and each link is confirmed, changed or discarded before it counts.
- **The generator and the scoring run in the browser**, as pure JS: one implementation drives both the proposal and the live feedback while dragging. The server stores the draft and applies it.
- **Latest edition only**, like every other organiser write (`latest_edition()`).
- **Disciplines that already exist** (they must, for the registration form): Apply **backfills** a `TeamResult` for each new team in every active discipline of the edition (`get_or_create`, as the base `Discipline.save()` does) and reports the disciplines that still need their games scheduled, since `Team.save()` creates no result and the schedulers read the teams at scheduling time. It does not schedule anything itself.
- **Roster changes under a saved draft are reconciled when the page loads**: departed players drop out of the draft's teams, links and locks, new registrants go to an « À placer » tray, and a banner says so (details under Front).
- **Existing teams: refuse.** An edition that already has teams is not rebuilt by the builder; corrections after Apply happen in the Player admin (`team` is editable in the changelist). The page says so and links there.
- **Missing answers fall back to the overall rating** and the card says so (details under The generator).
- **Applying while registration is open is a warning, not a block.**
- **Apply publishes at once.** `Team` has no hidden flag, so the new teams and their rosters are public as soon as they exist; the Apply panel says so, and the server-side draft is where organisers wait until they are ready. A reveal flag on the edition is a separate feature.
- **Late registrants are placed without a reshuffle.** Beside « Relancer » (which regenerates every unlocked player), « Placer les nouveaux » puts each player of the « À placer » tray into the best-scoring team among the smallest ones, leaving everyone else where they are.
- **Apply names the version it applies.** The page posts the `updated_at` of the draft it last saved or loaded; the server refuses a mismatch with 409 `stale_draft`, so one organiser's click never publishes another's draft. The page also disables Apply while the draft is stale or failing to save.
- **The raw request texts show on the player cards by default**, with a switch on the teams panel to hide them (a shared screen), remembered in the browser (`localStorage`, never on the server).
- **Two PRs, server then front**, both merged into `dev`; the UI is iterated on `dev` afterwards.
- Out of scope: announcing the teams (a copy button, a CSV, a shareable image: a visual to share is a likely later feature), placing late registrants after Apply (move them in the admin), team names or colours, changes to scoring or standings, a player-facing view of the draft.

## Server

### `TeamDraft`

`models/TeamDraft.py`, one row per edition (`edition` one-to-one, `related_name="team_draft"`), `document` (`JSONField`, default `{}`), `updated_by` (FK to `User`, null, `SET_NULL`), `updated_at` (`auto_now`). Not in the admin, not exported (`transfer.NOT_EXPORTED`, `test_transfer.py` enforces it), cascade-deleted with its edition. Its document is the browser's working state and the server only checks its shape:

```
{ "players_per_team": 3,
  "seed": 12345,
  "links": [{"player": <id>, "kind": "with"|"avoid", "target": <id>}],   // confirmed only
  "teams": [{"players": [<id>…]}],                                        // team order = name order
  "locked": [<id>…] }                                                     // players the re-roll never moves
```

Validation: `players_per_team` an integer 2 to 20, `seed` a non-negative integer below `2**31`, each id a player of that edition (active), `kind` known, no self link, `teams` a list of lists of distinct ids with no id twice across teams, `locked` a subset of the placed players, at most 200 links. A refusal is `{"errors": [codes]}` (`invalid_draft`, `unknown_player`, `bad_size`, `too_many_links`).

### Endpoints

All `IsOrganiser` (the default), `private, no-store`, only for `latest_edition()`'s year (another year is 409 `not_latest`, an unknown year 404). Routed by hand in `urls.py`, none in `test_permissions.py`'s `PUBLIC` or `PLAYER` lists, so the permission walk keeps them staff-only.

- `GET /builder/<year>/` → `{edition: {year}, skills: [{identifier, name_fr, name_en}], players: […], teams_exist, draft: {document, updated_at} | null}`. A player carries `id`, `first_name`, `last_name`, `rating`, `global_level`, `ratings` (`{identifier: n}`), `sport_frequency`, `sports` (`[{sport, level}]`), `team_with`, `team_avoid`, `team` (the id of a valid current team or null); the top level also carries `registration_open` (`registration_state` open for the edition, a late pass ignored), so the page can warn. It lists the **active** players of the edition and nothing else of the user (no username, no email). It runs a fixed number of queries whatever the roster (`BUILDER_QUERIES`).
- `PUT /builder/<year>/draft/` body `{document, based_on}` (`based_on`: the `updated_at` the page loaded, null for a first save). A mismatch with the stored `updated_at` is 409 `stale_draft` with the stored draft, so two organisers never silently overwrite each other. Success returns the new `{document, updated_at}`. `DELETE` clears it (204).
- `POST /builder/<year>/apply/` body `{based_on}` applies the **stored draft**, refusing with 409 `stale_draft` unless `based_on` is its current `updated_at`. In one transaction under a lock on the edition row it checks: a draft exists (409 `no_draft`) and is the version the caller saw (409 `stale_draft`); no active `Team` already exists for the edition (409 `teams_exist`); the draft's teams cover every active player exactly once (400 `incomplete`); sizes differ by at most 1 and there are at least 2 teams (400 `bad_size`). It creates `Team` rows named « Équipe 1 »… in team order, backfills their `TeamResult` rows in every active discipline of the edition, sets `Player.team` for every player (through `save()`, never `update()`, so the model's side effects run), deletes the draft and answers `{teams: [{id, name, players}], unscheduled: [{id, name}]}`, where `unscheduled` lists the active disciplines with a pairing system and no round yet (their results are backfilled, their games are not).

### Privacy

The payload carries the private registration answers (`team_with`, `team_avoid`, sports, frequency) and is therefore staff-only: a player's token gets 403, a visitor 401 (`test_permissions.py`). No public payload gains a field, so `PRIVATE_KEYS` is unchanged; a test walks the new routes for a non-staff token.

## Front

Route `/<year>/builder` (`routes/[year=year]/builder`), no tab bar (added to `NO_TAB_BAR`). Its `+page.server.js` redirects a visitor to `/login?next=…`, answers 403 for a logged-in non-organiser and 404 for a year that is not the latest, loads the builder payload with the organiser's token and sets `cache-control: private, no-store`. The draft is saved through the page's own form actions (`saveDraft`, `apply`, `clearDraft`), plain actions like the organiser tools. The organisers reach the page from a « Constituer les équipes » button on the latest edition's ranking page (organiser view only, shown while the edition has no team) and from a link on the Edition admin page.

**Three panels** (a progress `nav` like the registration wizard's, free movement between them):

1. **Demandes.** Each player's « avec » and « à éviter » text is split into names (on commas, semicolons, line breaks, « et », « & », « / ») and matched to the registered players: normalised (accents and case dropped), first the whole name, then the first name when it is unique, then a first name within one edit. Each request line shows its candidates, the best one pre-selected only when it is an exact whole-name or unique-first-name match; the organiser confirms, picks another player, or discards. Text that matches nothing (« peu importe », a friend who did not register) stays as a note on the player's card. Self matches are never offered. Confirmed links are the draft's `links`.
2. **Équipes.** « Players per team » (default 3, 2 to 20) and the resulting team count and sizes (sizes as even as possible, so they differ by at most 1; fewer than two teams is refused). The number is **fixed once teams are proposed**: changing it needs « Tout réinitialiser » (confirmed, naming how many placements and locks it discards), which clears the teams and the locks and keeps the confirmed links, since they are about people, not teams. « Proposer des équipes » runs the generator; « Relancer » re-runs it with a new seed. Players are dragged between teams (and moved with a menu for keyboard and touch), can be locked in place (the re-roll leaves them), and each team shows its size, average rating, its per-skill bars against the other teams, and the requests honoured or broken (the list of every unmet request sits above the teams).
3. **Appliquer.** A summary (teams, sizes, unmet requests) and « Créer les équipes ». It is disabled while a player is unplaced or in the « À placer » tray, while the draft is stale or failing to save, and refuses a stale draft with the server's message. While registration is open the panel shows « Les inscriptions sont encore ouvertes : les nouveaux inscrits n'auront pas d'équipe » and a checkbox to confirm before the button works (organisers sometimes build early; late people are placed in the Player admin, filtering on an empty team). After Apply the page lists the disciplines that still need scheduling (`unscheduled`), each linking to its admin page.

**An edition that already has teams** shows only a message, « Cette édition a déjà des équipes : déplacez les joueurs depuis l'administration », with a link to the Player admin, and no builder.

**Roster changes.** On load the page reconciles the saved draft with the payload: players no longer active are removed from the draft's teams, links and locks; players not in the draft are listed in an « À placer » tray (draggable into any team, and movable by the same menu); a banner says « 2 nouveaux inscrits, 1 désistement ». The reconciled draft is what the next save sends, so the server's strict validation (`unknown_player`) never trips on it.

The draft is saved automatically after a change, debounced, with `based_on`; a 409 `stale_draft` shows « Quelqu'un d'autre a modifié le brouillon » and offers to load theirs. Strings are `builder.*` in both dictionaries, worded « vous ».

## The generator

`$lib/builder.js`, pure (no Svelte, no network):

- `matchNames(text, players, selfId)` → candidates per name, with a confidence.
- `teamSizes(n, perTeam)` → the sizes (`n` over `ceil(n / perTeam)` teams, as even as possible).
- **Missing answers.** A skill without a rating counts as the player's overall `rating`; a missing frequency counts as `hour`; no sports rows count as no experience. Any assumption puts a « Profil incomplet » badge on the player's card, and the player is still balanced like everyone else.
- `score(assignment, players, links, weights)` → `{total, parts, unmet}`, the one function the generator and the live display share. Its parts, each a standard deviation across the teams' means or counts so they compare across team sizes: overall rating; each skill, averaged over the skills; experience (the count of players with frequency `two_hours` or more, or a sports row at `league` or above); then penalties: an unmet one-sided « avec » `P_WITH`, an unmet mutual « avec » `2 × P_WITH`, an « à éviter » pair on one team `P_AVOID` (> `2 × P_WITH`), all constants named at the top of the module.
- `generate(players, links, {perTeam, seed, locked, current})` → an assignment: locked players stay where they are; the rest start from a balanced greedy placement (strongest first, snaking over the teams) and then improve by swapping two unlocked players while the score decreases, over a few seeded restarts, keeping the best. The seed comes from a small seeded PRNG so the same input and seed give the same teams; « Relancer » picks a new seed.

Fewer than two teams, or fewer players than teams, is a refusal with a message, never a bad assignment.

## Tests

Server: draft validation (each code), the `TeamResult` backfill (a discipline created before the teams gets a result per new team, none duplicated) and `unscheduled`, the `registration_open` flag, the staff-only walk (visitor 401, player 403), `BUILDER_QUERIES` on a roster of a few players, the payload carrying no username or email, `stale_draft`, apply (every refusal, the created teams and the `Player.team` set through `save()`, the draft deleted, one transaction rolled back on failure), not-latest 409, the export exclusion, and the migration.

Front: the roster reconciliation (departed player, new registrant, link and lock cleanup), the fallbacks and the « Profil incomplet » badge, the number input disabled after a proposal and « Tout réinitialiser » keeping the links, the registration-open confirmation, the existing-teams message, `matchNames` (whole name, unique first name, ambiguous first name, one-edit typo, self, noise like « peu importe »), `teamSizes`, `score` (each part and each penalty), `generate` (sizes always valid, locked players stay, the same seed gives the same teams, an avoid pair is separated and a mutual « avec » kept together when balance allows, unmet requests reported), the page's three panels with the apply and stale-draft flows, drag by menu, and a French render.

The dev stack is walked in the browser on the throwaway 2029 edition (about ten registered players) before merging.

## Rollout

Two PRs: (1) the server (`TeamDraft`, `builder.py`, the endpoints, the Edition admin link, its docs); (2) the front (`$lib/builder/`, the page, the ranking-page button, the dictionaries, docs), opened from `dev` once the first is merged. Deploy: `migrate`, server before front (an older server answers the new page's loads with 404). The browser walk happens once both are on `dev`.
