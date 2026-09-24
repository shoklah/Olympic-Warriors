# Phone header menu — design

Date: 2026-09-24

## Goal

With the theme switch, five controls shared the phone top bar (logo, year, the
login link or ORGA pill, `FR | EN`, the theme). They only fitted at 320 px by
squeezing padding and letter-spacing. Fold the settings behind a menu button
instead.

## Decisions

- **Settings only.** The menu holds the account slot (login link or ORGA
  logout), the language and the theme. Navigation stays in the bottom tab bar,
  as the Scoreboard redesign decided when it dropped the old hamburger; the hub
  and the login page keep reaching the sections through their own links.
- **Below 600 px**, every phone. From 600 px up the bar is exactly as before.
- **The year stays in the bar:** it says which edition the page shows.
- **One set of controls for both layouts.** No duplicated forms: the wrapper
  `div#header-settings.settings` is `display: contents` from 600 px up, so its
  children stay flex items of the bar, and a panel below.

## Behaviour

- `button.menu-toggle` (`type="button"`, name « Menu » in both languages,
  `aria-expanded`, `aria-controls="header-settings"`), a 44 px round button at
  the right end of the bar, burger icon closed, cross open, accent while open.
  It follows the year in the DOM, so Tab goes from it into the panel.
- The panel opens under the bar, full width, on `--bg-raised` with a `--line`
  bottom border, one 60 px row per control separated by `--line`:
  - visitor: the whole row is the `Connexion` link, in accent;
  - organiser: the whole row is the logout button, the ORGA pill on the left
    and « Se déconnecter » on the right (the accessible name `Orga · Se
    déconnecter` already covered both);
  - `LANGUE` label, `FR | EN` pill on the right, the current segment on `--bg`
    since the panel is already `--bg-raised`;
  - `THÈME` label, then a pill with the icon and the theme it leads to
    (« Sombre » / « Clair »), hidden on the hub like the inline switch.
  The row labels are `aria-hidden`: each form already carries that name.
- It closes on a navigation (`afterNavigate`: the login link is client-side and
  the header persists), on Escape (focus back on the button), and on a click
  outside the header. Outside is read from `event.composedPath()`, not
  `header.contains(event.target)`: the button's own click re-renders its icon
  before the window listener runs, detaching the clicked `<path>`, which would
  otherwise close the menu the moment it opens. jsdom does not reproduce that
  timing, so the Header tests cannot catch it; it was found in Chromium.
- The language, theme and logout forms still submit as plain POSTs and reload
  the page, which closes the menu.
- The menu needs JavaScript, like the year select; before hydration the button
  does nothing.

## Tests

`Header.test.js`: the button starts collapsed, controls the panel holding the
login link and both forms but not the year, toggles; Escape closes it and
focuses the button; a click inside the header keeps it open, one outside closes
it; in French the rows read `Langue FR EN`, and the theme buttons show `Clair`
and `Sombre` inside their full names; the ORGA button reads `Orga Se
déconnecter`.
