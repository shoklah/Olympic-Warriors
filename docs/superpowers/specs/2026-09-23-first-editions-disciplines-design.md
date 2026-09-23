# First editions disciplines

## Goal

Earlier editions ran disciplines the app does not model yet. Add ten of them so those
editions can be entered (by hand or through `import_edition`) with the right name, result
type, icon and French name.

## Disciplines

| Model | `name` (database) | Result type | French name | Icon stem |
|---|---|---|---|---|
| `Volleyball` | Volleyball | points | Volley-ball | `volleyball` |
| `JumpingRope` | Jumping Rope | time | Corde à sauter | `jumpingrope` |
| `Dance` | Dance | points | Danse | `dance` |
| `Frisbee` | Frisbee | points | *(same)* | `frisbee` |
| `Geoguessr` | Geoguessr | points | *(same)* | `geoguessr` |
| `Football` | Football | points | *(same)* | `football` |
| `Handball` | Handball | points | *(same)* | `handball` |
| `BurgerQuizz` | Burger Quizz | points | Burger Quiz | `burgerquizz` |
| `BlindfoldedObstacleCourse` | Blindfolded Obstacle Course | time | Parcours d'obstacles à l'aveugle | `blindfoldedobstaclecourse` |
| `DiscThrow` | Disc Throw | points | Lancer de disque | `discthrow` |

Volleyball, Football and Handball are team sports: organisers pick a pairing system in the
admin, and the game points are computed, as for Basketball. None of them gets a `GameEvent`
subclass. The other disciplines have no games, and organisers enter their points or times by hand.

Frisbee is played golf style over several rounds, so the fewest throws wins. There is no
"lowest wins" support: organisers enter final points where higher is better. We can revisit
this if more disciplines like it show up.

## Changes

Server, following the "Adding a discipline" steps in `CLAUDE.md`:
- one `models/<Model>.py` per discipline, shaped like `models/Relay.py` (`save()` sets
  `name` and `result_type` when `pk is None`)
- export each one from `models/__init__.py`
- `site.register(<Model>, DisciplineAdmin)` in `admin.py`
- one migration `0030` creating the ten child tables

Front:
- ten SVG icons in `front/src/lib/img/icons/` in the house style (2000×2000 viewBox,
  white strokes, no fill background)
- French names in `FRENCH_NAMES`, same-name ones in `SAME_IN_FRENCH`
  (`front/src/lib/i18n/disciplines.js`)
- the ten names in `DISCIPLINE_NAMES` (`front/src/lib/icons.test.js`), so a missing icon or
  a missing French name fails the tests

## Testing

- Front: `icons.test.js` goes red when the names are added and green once the icons and
  French names exist. `npm test` and `npm run build` must pass.
- Server: one Django test per discipline checking that creation sets the expected `name`
  and `result_type`. Also check that `makemigrations --check` reports nothing after `0030`.

## Out of scope

- Importing the actual data of the first editions
- Lowest-wins ranking
