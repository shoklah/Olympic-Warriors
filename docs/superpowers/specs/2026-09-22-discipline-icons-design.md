# Discipline icons — design

Date: 2026-09-22

## Goal

Give every discipline model its own icon so the front never shows the generic
fallback star for a discipline that exists today. Follow-up to the
edition-aware frontend spec (`2026-09-22-edition-aware-frontend-design.md`).

## Current behaviour

`front/src/lib/icons.js` resolves a discipline name to
`front/src/lib/img/icons/<slug>.svg` (name lowercased, spaces and apostrophes
removed) and falls back to `default.svg`. Icons exist for Blindtest, Crossfit,
Darts, Dodgeball, Hide and Seek, Orienteering and Rugby. Seven models have
none: Relay, Basketball, Petanque, Fair, Obstacle Course, Geography Quizz,
General Culture Quizz.

## Decisions

- **Source:** hand-drawn SVG paths in the style of the existing set, no
  external icon library, no licence.
- **Scope:** all seven missing disciplines.
- **Pictograms:** Relay is a running figure (not a baton); Basketball a ball on
  a hoop; Petanque two boules and a jack; Fair (a funfair) a Ferris wheel;
  Obstacle Course a figure vaulting a wall; Geography Quizz a globe with a
  question mark; General Culture Quizz a lightbulb with a question mark.
- **Style:** `viewBox="0 0 2000 2000"`, `fill="none"` on the root, white
  filled shapes (strokes in white only where a thin line is the shape),
  silhouettes bold enough to read at 70 px in the ranking rail and at 30 %
  opacity on the hub.
- **Approval:** a contact sheet of all fourteen icons on black and on the pale
  theme colour is shown in the browser before the files are committed.

## Files

- Create `front/src/lib/img/icons/{relay,basketball,petanque,fair,obstaclecourse,geographyquizz,generalculturequizz}.svg`.
- `front/src/lib/components/EditionHub.test.js`: the Relay assertion expects
  `relay.svg`.
- `front/src/lib/icons.test.js`: a test listing every discipline name set in
  `server/olympic_warriors/models/*.py` (`self.name = '...'`) asserts none of
  them resolves to `default.svg`. The list is hand-maintained; adding a
  discipline model without an icon fails the front suite.
- `CLAUDE.md`: drop the list of available icons in the Frontend section and in
  step 5 of "Adding a discipline", state that every model has one and the test
  enforces it.

## Out of scope

Redrawing the existing seven icons; animated or coloured icons.
