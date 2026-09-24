# Light mode — design

Date: 2026-09-24

## Goal

Offer a light theme beside the Scoreboard dark one. The site is read on phones
outdoors during the event, where a dark page is hard to read in the sun, so a
visitor must be able to pick light even when their phone is set to dark.

## Decisions

- **Default follows the device** (`prefers-color-scheme`); a **header switch**
  overrides it, stored in a `theme` cookie for a year. Same mechanism as the
  language: a plain form POST to `/theme`, a 303 back to the page, the server
  writing `<html data-theme>` from the cookie, so the first paint is already in
  the right theme and no client code decides it.
- **The hub stays dark**, header included: the eclipse is a photograph on black.
  It shows no switch, since the switch would change nothing visible there.
- **Dark stays the default and the brand.** A browser without `:has()` (before
  Chrome 105, Safari 15.4, Firefox 121) always gets dark.
- **No theme class, no store.** Components keep reading tokens; the switch is the
  only markup that knows about themes.

## Mechanism

- `$lib/theme.js`: `THEMES = ['light', 'dark']`, `THEME_COOKIE = 'theme'`,
  `themeFrom(value)` returning the value when it is a theme, else `system`.
- `hooks.server.js` replaces `%theme%` in `app.html`
  (`<html lang="%lang%" data-theme="%theme%">`) with `themeFrom(cookie)`.
  `Vary: Cookie` is already set.
- `/theme` action: `light` or `dark` is stored (path `/`, one year, lax, not
  httpOnly, like `lang`); `system` or anything else deletes the cookie, handing
  the theme back to the device. Then `redirect(303, localPath(...))`.
  `localPath` moves to `$lib/local-path.js`, shared with `/lang` and `/logout`.
- `styles.css`:
  - `:root` keeps the dark tokens and adds `color-scheme: dark`,
    `--icon-filter: none`, `--icon-filter-on-accent: invert(1)`,
    `--switch-to-light: flex`, `--switch-to-dark: none`.
  - `:root[data-theme='light']:not(:has([data-always-dark]))` and, inside
    `@media (prefers-color-scheme: light)`,
    `:root[data-theme='system']:not(:has([data-always-dark]))` declare the same
    light block: `color-scheme: light`, every colour token, the icon filters
    swapped, the switch displays swapped. CSS cannot share one block between a
    selector and a media query without `light-dark()`, which would break every
    token in browsers from before 2024, so the block is duplicated and a test
    keeps the copies equal.
- `EditionHub` puts `data-always-dark` on its hero. Because the selector is
  evaluated live, a client-side navigation into or out of the hub flips the
  theme with no script. `Header` hides its whole theme form there with
  `:global(:root:has([data-always-dark])) .theme`, so the phone menu drops the
  row, label included.
- The discipline icons and badge glyphs are white SVGs in `<img>`: every one on
  a page surface (rail tile, disciplines card, discipline title, team result
  tile, profile disciplines, badge medallion) sets
  `filter: var(--icon-filter)`; the current rail tile, on the accent fill, sets
  `filter: var(--icon-filter-on-accent)`. The hub's icons sit on the dark hub.
- The year `<select>` options use `CanvasText` on `Canvas`, the popup's system
  colours, which follow `color-scheme` (they were hard-coded black for the
  default light popup).
- The logo, the title, the favicon and `error.html` are unchanged: on the light
  page the logo reads as a black badge.

## Light palette

Warm paper under white cards, near-black accent: the brand's cream and black,
swapped.

| Token | Dark | Light |
| --- | --- | --- |
| `--bg` | `#000000` | `#f5f2e8` |
| `--bg-raised` | `#141414` | `#ffffff` |
| `--bg-sunken` | `#121212` | `#fbfaf5` |
| `--scrim` | `rgba(0, 0, 0, 0.6)` | `rgba(20, 18, 8, 0.45)` |
| `--line` | `#262626` | `#e3dece` |
| `--line-strong` | `#2a2a2a` | `#d2ccb9` |
| `--ink` | `#ffffff` | `#0b0a05` |
| `--text` | `#f2ecc8` | `#2a2718` |
| `--muted` | `#8a8674` | `#686350` |
| `--faint` | `#6f6b5c` | `#7d7865` |
| `--ghost` | `#6a6658` | `#a19b86` |
| `--accent` | `#F9F3C1` | `#1c1a0f` |
| `--gold` / `--silver` / `--bronze` | `#e6b800` / `#c9c9c9` / `#cd7f32` | `#8a6500` / `#6b6b6b` / `#9a5418` |
| `--win` / `--loss` / `--todo` | `#7bd88f` / `#d87b7b` / `#4f8cff` | `#1f7a38` / `#b3383a` / `#1d5fd6` |

Contrast floors, checked for both themes on `--bg`, `--bg-raised` and
`--bg-sunken` by `styles.test.js`: 4.5:1 for `--ink`, `--text`, `--accent`,
`--muted`, the medals and the outcomes; 3:1 for `--faint` (large text only);
4.5:1 for `--bg` on `--accent` (filled buttons). `--ghost` is decorative and
unchecked.

## Header switch

A `<form method="POST" action="/theme" aria-label="Thème">` after `FR | EN`
with a `redirectTo` field and round 44 px buttons: sun (« Passer au thème
clair » / "Switch to light theme") and moon (« Passer au thème sombre » /
"Switch to dark theme"), each twice (`SWITCHES` in `Header.svelte`): once
storing the choice (`value="light"` / `"dark"`), once posting `system`.

Only the browser knows which theme is on screen and which one the device
prefers, so all four are rendered and CSS shows exactly one, the hidden ones
leaving the accessibility tree:

- the direction takes its `display` from `--switch-to-light` /
  `--switch-to-dark`, so it leads away from the theme on screen;
- the device's own theme is dark unless it prefers light, and the switch
  leading there is the one posting `system` (a media query per preference
  hides the other copy). Toggling twice therefore returns to the device, and
  the cookie only ever records a departure from it, such as light outdoors on
  a dark phone.

A browser without `:has()` never leaves dark, so the form is hidden there
(`@supports not selector(:has(a))`). Quiet like the login pill:
`--line-strong` border, `--muted` icon, accent on hover and focus, the same
`round` class as the phone menu button.

Below 600 px the switch sits in the header's menu panel with the account slot
and the language (see the phone header menu spec), where it reads as a pill
naming the theme it leads to (« Sombre » / « Clair ») beside its icon; the
accessible name keeps the full action, which contains that word.

## Tests

- `styles.test.js`: the two light blocks are equal; light redefines exactly the
  dark tokens minus the layout ones; the contrast floors above; every `.svelte`
  file rendering a discipline icon or a badge glyph (the hub aside) has at least
  one `filter: var(--icon-filter…)` rule per such image.
- `hooks.server.test.js`: `data-theme` from the cookie, `system` by default, and
  the placeholder present in `app.html`.
- `theme/page.server.test.js`: stores light and dark, deletes anything else,
  refuses a non-local redirect, a GET goes to the hub.
- `theme.test.js`: `themeFrom`.
- `Header.test.js`: the form, its action, and each direction offered storing a
  choice and posting `system`, in English and French.
- `EditionHub.test.js`: the hub carries `data-always-dark`.
