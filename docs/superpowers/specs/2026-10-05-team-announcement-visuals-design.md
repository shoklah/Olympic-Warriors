# Team announcement visuals

Status: design, approved section by section in conversation on 2026-10-05. Follows the team builder (`2026-10-05-team-builder-design.md`), whose spec listed « a shareable visual » as a likely later feature.

## Goal

Once the teams exist, let the organisers generate images to announce them: one poster with every team, and one square card per team, as PNG files ready to post in a group chat or on social media.

## Decisions

- **Both a poster and per-team cards.** The poster announces everything at once; the cards let a team be tagged or shared on its own.
- **Organisers only.** The images are generated and downloaded by organisers, from the builder's done screen and from the latest edition's ranking page. Nothing is public and nothing is stored: a player sees only what the organisers share.
- **Drawn in the browser, on a 2D canvas.** No server code, an instant preview while options change, the layout a pure function. The downloads happen on the organiser's machine.
- **Content:** the event identity (logo, « Olympic Warriors », year, host, dates), the team names and the player names, and **player photos**, with a switch (on by default: Hugo wants to try it and see how it goes). Initials on a round stand in for a missing photo. **No team colours or emblems.**
- **Sizes:** the poster is 1600px wide and its height follows its content, so 6 and 16 teams both stay readable; each team card is a 1080×1080 square. No per-network formats.
- **A dedicated page**, `/<year>/announce`, with live previews and the downloads, so it works at any time after Apply, not only right after it.
- **« Tout télécharger » is one ZIP**, built in the browser by a small store-only ZIP writer (no new dependency).
- Out of scope: team colours or emblems, public download, posting to social networks, storing generated images, story/landscape formats, a server-side renderer.

## Data

None added. The page reads the edition summary the `[year=year]` layout already loads (`/edition/year/<year>/summary/`): the active teams (their names, renamed in the admin or the placeholder « Équipe N »), each roster with `first_name`, `last_name` and `photo` (the small URL, 128px WebP under `/media/avatars/`, or `null`), and the edition's year, host and dates. Photos are same-origin, so drawing them does not taint the canvas, and an anonymized player already comes through as « Joueur anonyme » with no photo. Players are ordered by last name then first name, as on the team pages; teams by id (their creation order), not by ranking.

No API change, no migration, no server code. The site's fonts (Bebas Neue, Inter), the logo (`$lib/img/logo.svg`, `title.svg`) and the eclipse are already front assets.

## Front

### The page

Route `/<year>/announce` (`routes/[year=year]/announce`), added to `NO_TAB_BAR`. Its `+page.server.js` mirrors the builder's guards (a visitor goes to `/login?next=…`, a logged-in non-organiser gets 403, a year that is not the latest 404, `private, no-store`) and reads `summary` from `parent()`; it fetches nothing itself. An edition with no team shows a message (« Il n'y a pas encore d'équipes ») and a link to the builder. The page has:

- the options: a **« Afficher les photos »** switch (on by default, remembered in `localStorage` like the builder's notes switch, never on the server);
- a **poster preview** and one **card preview per team**, each a canvas scaled to fit the column with CSS, redrawn whenever the switch or the data changes;
- downloads: **« Télécharger l'affiche »** (PNG), a download button on each card, and **« Tout télécharger (ZIP) »** (every card plus the poster).

It is reached from the builder's « Équipes créées » screen (a link) and from the latest edition's ranking page: an organiser-only link to `/<year>/announce` while the edition has teams and is the latest (the counterpart of « Constituer les équipes », which shows while it has none). Strings are `announce.*` in both dictionaries, worded « vous ».

### `$lib/announce/`

All pure except `draw.js` and `export.js`, which touch the canvas and the browser.

- `layout.js`: `posterLayout(teams, { photos, width })` and `cardLayout(team, { photos, size })` return plain objects describing what to draw and where (rectangles, text boxes with a font size, avatar circles), with no canvas involved.
  - **Poster:** a header band (logo, title, « Édition {year} · {host} · {dates} »), then the team blocks in a grid whose column count follows the team count (2 columns up to 6 teams, 3 up to 12, 4 beyond), each block a title and one row per player (an avatar circle when photos are on, then the name). Row height depends on the photos switch; names longer than the column shrink their font down to a floor, then truncate with an ellipsis. The canvas height is the header plus the tallest block per row of blocks, plus margins and a footer.
  - **Card:** the logo small at the top, the team name very large (shrinking to fit), then the players in a grid sized from the roster: one column of large portraits for 1 to 3 players, two columns for 4 to 8, three beyond; portrait diameter and name size follow the cell size, so 3 players get big faces and 9 get smaller ones. With photos off the names alone fill the card at a larger size.
  - Text measurement is injected (`measure(text, font)`), so the layout is testable with a fake measurer.
- `draw.js`: `drawLayout(ctx, layout, images)` paints a layout: the dark `--bg`-like background, gold accents (the `--gold`/`--accent` values read once from the page's computed style, so the images follow the design tokens), text in Bebas Neue and Inter, the logo, and each player's photo clipped to a circle, or the initials from `$lib/avatar.js` (`initials(first, last)`) on a round when there is no photo or it failed to load. It never throws on a missing image.
- `images.js`: `loadImages(urls)` loads the logo and the photos (an `Image` per URL, same-origin, `decode()` where available), resolving to a map where a failed load is simply absent; and `fontsReady()` awaits `document.fonts.load` for the two faces so the first draw is not in a fallback font.
- `zip.js`: `makeZip([{ name, data }])` → a `Uint8Array` of a valid store-only ZIP (local file headers, central directory, end record, CRC-32, DOS date and time); file names are UTF-8 (general purpose bit 11).
- `export.js`: `toPng(canvas)` → `Blob` (`canvas.toBlob`), `fileName(prefix, name)` (slugified, accents folded: `equipe-3.png`, `affiche-2029.png`), `download(blob, name)` (an object URL on a temporary link, revoked after the click), and `downloadAll(…)` building the ZIP.

### Behaviour notes

- Drawing is done once the fonts and images are ready; until then the previews show a quiet placeholder. A photo that fails to load falls back to initials rather than leaving a hole.
- The canvases are drawn at the real size (1600px wide, 1080×1080), and shown scaled by CSS, so the downloaded PNG is full resolution whatever the preview size. For a 16-team poster the height is bounded by the layout, not the screen.
- A photo is the 128px version: drawn at up to about 200px on a card it softens slightly. That is accepted for now (« see how it goes »); a larger variant would need an API change and is the obvious next step if the cards look soft.
- The language of the text is the viewer's (`useLocale()`): dates through the existing `formatDateRange`.

## Tests

- `layout.test.js`: column count by team count, block order and player order, name fitting and truncation with a fake measurer, the card's grid and portrait size for 1, 3, 4, 8 and 9 players, the poster height growing with the rows, the photos switch changing row height and card layout.
- `zip.test.js`: a known CRC-32, and a ZIP read back by a minimal parser in the test (entry names, sizes, the stored bytes, central directory offsets, UTF-8 names).
- `draw.test.js`: a fake 2D context recording its calls: every team name and player name is drawn, the photos switch changes the `drawImage` calls, a missing image draws initials, and nothing throws when an image is absent.
- `export.test.js`: `fileName` slugs, and `download` with `URL.createObjectURL` and the link click stubbed.
- The page: its server guards, the previews rendered, the switch redrawing and being remembered, the empty state with its link to the builder, the download buttons calling the exporter (stubbed `toBlob`), the ranking page and the done screen links, and a French render.
- Walked in the browser on the demo edition once it has teams (apply the builder's teams first): the poster and a few cards on screen and as downloaded files, with photos on and off.

## Rollout

One front-only PR: `$lib/announce/`, the page, the two entry-point links, the dictionaries and `CLAUDE.md`. No migration and no deploy ordering.
