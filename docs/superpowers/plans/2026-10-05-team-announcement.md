# Team Announcement Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An organiser-only page, `/<year>/announce`, that draws a poster of every team and one square card per team on a canvas, with a photos switch (off by default), a language selector (French by default), PNG downloads and a one-click ZIP.

**Architecture:** Front only. A pure layout module turns the edition summary's teams into plain drawing instructions (rectangles, texts, avatars, logo); a small canvas painter executes them; export helpers produce PNGs and a store-only ZIP. The page reads `summary` from the year layout, so there is no server, API or migration change.

**Tech Stack:** SvelteKit 2 / Svelte 4 (plain JS, tabs), Vitest + @testing-library/svelte (jsdom has no canvas: tests use a recording fake context).

Spec: `docs/superpowers/specs/2026-10-05-team-announcement-visuals-design.md`.

**Rules for every implementer** (from CLAUDE.md and past slices):
- Front only. NEVER write to the dev database; no servers; the controller does the browser walk.
- Tests: `cd front && npx vitest run <file>`. Run each new test red before the code that makes it green; one commit per task, each ending with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Run vitest from `front/`, never from `front/src` (it creates a stray `.svelte-kit` folder; `git status` must be clean of it before each commit).
- Colours only through tokens in `.svelte` files (`styles.test.js`); every visible string through `t`; fr.js/en.js in parity. The drawing code has its own fixed dark palette, pinned by a test (Task 3).
- Svelte 4: never reload derived data from props in a bare `$:` that bound inputs can retrigger; here the page only reads `data`.

## Deviation from the spec (decided while planning)

The spec says the painter reads the colours from the page's computed style. That would follow the viewer's theme: an organiser in light mode would download a light poster. The announcement is always the dark brand image, so the painter uses a fixed palette (`palette.js`) whose values are pinned by a test against the dark tokens in `routes/styles.css`; a palette change in the CSS fails that test.

## Decisions from the grilling (all in the spec)

Photos are **off by default** with a one-line notice when switched on (players agreed to show their photo on the site only); the image text is **French by default with a selector** (« Langue des images »), independent of the site's language; the text is **fixed** (no custom line); **no warning** for provisional team names.

## File structure

- `front/src/lib/announce/palette.js` — the dark palette. `layout.js` — pure layouts. `draw.js` — canvas painter. `images.js` — image and font loading. `zip.js` — store-only ZIP. `export.js` — PNG, file names, downloads. Tests beside each.
- `front/src/routes/[year=year]/announce/+page.server.js`, `+page.svelte`, `page.server.test.js`, `page.test.js`.
- Modify: `routes/+layout.svelte` (`NO_TAB_BAR`), `routes/[year=year]/ranking/+page.svelte` (+ test), `components/builder/BuilderApply.svelte` (+ test) and the builder page (the `year` prop), `i18n/fr.js`, `en.js`, `CLAUDE.md`.

---

### Task 1: Layout (pure)

**Files:** Create `front/src/lib/announce/layout.js`; Test `front/src/lib/announce/layout.test.js`.

A layout is `{ width, height, items }`. Items, all in canvas pixels:
- `{ type: 'rect', x, y, w, h, fill, stroke?, radius? }` (`fill`/`stroke` are palette keys),
- `{ type: 'text', x, y, text, family: 'display'|'body', weight, size, color, align?: 'left'|'center'|'right', baseline?: 'alphabetic'|'middle' }`,
- `{ type: 'avatar', x, y, size, player }` (`player`: `{ first_name, last_name, photo }`; `x`,`y` the top-left),
- `{ type: 'logo' | 'title', x, y, w, h }` (the two brand images).

`measure(text, font)` is injected (the page gives a canvas `measureText`); `font` is the CSS font string from `fontString`.

- [ ] **Step 1: Write the failing tests**

```js
import { describe, expect, it } from 'vitest';
import { POSTER, cardLayout, columnsFor, fitText, fontString, orderedPlayers, posterLayout } from './layout.js';

// A measurer that makes a character as wide as half the font size.
const measure = (text, font) => text.length * (Number(/(\d+)px/.exec(font)[1]) / 2);
const labels = { title: 'Les équipes 2029', subtitle: 'Paris · 14 – 15 septembre 2029', event: 'Olympic Warriors 2029' };
const player = (id, first, last, photo = null) => ({ id, first_name: first, last_name: last, photo });
const team = (id, name, players) => ({ id, name, players });
const texts = (layout) => layout.items.filter((i) => i.type === 'text');
const avatars = (layout) => layout.items.filter((i) => i.type === 'avatar');
const manyTeams = (n, perTeam = 3) =>
	Array.from({ length: n }, (_, i) =>
		team(i + 1, `Équipe ${i + 1}`, Array.from({ length: perTeam }, (_, j) => player(i * 10 + j, `P${j}`, `Nom${i}`)))
	);

describe('fontString', () => {
	it('builds the CSS font of a text item', () => {
		expect(fontString({ family: 'display', weight: 400, size: 64 })).toBe('400 64px "Bebas Neue", sans-serif');
		expect(fontString({ family: 'body', weight: 600, size: 30 })).toBe('600 30px Inter, sans-serif');
	});
});

describe('orderedPlayers', () => {
	it('sorts by last name then first name, ignoring accents and case', () => {
		const out = orderedPlayers([player(1, 'Zoé', 'Martin'), player(2, 'Élodie', 'durand'), player(3, 'Ana', 'Martin')]);

		expect(out.map((p) => p.id)).toEqual([2, 3, 1]);
	});
});

describe('columnsFor', () => {
	it.each([[1, 2], [6, 2], [7, 3], [12, 3], [13, 4], [16, 4]])('%i teams use %i columns', (n, cols) => {
		expect(columnsFor(n)).toBe(cols);
	});
});

describe('fitText', () => {
	const base = { family: 'body', weight: 600, size: 30, min: 20 };

	it('keeps a text that fits', () => {
		expect(fitText(measure, 'Léa Martin', { ...base, maxWidth: 500 })).toEqual({ text: 'Léa Martin', size: 30 });
	});

	it('shrinks down to the floor first', () => {
		const out = fitText(measure, 'Léa Martin-Dupont', { ...base, maxWidth: 200 });

		expect(out.size).toBeLessThan(30);
		expect(out.size).toBeGreaterThanOrEqual(20);
		expect(measure(out.text, fontString({ ...base, size: out.size }))).toBeLessThanOrEqual(200);
	});

	it('then truncates with an ellipsis', () => {
		const out = fitText(measure, 'Maximilien Alexandre de la Tour', { ...base, maxWidth: 120 });

		expect(out.size).toBe(20);
		expect(out.text.endsWith('…')).toBe(true);
		expect(measure(out.text, fontString({ ...base, size: 20 }))).toBeLessThanOrEqual(120);
	});
});

describe('posterLayout', () => {
	const poster = (teams, photos = true) => posterLayout(teams, { photos, measure, labels });

	it('is 1600 wide with the header texts and a background', () => {
		const layout = poster(manyTeams(4));

		expect(layout.width).toBe(POSTER.width);
		expect(layout.items[0]).toMatchObject({ type: 'rect', x: 0, y: 0, w: POSTER.width, fill: 'bg' });
		expect(layout.items[0].h).toBe(layout.height);
		expect(texts(layout).map((t) => t.text)).toEqual(expect.arrayContaining([labels.title, labels.subtitle]));
		expect(layout.items.some((i) => i.type === 'logo')).toBe(true);
	});

	it('lays teams out in the columns the count calls for, in id order', () => {
		const layout = poster([...manyTeams(8)].reverse());
		const titles = texts(layout).filter((t) => t.text.startsWith('Équipe'));

		expect(titles.map((t) => t.text)).toEqual(Array.from({ length: 8 }, (_, i) => `Équipe ${i + 1}`));
		expect(new Set(titles.map((t) => t.x)).size).toBe(3); // 8 teams: 3 columns
		expect(new Set(titles.map((t) => t.y)).size).toBe(3); // 3 rows
	});

	it('lists each team players by last name, one per row', () => {
		const layout = poster([team(1, 'Aigles', [player(1, 'Zoé', 'Zed'), player(2, 'Ana', 'Abel')])]);
		const names = texts(layout).filter((t) => /Abel|Zed/.test(t.text));

		expect(names.map((t) => t.text)).toEqual(['Ana Abel', 'Zoé Zed']);
		expect(names[1].y).toBeGreaterThan(names[0].y);
	});

	it('draws an avatar per player with photos on, none with photos off, and shortens the rows', () => {
		const on = poster(manyTeams(2));
		const off = poster(manyTeams(2), false);

		expect(avatars(on)).toHaveLength(6);
		expect(avatars(off)).toHaveLength(0);
		expect(off.height).toBeLessThan(on.height);
	});

	it('grows taller with more rows of teams and with bigger rosters', () => {
		expect(poster(manyTeams(7)).height).toBeGreaterThan(poster(manyTeams(6)).height);
		expect(poster(manyTeams(2, 6)).height).toBeGreaterThan(poster(manyTeams(2, 3)).height);
	});

	it('makes the blocks of a row the same height, the tallest roster setting it', () => {
		const layout = poster([team(1, 'A', [player(1, 'a', 'a')]), team(2, 'B', [player(2, 'b', 'b'), player(3, 'c', 'c'), player(4, 'd', 'd')])]);
		const blocks = layout.items.filter((i) => i.type === 'rect' && i.fill === 'raised');

		expect(blocks).toHaveLength(2);
		expect(blocks[0].h).toBe(blocks[1].h);
	});

	it('shortens a long name to fit its column', () => {
		const layout = poster([team(1, 'Aigles', [player(1, 'Maximilien-Alexandre', 'de la Tour d’Auvergne-Lauraguais')])]);
		const name = texts(layout).find((t) => t.text.includes('Maximilien') || t.text.endsWith('…'));

		expect(name).toBeDefined();
		const colW = (POSTER.width - 2 * POSTER.margin - POSTER.gap) / 2;
		expect(measure(name.text, fontString(name))).toBeLessThanOrEqual(colW - 2 * POSTER.pad - POSTER.avatar - 20);
	});

	it('handles an empty edition and a team without players', () => {
		expect(poster([]).height).toBeGreaterThan(0);
		expect(poster([team(1, 'Vide', [])]).items.some((i) => i.type === 'text' && i.text === 'Vide')).toBe(true);
	});
});

describe('cardLayout', () => {
	const card = (n, photos = true) =>
		cardLayout(team(1, 'Aigles', Array.from({ length: n }, (_, i) => player(i + 1, `P${i}`, `N${String(i).padStart(2, '0')}`))), {
			photos,
			measure,
			labels
		});
	const nameXs = (layout) => new Set(texts(layout).filter((t) => /^P\d/.test(t.text)).map((t) => t.x));

	it('is a 1080 square with the team name, the event line and the logo', () => {
		const layout = card(3);

		expect(layout).toMatchObject({ width: 1080, height: 1080 });
		expect(texts(layout).map((t) => t.text)).toEqual(expect.arrayContaining(['Aigles', labels.event]));
		expect(layout.items.some((i) => i.type === 'logo')).toBe(true);
	});

	it('uses one column for up to 3 players, two up to 8 and three beyond', () => {
		expect(nameXs(card(3)).size).toBe(1);
		expect(nameXs(card(4)).size).toBe(2);
		expect(nameXs(card(8)).size).toBe(2);
		expect(nameXs(card(9)).size).toBe(3);
	});

	it('gives few players big portraits and many players smaller ones', () => {
		const size = (layout) => avatars(layout)[0].size;

		expect(size(card(3))).toBeGreaterThan(size(card(8)));
		expect(size(card(8))).toBeGreaterThan(size(card(9)) - 1);
	});

	it('draws an avatar per player with photos on and none with photos off, names larger', () => {
		const on = card(4);
		const off = card(4, false);
		const nameSize = (layout) => texts(layout).find((t) => /^P\d/.test(t.text)).size;

		expect(avatars(on)).toHaveLength(4);
		expect(avatars(off)).toHaveLength(0);
		expect(nameSize(off)).toBeGreaterThanOrEqual(nameSize(on));
	});

	it('keeps every player inside the square', () => {
		for (const n of [1, 3, 4, 8, 9, 12]) {
			for (const item of card(n).items.filter((i) => i.type === 'avatar')) {
				expect(item.x).toBeGreaterThanOrEqual(0);
				expect(item.y + item.size).toBeLessThanOrEqual(1080);
			}
		}
	});

	it('shrinks a long team name to fit and handles a team without players', () => {
		const long = cardLayout(team(1, 'Les Valeureux Guerriers de la Grande Plaine Orientale', []), { photos: true, measure, labels });
		const name = texts(long).find((t) => t.text.startsWith('Les Valeureux'));

		expect(measure(name.text, fontString(name))).toBeLessThanOrEqual(1080 - 2 * 72);
		expect(avatars(long)).toHaveLength(0);
	});
});
```

- [ ] **Step 2: Run red** — `npx vitest run src/lib/announce/layout.test.js` → import error.
- [ ] **Step 3: Implement** `layout.js`:

```js
import { fullName } from '$lib/players';

/** Sizes of the poster, in canvas pixels. */
export const POSTER = { width: 1600, margin: 80, gap: 40, header: 300, pad: 32, title: 92, rowPhotos: 80, rowPlain: 48, avatar: 60 };
const CARD = { size: 1080, margin: 72, areaTop: 470, gap: 32 };
const FAMILIES = { display: '"Bebas Neue", sans-serif', body: 'Inter, sans-serif' };

/** The CSS font of a text item (the painter and the measurer use the same string). */
export const fontString = ({ family, weight, size }) => `${weight} ${size}px ${FAMILIES[family]}`;

const collator = new Intl.Collator('fr', { sensitivity: 'base' });

/** A roster by last name then first name, as the team pages list it. */
export const orderedPlayers = (players) =>
	[...players].sort(
		(a, b) => collator.compare(a.last_name, b.last_name) || collator.compare(a.first_name, b.first_name) || a.id - b.id
	);

/** Poster columns for a team count: 2 up to 6 teams, 3 up to 12, 4 beyond. */
export const columnsFor = (count) => (count <= 6 ? 2 : count <= 12 ? 3 : 4);

/**
 * A text that fits `maxWidth`: its size shrinks by 2 down to `min`, then it is cut with an
 * ellipsis. `measure(text, font)` is the caller's (a canvas in the page, a fake in tests).
 */
export function fitText(measure, text, { family, weight, size, min, maxWidth }) {
	const width = (s, t) => measure(t, fontString({ family, weight, size: s }));
	let current = size;
	while (current > min && width(current, text) > maxWidth) current = Math.max(min, current - 2);
	if (width(current, text) <= maxWidth) return { text, size: current };
	let cut = text;
	while (cut.length > 1 && width(current, `${cut}…`) > maxWidth) cut = cut.slice(0, -1);
	return { text: `${cut.trimEnd()}…`, size: current };
}

const text = (x, y, value, fit, extra) => ({ type: 'text', x, y, text: value, ...fit, ...extra });
const avatar = (x, y, size, p) => ({ type: 'avatar', x, y, size, player: { first_name: p.first_name, last_name: p.last_name, photo: p.photo ?? null } });

/**
 * The poster: a header (logo, title, subtitle) and the teams in blocks, in id order, in the
 * columns the count calls for; a row of blocks is as tall as its tallest roster, and the canvas
 * as tall as its rows, so any number of teams fits without shrinking the text.
 */
export function posterLayout(teams, { photos, measure, labels, width = POSTER.width }) {
	const ordered = [...teams].sort((a, b) => a.id - b.id);
	const cols = columnsFor(ordered.length);
	const { margin, gap, pad, header } = POSTER;
	const colW = (width - 2 * margin - (cols - 1) * gap) / cols;
	const rowH = photos ? POSTER.rowPhotos : POSTER.rowPlain;
	const avatarSize = photos ? POSTER.avatar : 0;

	const chunks = [];
	for (let i = 0; i < ordered.length; i += cols) chunks.push(ordered.slice(i, i + cols));
	const heights = chunks.map((chunk) => 2 * pad + POSTER.title + Math.max(1, ...chunk.map((t) => t.players.length)) * rowH);
	const height = header + heights.reduce((a, b) => a + b, 0) + Math.max(0, chunks.length - 1) * gap + margin;

	const items = [{ type: 'rect', x: 0, y: 0, w: width, h: height, fill: 'bg' }];

	// Header: the logo, the title and the subtitle beside it, a gold rule under them.
	const logoW = 132;
	const headX = margin + logoW + 40;
	const headWidth = width - headX - margin;
	items.push({ type: 'logo', x: margin, y: 64, w: logoW, h: 125 });
	items.push(text(headX, 150, labels.title, fitText(measure, labels.title, { family: 'display', weight: 400, size: 104, min: 56, maxWidth: headWidth }), { family: 'display', weight: 400, color: 'ink' }));
	items.push(text(headX, 210, labels.subtitle, fitText(measure, labels.subtitle, { family: 'body', weight: 500, size: 36, min: 22, maxWidth: headWidth }), { family: 'body', weight: 500, color: 'muted' }));
	items.push({ type: 'rect', x: headX, y: 244, w: 160, h: 4, fill: 'gold' });

	let y = header;
	chunks.forEach((chunk, row) => {
		chunk.forEach((t, col) => {
			const x = margin + col * (colW + gap);
			items.push({ type: 'rect', x, y, w: colW, h: heights[row], fill: 'raised', stroke: 'line', radius: 20 });
			const name = fitText(measure, t.name, { family: 'display', weight: 400, size: 64, min: 36, maxWidth: colW - 2 * pad });
			items.push(text(x + pad, y + pad + 56, name.text, { size: name.size }, { family: 'display', weight: 400, color: 'accent' }));
			items.push({ type: 'rect', x: x + pad, y: y + pad + POSTER.title - 14, w: 72, h: 4, fill: 'gold' });
			const offset = photos ? avatarSize + 20 : 0;
			orderedPlayers(t.players).forEach((p, i) => {
				const top = y + pad + POSTER.title + i * rowH;
				if (photos) items.push(avatar(x + pad, top + (rowH - avatarSize) / 2, avatarSize, p));
				const label = fitText(measure, fullName(p), { family: 'body', weight: 600, size: 30, min: 20, maxWidth: colW - 2 * pad - offset });
				items.push(text(x + pad + offset, top + rowH / 2, label.text, { size: label.size }, { family: 'body', weight: 600, color: 'text', baseline: 'middle' }));
			});
		});
		y += heights[row] + gap;
	});
	return { width, height, items };
}

/**
 * One team's 1080 square card: the logo and event line on top, the team name very large, then
 * the players in 1 column up to 3, 2 up to 8 and 3 beyond (a portrait over a name in 3 columns),
 * the portrait size following the room each player has.
 */
export function cardLayout(team, { photos, measure, labels, size = CARD.size }) {
	const { margin, areaTop, gap } = CARD;
	const items = [{ type: 'rect', x: 0, y: 0, w: size, h: size, fill: 'bg' }];
	items.push({ type: 'logo', x: margin, y: margin, w: 84, h: 80 });
	items.push(text(size - margin, margin + 52, labels.event, fitText(measure, labels.event, { family: 'body', weight: 600, size: 30, min: 20, maxWidth: size - 2 * margin - 120 }), { family: 'body', weight: 600, color: 'muted', align: 'right' }));

	const name = fitText(measure, team.name, { family: 'display', weight: 400, size: 168, min: 72, maxWidth: size - 2 * margin });
	items.push(text(size / 2, 380, name.text, { size: name.size }, { family: 'display', weight: 400, color: 'ink', align: 'center' }));
	items.push({ type: 'rect', x: size / 2 - 80, y: 408, w: 160, h: 6, fill: 'gold' });

	const players = orderedPlayers(team.players);
	const n = players.length;
	if (n > 0) {
		const cols = n <= 3 ? 1 : n <= 8 ? 2 : 3;
		const rows = Math.ceil(n / cols);
		const areaH = size - margin - areaTop;
		const cellW = (size - 2 * margin - (cols - 1) * gap) / cols;
		const cellH = Math.min(areaH / rows, 190);
		const top0 = areaTop + (areaH - rows * cellH) / 2;
		const stacked = cols === 3;
		players.forEach((p, i) => {
			const cx = margin + (i % cols) * (cellW + gap);
			const cy = top0 + Math.floor(i / cols) * cellH;
			const label = fullName(p);
			if (stacked) {
				const a = photos ? Math.min(cellH - 56, 110) : 0;
				if (photos) items.push(avatar(cx + (cellW - a) / 2, cy + 4, a, p));
				const fit = fitText(measure, label, { family: 'body', weight: 700, size: 32, min: 20, maxWidth: cellW });
				items.push(text(cx + cellW / 2, cy + (photos ? a + 36 : cellH / 2), fit.text, { size: fit.size }, { family: 'body', weight: 700, color: 'ink', align: 'center', baseline: photos ? 'alphabetic' : 'middle' }));
			} else {
				const a = photos ? Math.min(cellH - 20, 150, cellW * 0.4) : 0;
				const offset = photos ? a + 28 : 0;
				if (photos) items.push(avatar(cx, cy + (cellH - a) / 2, a, p));
				const preferred = Math.min(photos ? 54 : 64, Math.round(cellH * 0.3));
				const fit = fitText(measure, label, { family: 'body', weight: 700, size: preferred, min: 24, maxWidth: cellW - offset });
				items.push(text(cx + offset, cy + cellH / 2, fit.text, { size: fit.size }, { family: 'body', weight: 700, color: 'ink', baseline: 'middle' }));
			}
		});
	}
	return { width: size, height: size, items };
}
```

If a test in Step 1 disagrees with the code in a way that is the test's arithmetic rather than the behaviour the spec pins (for example the exact avatar size comparison for 8 versus 9 players), fix the test to state the behaviour, never loosen what it pins: few players → bigger portraits; the three-column cards still show every player.

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] announce: poster and card layouts`.

### Task 2: ZIP writer

**Files:** Create `front/src/lib/announce/zip.js`; Test `zip.test.js`.

- [ ] **Step 1: Failing tests**

```js
import { describe, expect, it } from 'vitest';
import { crc32, makeZip } from './zip.js';

const bytes = (text) => new TextEncoder().encode(text);

/** A minimal reader: the entries of a ZIP through its central directory. */
function readZip(zip) {
	const view = new DataView(zip.buffer, zip.byteOffset, zip.byteLength);
	let end = zip.length - 22;
	while (view.getUint32(end, true) !== 0x06054b50) end -= 1;
	const count = view.getUint16(end + 10, true);
	let offset = view.getUint32(end + 16, true);
	const out = [];
	for (let i = 0; i < count; i++) {
		expect(view.getUint32(offset, true)).toBe(0x02014b50);
		const flags = view.getUint16(offset + 8, true);
		const method = view.getUint16(offset + 10, true);
		const crc = view.getUint32(offset + 16, true);
		const size = view.getUint32(offset + 20, true);
		const nameLen = view.getUint16(offset + 28, true);
		const local = view.getUint32(offset + 42, true);
		const name = new TextDecoder().decode(zip.subarray(offset + 46, offset + 46 + nameLen));
		expect(view.getUint32(local, true)).toBe(0x04034b50);
		const localNameLen = view.getUint16(local + 26, true);
		const start = local + 30 + localNameLen;
		out.push({ name, flags, method, crc, size, data: zip.slice(start, start + size) });
		offset += 46 + nameLen;
	}
	return out;
}

describe('crc32', () => {
	it('matches the standard check value', () => {
		expect(crc32(bytes('123456789'))).toBe(0xcbf43926);
		expect(crc32(new Uint8Array())).toBe(0);
	});
});

describe('makeZip', () => {
	it('stores each file under its name, with its CRC, uncompressed', () => {
		const zip = makeZip([
			{ name: 'a.png', data: bytes('hello') },
			{ name: 'équipe-2.png', data: new Uint8Array([0, 1, 2, 255]) }
		]);

		const entries = readZip(zip);
		expect(entries.map((e) => e.name)).toEqual(['a.png', 'équipe-2.png']);
		expect(entries.every((e) => e.method === 0 && (e.flags & 0x0800) !== 0)).toBe(true);
		expect(new TextDecoder().decode(entries[0].data)).toBe('hello');
		expect([...entries[1].data]).toEqual([0, 1, 2, 255]);
		expect(entries[0].crc).toBe(crc32(bytes('hello')));
		expect(entries[0].size).toBe(5);
	});

	it('makes an empty but valid archive', () => {
		const zip = makeZip([]);

		expect(zip.length).toBe(22);
		expect(readZip(zip)).toEqual([]);
	});
});
```

- [ ] **Step 2: Run red.** **Step 3: Implement** `zip.js`:

```js
const TABLE = (() => {
	const table = new Uint32Array(256);
	for (let n = 0; n < 256; n++) {
		let c = n;
		for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
		table[n] = c >>> 0;
	}
	return table;
})();

/** CRC-32 of some bytes (the checksum a ZIP stores for each file). */
export function crc32(bytes) {
	let c = 0xffffffff;
	for (const byte of bytes) c = TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
	return (c ^ 0xffffffff) >>> 0;
}

const dosTime = (d) => (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1);
const dosDate = (d) => ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();

/**
 * A ZIP archive of `files` (`{ name, data: Uint8Array }`), every file stored uncompressed (PNGs
 * are already compressed), names in UTF-8. Returns the archive's bytes.
 */
export function makeZip(files, now = new Date()) {
	const encoder = new TextEncoder();
	const entries = files.map((file) => ({
		name: encoder.encode(file.name),
		data: file.data,
		crc: crc32(file.data)
	}));
	const time = dosTime(now);
	const date = dosDate(now);
	const localSize = entries.reduce((sum, e) => sum + 30 + e.name.length + e.data.length, 0);
	const centralSize = entries.reduce((sum, e) => sum + 46 + e.name.length, 0);
	const out = new Uint8Array(localSize + centralSize + 22);
	const view = new DataView(out.buffer);

	let offset = 0;
	const offsets = [];
	for (const e of entries) {
		offsets.push(offset);
		view.setUint32(offset, 0x04034b50, true);
		view.setUint16(offset + 4, 20, true); // version needed
		view.setUint16(offset + 6, 0x0800, true); // UTF-8 names
		view.setUint16(offset + 8, 0, true); // stored
		view.setUint16(offset + 10, time, true);
		view.setUint16(offset + 12, date, true);
		view.setUint32(offset + 14, e.crc, true);
		view.setUint32(offset + 18, e.data.length, true);
		view.setUint32(offset + 22, e.data.length, true);
		view.setUint16(offset + 26, e.name.length, true);
		view.setUint16(offset + 28, 0, true);
		out.set(e.name, offset + 30);
		out.set(e.data, offset + 30 + e.name.length);
		offset += 30 + e.name.length + e.data.length;
	}

	const centralStart = offset;
	entries.forEach((e, i) => {
		view.setUint32(offset, 0x02014b50, true);
		view.setUint16(offset + 4, 20, true); // made by
		view.setUint16(offset + 6, 20, true); // needed
		view.setUint16(offset + 8, 0x0800, true);
		view.setUint16(offset + 10, 0, true);
		view.setUint16(offset + 12, time, true);
		view.setUint16(offset + 14, date, true);
		view.setUint32(offset + 16, e.crc, true);
		view.setUint32(offset + 20, e.data.length, true);
		view.setUint32(offset + 24, e.data.length, true);
		view.setUint16(offset + 28, e.name.length, true);
		// extra, comment, disk, internal and external attributes stay zero
		view.setUint32(offset + 42, offsets[i], true);
		out.set(e.name, offset + 46);
		offset += 46 + e.name.length;
	});

	view.setUint32(offset, 0x06054b50, true);
	view.setUint16(offset + 8, entries.length, true);
	view.setUint16(offset + 10, entries.length, true);
	view.setUint32(offset + 12, centralSize, true);
	view.setUint32(offset + 16, centralStart, true);
	return out;
}
```

- [ ] **Step 4: Run green.** Also validate once with a real unzip when available: build a ZIP in a node script from the test fixture and run `unzip -t` on it (Python's `zipfile.ZipFile(...).testzip()` works too); note the result in the report. **Step 5: Commit** `[FEAT] announce: store-only ZIP writer`.

### Task 3: Palette and painter

**Files:** Create `palette.js`, `draw.js`; Test `palette.test.js`, `draw.test.js`.

- [ ] **Step 1: Failing tests.** `palette.test.js`:

```js
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { PALETTE } from './palette.js';

const css = readFileSync(new URL('../../routes/styles.css', import.meta.url), 'utf8');
const dark = css.slice(css.indexOf(':root {'), css.indexOf('}', css.indexOf(':root {')));
const token = (name) => new RegExp(`${name}:\\s*(#[0-9a-fA-F]{3,8})`).exec(dark)?.[1].toLowerCase();

describe('PALETTE', () => {
	it.each([
		['bg', '--bg'],
		['raised', '--bg-raised'],
		['sunken', '--bg-sunken'],
		['line', '--line'],
		['ink', '--ink'],
		['text', '--text'],
		['muted', '--muted'],
		['accent', '--accent'],
		['gold', '--gold']
	])('%s is the dark theme token %s', (key, name) => {
		expect(token(name), name).toBeDefined();
		expect(PALETTE[key].toLowerCase()).toBe(token(name));
	});
});
```

`draw.test.js`:

```js
import { describe, expect, it, vi } from 'vitest';
import { drawLayout } from './draw.js';
import { PALETTE } from './palette.js';

/** A 2D context that records what is drawn. */
function fakeContext() {
	const calls = [];
	const ctx = new Proxy(
		{ font: '', fillStyle: '', strokeStyle: '', lineWidth: 0, textAlign: '', textBaseline: '' },
		{
			get: (target, key) => (key in target ? target[key] : (...args) => calls.push([key, ...args])),
			set: (target, key, value) => ((target[key] = value), calls.push(['set', key, value]), true)
		}
	);
	return { ctx, calls, drawn: (name) => calls.filter(([k]) => k === name) };
}

const image = { width: 128, height: 128 };
const layout = (items) => ({ width: 100, height: 100, items });
const avatarItem = (photo) => ({ type: 'avatar', x: 10, y: 20, size: 60, player: { first_name: 'Ana', last_name: 'Lopez', photo } });
const textItem = { type: 'text', x: 5, y: 9, text: 'Aigles', family: 'display', weight: 400, size: 64, color: 'accent', align: 'center' };

describe('drawLayout', () => {
	it('fills rects with the palette colour, rounded when asked, with a stroke', () => {
		const { ctx, calls, drawn } = fakeContext();

		drawLayout(ctx, layout([{ type: 'rect', x: 1, y: 2, w: 30, h: 40, fill: 'raised', stroke: 'line', radius: 8 }]), { images: new Map() });

		expect(calls.some(([k, key, v]) => k === 'set' && key === 'fillStyle' && v === PALETTE.raised)).toBe(true);
		expect(drawn('fill').length).toBe(1);
		expect(drawn('stroke').length).toBe(1);
	});

	it('writes texts with the font, colour and alignment of the item', () => {
		const { ctx, calls, drawn } = fakeContext();

		drawLayout(ctx, layout([textItem]), { images: new Map() });

		expect(drawn('fillText')).toEqual([['fillText', 'Aigles', 5, 9]]);
		expect(calls).toContainEqual(['set', 'font', '400 64px "Bebas Neue", sans-serif']);
		expect(calls).toContainEqual(['set', 'fillStyle', PALETTE.accent]);
		expect(calls).toContainEqual(['set', 'textAlign', 'center']);
	});

	it('draws the logo and title images when loaded and skips them when not', () => {
		const items = [{ type: 'logo', x: 1, y: 2, w: 10, h: 12 }, { type: 'title', x: 3, y: 4, w: 20, h: 14 }];
		const withImages = fakeContext();
		const without = fakeContext();

		drawLayout(withImages.ctx, layout(items), { images: new Map([['logo', image], ['title', image]]) });
		drawLayout(without.ctx, layout(items), { images: new Map() });

		expect(withImages.drawn('drawImage')).toHaveLength(2);
		expect(without.drawn('drawImage')).toHaveLength(0);
	});

	it('clips a player photo to a circle', () => {
		const { ctx, drawn } = fakeContext();

		drawLayout(ctx, layout([avatarItem('/media/avatars/1-sm.webp')]), { images: new Map([['/media/avatars/1-sm.webp', image]]) });

		expect(drawn('clip')).toHaveLength(1);
		expect(drawn('drawImage')).toEqual([['drawImage', image, 10, 20, 60, 60]]);
	});

	it('draws the initials on a round when there is no photo, or the photo did not load', () => {
		for (const [photo, images] of [[null, new Map()], ['/media/avatars/missing.webp', new Map()]]) {
			const { ctx, drawn } = fakeContext();

			drawLayout(ctx, layout([avatarItem(photo)]), { images });

			expect(drawn('drawImage')).toHaveLength(0);
			expect(drawn('fillText').map(([, t]) => t)).toEqual(['AL']);
			expect(drawn('arc').length).toBeGreaterThan(0);
		}
	});

	it('does not throw on an empty layout', () => {
		expect(() => drawLayout(fakeContext().ctx, layout([]), { images: new Map() })).not.toThrow();
	});
});
```

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement.** `palette.js`:

```js
/**
 * The colours of the announcement images: always the dark brand look, whatever theme the
 * organiser browses in, so they are fixed here instead of read from the page. `palette.test.js`
 * pins each to its dark token in routes/styles.css.
 */
export const PALETTE = {
	bg: '#000000',
	raised: '#141414',
	sunken: '#121212',
	line: '#262626',
	ink: '#ffffff',
	text: '#f2ecc8',
	muted: '#8a8674',
	accent: '#F9F3C1',
	gold: '#e6b800'
};
```

`draw.js`:

```js
import { initials } from '$lib/avatar.js';
import { fontString } from './layout.js';
import { PALETTE } from './palette.js';

/** A rounded rectangle path (the context's own roundRect is not everywhere yet). */
function roundedRect(ctx, x, y, w, h, r) {
	const radius = Math.min(r, w / 2, h / 2);
	ctx.beginPath();
	ctx.moveTo(x + radius, y);
	ctx.arcTo(x + w, y, x + w, y + h, radius);
	ctx.arcTo(x + w, y + h, x, y + h, radius);
	ctx.arcTo(x, y + h, x, y, radius);
	ctx.arcTo(x, y, x + w, y, radius);
	ctx.closePath();
}

function drawRect(ctx, item) {
	if (item.radius) roundedRect(ctx, item.x, item.y, item.w, item.h, item.radius);
	else {
		ctx.beginPath();
		ctx.rect(item.x, item.y, item.w, item.h);
	}
	ctx.fillStyle = PALETTE[item.fill];
	ctx.fill();
	if (item.stroke) {
		ctx.strokeStyle = PALETTE[item.stroke];
		ctx.lineWidth = 2;
		ctx.stroke();
	}
}

function drawText(ctx, item) {
	ctx.font = fontString(item);
	ctx.fillStyle = PALETTE[item.color];
	ctx.textAlign = item.align ?? 'left';
	ctx.textBaseline = item.baseline ?? 'alphabetic';
	ctx.fillText(item.text, item.x, item.y);
}

/** A player's round: the photo clipped to a circle, else their initials on a plain round. */
function drawAvatar(ctx, item, images) {
	const { x, y, size, player } = item;
	const cx = x + size / 2;
	const cy = y + size / 2;
	const photo = player.photo ? images.get(player.photo) : null;
	if (photo) {
		ctx.save();
		ctx.beginPath();
		ctx.arc(cx, cy, size / 2, 0, Math.PI * 2);
		ctx.clip();
		ctx.drawImage(photo, x, y, size, size);
		ctx.restore();
	} else {
		ctx.beginPath();
		ctx.arc(cx, cy, size / 2, 0, Math.PI * 2);
		ctx.fillStyle = PALETTE.sunken;
		ctx.fill();
		ctx.font = fontString({ family: 'body', weight: 700, size: Math.round(size * 0.38) });
		ctx.fillStyle = PALETTE.muted;
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(initials(player.first_name, player.last_name), cx, cy);
	}
	ctx.beginPath();
	ctx.arc(cx, cy, size / 2 - 1, 0, Math.PI * 2);
	ctx.strokeStyle = PALETTE.line;
	ctx.lineWidth = 2;
	ctx.stroke();
}

/**
 * Paint a layout (`layout.js`) onto a 2D context. `images` maps `'logo'`, `'title'` and the
 * photo URLs to loaded images; a missing one is simply skipped (initials for a player).
 */
export function drawLayout(ctx, layout, { images }) {
	for (const item of layout.items) {
		if (item.type === 'rect') drawRect(ctx, item);
		else if (item.type === 'text') drawText(ctx, item);
		else if (item.type === 'avatar') drawAvatar(ctx, item, images);
		else {
			const image = images.get(item.type);
			if (image) ctx.drawImage(image, item.x, item.y, item.w, item.h);
		}
	}
}
```

If the fake context's `Proxy` mishandles `ctx.fill`-style property reads (it returns a recorder for any unknown key), keep it as written: it is the intended seam.

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] announce: palette and canvas painter`.

### Task 4: Images, fonts and exports

**Files:** Create `images.js`, `export.js`; Test `images.test.js`, `export.test.js`.

- [ ] **Step 1: Failing tests.** `images.test.js`:

```js
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fontsReady, loadImage, loadImages } from './images.js';

class FakeImage {
	set src(url) {
		this._src = url;
		queueMicrotask(() => (url.includes('broken') ? this.onerror?.() : this.onload?.()));
	}
	get src() {
		return this._src;
	}
}

afterEach(() => vi.unstubAllGlobals());

describe('loadImage', () => {
	it('resolves the image once loaded and null when it fails', async () => {
		vi.stubGlobal('Image', FakeImage);

		expect((await loadImage('/media/a.webp')).src).toBe('/media/a.webp');
		expect(await loadImage('/media/broken.webp')).toBeNull();
	});
});

describe('loadImages', () => {
	it('loads each distinct url once and leaves out the failures and the blanks', async () => {
		const made = [];
		vi.stubGlobal('Image', class extends FakeImage { constructor() { super(); made.push(this); } });

		const images = await loadImages(['/a.webp', '/a.webp', null, '/broken.webp', '/b.webp']);

		expect([...images.keys()].sort()).toEqual(['/a.webp', '/b.webp']);
		expect(made).toHaveLength(3);
	});
});

describe('fontsReady', () => {
	it('waits for the faces the images use, and tolerates a browser without the font API', async () => {
		const load = vi.fn(() => Promise.resolve([]));
		vi.stubGlobal('document', { fonts: { load } });

		await fontsReady();

		expect(load.mock.calls.map(([f]) => f)).toEqual(
			expect.arrayContaining([expect.stringContaining('Bebas Neue'), expect.stringContaining('Inter')])
		);
		vi.stubGlobal('document', {});
		await expect(fontsReady()).resolves.toBeUndefined();
	});
});
```

`export.test.js`:

```js
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cardFileName, download, downloadZip, posterFileName, slug, toPng } from './export.js';

afterEach(() => vi.unstubAllGlobals());

describe('file names', () => {
	it('slugifies accents and punctuation', () => {
		expect(slug('Les Écureuils d’Or !')).toBe('les-ecureuils-d-or');
		expect(slug('')).toBe('equipe');
	});

	it('names the poster and the cards', () => {
		expect(posterFileName(2029)).toBe('equipes-2029.png');
		expect(cardFileName(3, 'Équipe 3')).toBe('equipe-03-equipe-3.png');
		expect(cardFileName(12, 'Aigles')).toBe('equipe-12-aigles.png');
	});
});

describe('toPng', () => {
	it('resolves the blob the canvas gives and rejects when it gives none', async () => {
		const blob = new Blob(['x']);

		await expect(toPng({ toBlob: (cb, type) => cb(type === 'image/png' ? blob : null) })).resolves.toBe(blob);
		await expect(toPng({ toBlob: (cb) => cb(null) })).rejects.toThrow();
	});
});

describe('download', () => {
	it('clicks a temporary link to an object URL and revokes it', () => {
		vi.useFakeTimers();
		const click = vi.fn();
		const link = { click, set href(v) { this._href = v; }, set download(v) { this._download = v; } };
		vi.stubGlobal('document', { createElement: () => link, body: { append: vi.fn(), removeChild: vi.fn() } });
		vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() });

		download(new Blob(['x']), 'a.png');

		expect(click).toHaveBeenCalled();
		expect(link._download).toBe('a.png');
		vi.runAllTimers();
		expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:x');
		vi.useRealTimers();
	});
});

describe('downloadZip', () => {
	it('zips the blobs under their names and downloads the archive', async () => {
		const click = vi.fn();
		let archive;
		const link = { click, set href(v) {}, set download(v) { this._d = v; } };
		vi.stubGlobal('document', { createElement: () => link, body: { append: vi.fn(), removeChild: vi.fn() } });
		vi.stubGlobal('URL', { createObjectURL: vi.fn((blob) => ((archive = blob), 'blob:z')), revokeObjectURL: vi.fn() });

		await downloadZip([{ name: 'a.png', blob: new Blob(['hello']) }], 'equipes-2029.zip');

		expect(link._d).toBe('equipes-2029.zip');
		expect(archive.type).toBe('application/zip');
		expect(archive.size).toBeGreaterThan(5 + 30 + 46 + 22);
		expect(click).toHaveBeenCalled();
	});
});
```

- [ ] **Step 2: Run red.** **Step 3: Implement.**

`images.js`:
```js
/** An image loaded from `url`, or null when it fails (a missing photo is not an error here). */
export function loadImage(url) {
	return new Promise((resolve) => {
		const image = new Image();
		image.onload = () => resolve(image);
		image.onerror = () => resolve(null);
		image.src = url;
	});
}

/** The images of `urls` (each distinct url once, blanks and failures left out) as a Map. */
export async function loadImages(urls) {
	const unique = [...new Set(urls.filter(Boolean))];
	const loaded = await Promise.all(unique.map(async (url) => [url, await loadImage(url)]));
	return new Map(loaded.filter(([, image]) => image));
}

const FACES = ['400 40px "Bebas Neue"', '500 20px Inter', '600 20px Inter', '700 20px Inter'];

/** Resolves once the site's fonts are loaded, so the first draw is not in a fallback face. */
export async function fontsReady() {
	if (!globalThis.document?.fonts) return;
	await Promise.all(FACES.map((face) => document.fonts.load(face).catch(() => [])));
}
```

`export.js`:
```js
import { makeZip } from './zip.js';

/** A file-name-safe version of a text: no accents, lower case, dashes. */
export const slug = (text) =>
	String(text ?? '')
		.normalize('NFD')
		.replace(/\p{M}/gu, '')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '') || 'equipe';

export const posterFileName = (year) => `equipes-${year}.png`;
export const cardFileName = (index, name) => `equipe-${String(index).padStart(2, '0')}-${slug(name)}.png`;

/** The PNG of a canvas as a Blob. */
export function toPng(canvas) {
	return new Promise((resolve, reject) => {
		canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('The canvas gave no image'))), 'image/png');
	});
}

/** Save a blob as a file: a temporary link to an object URL, revoked right after. */
export function download(blob, name) {
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = name;
	document.body.append(link);
	link.click();
	document.body.removeChild(link);
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Save `entries` (`{ name, blob }`) as one store-only ZIP called `zipName`. */
export async function downloadZip(entries, zipName) {
	const files = await Promise.all(
		entries.map(async ({ name, blob }) => ({ name, data: new Uint8Array(await blob.arrayBuffer()) }))
	);
	download(new Blob([makeZip(files)], { type: 'application/zip' }), zipName);
}
```

(In the `download` test the stubbed `document.body.removeChild` is used; in a real page `link.remove()` also works: keep `removeChild`.)

- [ ] **Step 4: Run green.** **Step 5: Commit** `[FEAT] announce: image and font loading, PNG and ZIP exports`.

### Task 5: Dictionaries and the page

**Files:** Create `routes/[year=year]/announce/+page.server.js`, `+page.svelte`; Test `page.server.test.js`, `page.test.js`; Modify `routes/+layout.svelte` (`NO_TAB_BAR`), `i18n/fr.js`, `en.js`.

- [ ] **Step 1: Dictionaries.** Add to both (after the `builder.*` block), French first:

```js
	'announce.title': 'Annoncer les équipes',
	'announce.link': 'Annoncer les équipes',
	'announce.empty': "Il n'y a pas encore d'équipes à annoncer.",
	'announce.photos': 'Afficher les photos',
	'announce.photos.notice': 'Les photos ont été ajoutées pour le site : vérifiez que vous pouvez les diffuser ailleurs.',
	'announce.lang': 'Langue des images',
	'announce.loading': 'Préparation des images…',
	'announce.failed': "La préparation de l'image a échoué : réessayez.",
	'announce.poster.heading': "L'affiche",
	'announce.poster.alt': "Aperçu de l'affiche des équipes",
	'announce.poster.download': "Télécharger l'affiche",
	'announce.cards.heading': "Les cartes d'équipe",
	'announce.card.alt': 'Aperçu de la carte de {name}',
	'announce.card.download': 'Télécharger la carte de {name}',
	'announce.all': 'Tout télécharger (ZIP)',
	'announce.draw.title': 'Les équipes {year}',
	'announce.draw.event': 'Olympic Warriors {year}',
```
English: « Announce the teams », « Announce the teams », « There are no teams to announce yet. », « Show photos », « Photos were added for the site: check you can share them elsewhere. », « Image language », « Preparing the images… », « Preparing the image failed: try again. », « The poster », « Preview of the teams poster », « Download the poster », « The team cards », « Preview of the card of {name} », « Download the card of {name} », « Download everything (ZIP) », « The {year} teams », « Olympic Warriors {year} ».

`routes/+layout.svelte`: add `'/[year=year]/announce'` to `NO_TAB_BAR`. Run `npx vitest run src/lib/i18n`.

- [ ] **Step 2: Failing tests.** `page.server.test.js` (copy the builder's `page.server.test.js` shape: `// @vitest-environment node`, a faked event):

```js
// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server.js';

const event = (over = {}) => ({
	params: { year: '2029' },
	cookies: { get: () => 'tok' },
	setHeaders: vi.fn(),
	parent: async () => ({ organiser: true, latestYear: 2029 }),
	...over
});

describe('announce load', () => {
	it('sends a visitor to the login and refuses a player', async () => {
		await expect(load(event({ cookies: { get: () => undefined }, parent: async () => ({ organiser: false, latestYear: 2029 }) }))).rejects.toMatchObject({ status: 303, location: '/login?next=/2029/announce' });
		await expect(load(event({ parent: async () => ({ organiser: false, latestYear: 2029 }) }))).rejects.toMatchObject({ status: 403 });
	});

	it('is 404 for a year that is not the latest', async () => {
		await expect(load(event({ params: { year: '2028' } }))).rejects.toMatchObject({ status: 404 });
	});

	it('lets an organiser in and never caches the page', async () => {
		const e = event();

		await load(e);

		expect(e.setHeaders).toHaveBeenCalledWith({ 'cache-control': 'private, no-store' });
	});
});
```

`page.test.js` (the fake canvas context: `HTMLCanvasElement.prototype.getContext` and `toBlob` stubbed; `loadImages`/`fontsReady` mocked; `$lib/announce/export.js` mocked for the downloads):

```js
import { fireEvent, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { summary } from '$lib/fixtures/summary.js';
import Page from './+page.svelte';

vi.mock('$lib/announce/images.js', () => ({
	fontsReady: vi.fn(async () => {}),
	loadImages: vi.fn(async () => new Map())
}));
vi.mock('$lib/announce/export.js', async (original) => ({
	...(await original()),
	toPng: vi.fn(async () => new Blob(['png'])),
	download: vi.fn(),
	downloadZip: vi.fn(async () => {})
}));

import { loadImages } from '$lib/announce/images.js';
import { download, downloadZip } from '$lib/announce/export.js';

const calls = [];
beforeEach(() => {
	calls.length = 0;
	localStorage.clear();
	const ctx = new Proxy({}, { get: (_, key) => (key === 'measureText' ? (t) => ({ width: String(t).length * 10 }) : (...args) => calls.push([key, ...args])), set: () => true });
	vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx);
	vi.mocked(loadImages).mockClear();
	vi.mocked(download).mockClear();
	vi.mocked(downloadZip).mockClear();
});
afterEach(() => vi.restoreAllMocks());

const data = (teams = summary.teams) => ({ summary: { ...summary, teams }, editable: true });
const filled = (name) => calls.filter(([k, text]) => k === 'fillText' && text === name);

describe('announce page', () => {
	it('draws the poster and a card per team, in French, with the photos off', async () => {
		renderWith(Page, { data: data() });

		await waitFor(() => expect(screen.queryByText('Preparing the images…')).toBeNull());
		expect(screen.getByRole('img', { name: 'Preview of the teams poster' })).toBeInTheDocument();
		expect(screen.getAllByRole('img', { name: /^Preview of the card of / })).toHaveLength(3);
		expect(filled('Aigles').length).toBeGreaterThanOrEqual(2); // on the poster and on its card
		// the page is in English, the images are not: French unless the organiser picks another
		expect(filled('Les équipes 2026').length).toBeGreaterThan(0);
		expect(screen.getByLabelText('Show photos')).not.toBeChecked();
		expect(screen.queryByText(/Photos were added for the site/)).toBeNull();
	});

	it('shows the photos, with the reminder, when the switch is turned on, and remembers it', async () => {
		renderWith(Page, { data: data() });
		await waitFor(() => expect(loadImages).toHaveBeenCalled());
		expect(vi.mocked(loadImages).mock.calls[0][0]).toContain('/media/avatars/11-7c3e9a1f5b2d-sm.webp');

		await fireEvent.click(screen.getByLabelText('Show photos'));

		expect(screen.getByLabelText('Show photos')).toBeChecked();
		expect(screen.getByText(/Photos were added for the site/)).toBeInTheDocument();
		expect(localStorage.getItem('announce.photos')).toBe('on');
		await waitFor(() => expect(calls.some(([k]) => k === 'clip' || k === 'drawImage')).toBe(true));
	});

	it('starts with the photos on when the browser remembers that', async () => {
		localStorage.setItem('announce.photos', 'on');
		renderWith(Page, { data: data() });

		await waitFor(() => expect(screen.getByLabelText('Show photos')).toBeChecked());
	});

	it('writes the images in the language picked on the page, and remembers it', async () => {
		renderWith(Page, { data: data() });
		await waitFor(() => expect(screen.queryByText('Preparing the images…')).toBeNull());
		expect(screen.getByLabelText('Image language')).toHaveValue('fr');

		await fireEvent.change(screen.getByLabelText('Image language'), { target: { value: 'en' } });

		await waitFor(() => expect(filled('The 2026 teams').length).toBeGreaterThan(0));
		expect(localStorage.getItem('announce.lang')).toBe('en');
	});

	it('starts in the remembered language', async () => {
		localStorage.setItem('announce.lang', 'en');
		renderWith(Page, { data: data() });

		await waitFor(() => expect(screen.getByLabelText('Image language')).toHaveValue('en'));
		await waitFor(() => expect(filled('The 2026 teams').length).toBeGreaterThan(0));
	});

	it('downloads the poster, one card and everything', async () => {
		renderWith(Page, { data: data() });
		await waitFor(() => expect(screen.queryByText('Preparing the images…')).toBeNull());

		await fireEvent.click(screen.getByRole('button', { name: 'Download the poster' }));
		await waitFor(() => expect(download).toHaveBeenCalledWith(expect.any(Blob), 'equipes-2026.png'));

		await fireEvent.click(screen.getByRole('button', { name: 'Download the card of Bisons' }));
		await waitFor(() => expect(download).toHaveBeenCalledWith(expect.any(Blob), 'equipe-02-bisons.png'));

		await fireEvent.click(screen.getByRole('button', { name: 'Download everything (ZIP)' }));
		await waitFor(() => expect(downloadZip).toHaveBeenCalled());
		const [entries, zipName] = vi.mocked(downloadZip).mock.calls[0];
		expect(zipName).toBe('equipes-2026.zip');
		expect(entries.map((e) => e.name)).toEqual(['equipes-2026.png', 'equipe-01-aigles.png', 'equipe-02-bisons.png', 'equipe-03-cerfs.png']);
	});

	it('words a failed download', async () => {
		vi.mocked(download).mockImplementation(() => {
			throw new Error('nope');
		});
		renderWith(Page, { data: data() });
		await waitFor(() => expect(screen.queryByText('Preparing the images…')).toBeNull());

		await fireEvent.click(screen.getByRole('button', { name: 'Download the poster' }));

		await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Preparing the image failed'));
	});

	it('says there is nothing to announce yet, with a way to the builder', () => {
		renderWith(Page, { data: data([]) });

		expect(screen.getByText('There are no teams to announce yet.')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Build the teams' })).toHaveAttribute('href', '/2026/builder');
		expect(screen.queryByRole('button', { name: 'Download the poster' })).toBeNull();
	});

	it('speaks French', async () => {
		renderWith(Page, { data: data() }, 'fr');

		expect(screen.getByRole('heading', { name: 'Annoncer les équipes' })).toBeInTheDocument();
		await waitFor(() => expect(screen.getByRole('button', { name: "Télécharger l'affiche" })).toBeInTheDocument());
	});
});
```

The fixture `summary` has teams Aigles (id 1, two players, Ana with a photo), Bisons (id 2), Cerfs (id 3, no players): the file names above follow their ids. If `toPng` is called with a real canvas element, the stub of `HTMLCanvasElement.prototype.toBlob` is not needed because `toPng` is mocked.

- [ ] **Step 3: Run red.**
- [ ] **Step 4: Implement.**

`+page.server.js`:
```js
import { error, redirect } from '@sveltejs/kit';
import { TOKEN_COOKIE } from '$lib/session';

/**
 * The announcement visuals: organisers only, the latest edition only, never cached. It reads
 * the summary the year layout already loads, so it fetches nothing itself.
 */
export const load = async ({ params, cookies, parent, setHeaders }) => {
	const { organiser, latestYear } = await parent();
	if (!cookies.get(TOKEN_COOKIE)) redirect(303, `/login?next=/${params.year}/announce`);
	if (!organiser) error(403, 'Organisers only');
	if (Number(params.year) !== latestYear) error(404, `No announcement for ${params.year}`);
	setHeaders({ 'cache-control': 'private, no-store' });
	return {};
};
```

`+page.svelte`:
```svelte
<script>
	import { onMount, tick } from 'svelte';
	import { t as translate, useT } from '$lib/i18n';
	import { formatDateRange } from '$lib/edition';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import logo from '$lib/img/logo.svg';
	import title from '$lib/img/title.svg';
	import { cardLayout, posterLayout } from '$lib/announce/layout.js';
	import { drawLayout } from '$lib/announce/draw.js';
	import { fontsReady, loadImages } from '$lib/announce/images.js';
	import { cardFileName, download, downloadZip, posterFileName, toPng } from '$lib/announce/export.js';

	export let data;

	const t = useT();
	const PHOTOS_KEY = 'announce.photos';
	const LANG_KEY = 'announce.lang';

	$: edition = data.summary.edition;
	$: year = edition.year;
	$: teams = [...data.summary.teams].sort((a, b) => a.id - b.id);
	$: photoUrls = teams.flatMap((team) => team.players.map((p) => p.photo)).filter(Boolean);

	// Photos start off (players agreed to the site only) and the images start in French, whatever
	// the site's language: what an organiser chose is remembered, nothing else is.
	let photos = false;
	let lang = 'fr';
	let ready = false;
	let images = new Map();
	let failed = false;
	let posterCanvas;
	let cardCanvases = [];

	onMount(async () => {
		try {
			photos = localStorage.getItem(PHOTOS_KEY) === 'on';
			const saved = localStorage.getItem(LANG_KEY);
			if (saved === 'fr' || saved === 'en') lang = saved;
		} catch {
			// storage blocked: the defaults stand
		}
		await fontsReady();
		images = await loadImages([logo, title, ...photoUrls]);
		// `loadImages` keys the brand images by url; the painter looks them up by role.
		images.set('logo', images.get(logo));
		images.set('title', images.get(title));
		ready = true;
	});

	const measurer = () => {
		const ctx = document.createElement('canvas').getContext('2d');
		return (text, font) => {
			ctx.font = font;
			return ctx.measureText(text).width;
		};
	};

	function paint(canvas, layout) {
		if (!canvas) return;
		canvas.width = layout.width;
		canvas.height = layout.height;
		drawLayout(canvas.getContext('2d'), layout, { images });
	}

	// The text of the images, in the language chosen on the page (not the site's).
	$: labels = {
		title: translate(lang, 'announce.draw.title', { year }),
		subtitle: [edition.host, formatDateRange(edition.start_date, edition.end_date, lang)].filter(Boolean).join(' · '),
		event: translate(lang, 'announce.draw.event', { year })
	};
	// Redraw whenever the data, the switch or the images change.
	$: if (ready && teams.length > 0) draw(teams, photos, labels, images);
	async function draw(list, withPhotos, text, loaded) {
		await tick(); // the canvases exist after the first render with `ready`
		const measure = measurer();
		paint(posterCanvas, posterLayout(list, { photos: withPhotos, measure, labels: text }));
		list.forEach((team, i) => paint(cardCanvases[i], cardLayout(team, { photos: withPhotos, measure, labels: text })));
	}

	function setPhotos(event) {
		photos = event.currentTarget.checked;
		try {
			localStorage.setItem(PHOTOS_KEY, photos ? 'on' : 'off');
		} catch {
			// not remembered, still applied
		}
	}
	function setLang(event) {
		lang = event.currentTarget.value;
		try {
			localStorage.setItem(LANG_KEY, lang);
		} catch {
			// not remembered, still applied
		}
	}

	async function attempt(action) {
		failed = false;
		try {
			await action();
		} catch {
			failed = true;
		}
	}
	const downloadPoster = () => attempt(async () => download(await toPng(posterCanvas), posterFileName(year)));
	const downloadCard = (i) => attempt(async () => download(await toPng(cardCanvases[i]), cardFileName(i + 1, teams[i].name)));
	const downloadAll = () =>
		attempt(async () => {
			const entries = [{ name: posterFileName(year), blob: await toPng(posterCanvas) }];
			for (let i = 0; i < teams.length; i++) entries.push({ name: cardFileName(i + 1, teams[i].name), blob: await toPng(cardCanvases[i]) });
			await downloadZip(entries, `equipes-${year}.zip`);
		});
</script>

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: t('announce.title') }]} />
	<h1>{t('announce.title')}</h1>

	{#if teams.length === 0}
		<p class="notice">{t('announce.empty')}</p>
		<a class="pill-link" href="/{year}/builder">{t('builder.link')}</a>
	{:else}
		<div class="controls">
			<label class="check"><input type="checkbox" checked={photos} on:change={setPhotos} /> {t('announce.photos')}</label>
			<label class="check">
				{t('announce.lang')}
				<select value={lang} on:change={setLang}>
					<option value="fr">Français</option>
					<option value="en">English</option>
				</select>
			</label>
			<button type="button" class="submit" disabled={!ready} on:click={downloadAll}>{t('announce.all')}</button>
		</div>
		{#if photos}<p class="hint" role="note">{t('announce.photos.notice')}</p>{/if}
		{#if failed}<p class="error" role="alert">{t('announce.failed')}</p>{/if}
		{#if !ready}<p class="hint" role="status">{t('announce.loading')}</p>{/if}

		<section aria-labelledby="poster-title">
			<h2 id="poster-title">{t('announce.poster.heading')}</h2>
			<canvas class="preview" bind:this={posterCanvas} role="img" aria-label={t('announce.poster.alt')}></canvas>
			<button type="button" class="pill" disabled={!ready} on:click={downloadPoster}>{t('announce.poster.download')}</button>
		</section>

		<section aria-labelledby="cards-title">
			<h2 id="cards-title">{t('announce.cards.heading')}</h2>
			<ul class="cards">
				{#each teams as team, i (team.id)}
					<li>
						<canvas class="preview" bind:this={cardCanvases[i]} role="img" aria-label={t('announce.card.alt', { name: team.name })}></canvas>
						<button type="button" class="pill" disabled={!ready} on:click={() => downloadCard(i)}>{t('announce.card.download', { name: team.name })}</button>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
</div>

<style>
	.page {
		--page: min(100% - 2rem, 110rem);
		padding-bottom: 3rem;
	}
	h1 {
		margin: 0.2rem 0 1rem;
		overflow-wrap: anywhere;
	}
	h2 {
		font-size: 1rem;
		font-family: var(--font-body);
		text-transform: none;
		letter-spacing: 0;
		margin: 1.5rem 0 0.75rem;
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: center;
		margin-bottom: 1rem;
	}
	.check {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	select {
		padding: 0.375rem 0.5rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	.preview {
		display: block;
		width: 100%;
		height: auto;
		margin-bottom: 0.75rem;
		background: var(--bg-sunken);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(18rem, 100%), 1fr));
		gap: 1.25rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.notice,
	.error {
		margin: 0 0 1rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		background: var(--bg-raised);
	}
	.error {
		color: var(--loss);
		border-color: var(--loss);
	}
	.hint {
		color: var(--muted);
		font-size: 0.875rem;
		margin: 0 0 1rem;
	}
	.submit,
	.pill,
	.pill-link {
		justify-self: start;
		display: inline-block;
		padding: 0.625rem 1.25rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.submit {
		background: var(--accent);
		color: var(--bg);
	}
	button:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
```

Notes: (a) the previews follow `photos` and `lang`, whatever the site's language; (a2) a canvas only shows what is drawn at its real pixel size and is scaled by the CSS `width: 100%; height: auto`; (b) the page keeps no state in derived props: `draw` reads `data` and the switch only; (c) `images.get(logo)` may be `undefined` when the logo fails, and a map entry `undefined` is skipped by the painter's `if (image)`; (d) `localStorage` and `canvas` access happen only in `onMount`/handlers, so the server render does not touch them (the canvases render empty). In the page test the first render has `ready` false, so the previews exist but are blank, and the buttons are disabled until the images are ready.

- [ ] **Step 5: Run green** (`npx vitest run "src/routes/[year=year]/announce" src/lib/i18n src/lib/announce`), then the whole front suite and `npm run build`. Fix tests that rely on a label the page words differently by fixing the page or the dictionary, never by weakening an assertion.
- [ ] **Step 6: Commit** `[FEAT] announce page: previews, photos switch, PNG and ZIP downloads`.

### Task 6: Entry points

**Files:** Modify `routes/[year=year]/ranking/+page.svelte` and `page.test.js`; `components/builder/BuilderApply.svelte` and `BuilderApply.test.js`; `routes/[year=year]/builder/+page.svelte`.

- [ ] **Step 1: Failing tests.** Ranking page tests (use the file's existing helpers for `data`/year):

```js
it('offers the announcement visuals to an organiser of the latest edition once there are teams', () => {
	renderWith(Page, { data: { ...data, editable: true } }, 'en', true);

	expect(screen.getByRole('link', { name: 'Announce the teams' })).toHaveAttribute('href', '/2026/announce');
});

it('hides it from visitors, from older editions and while there are no teams', () => {
	renderWith(Page, { data: { ...data, editable: false } });
	expect(screen.queryByRole('link', { name: 'Announce the teams' })).toBeNull();

	renderWith(Page, { data: { ...data, editable: true, summary: { ...data.summary, teams: [] } } }, 'en', true);
	expect(screen.queryByRole('link', { name: 'Announce the teams' })).toBeNull();
});
```

`BuilderApply.test.js` (new case; it takes a `year` prop):

```js
it('links to the announcement visuals once the teams are created', () => {
	renderWith(BuilderApply, { ...base, year: 2029, done: { teams: [{ id: 1 }], unscheduled: [] } });

	expect(screen.getByRole('link', { name: 'Announce the teams' })).toHaveAttribute('href', '/2029/announce');
});
```
(use the file's own base props object name).

- [ ] **Step 2: Run red.** **Step 3: Implement.** Ranking page, after the builder link:
```svelte
	{#if data.editable && teams.length > 0}
		<a class="builder-link quiet-link" href="/{year}/announce">{t('announce.link')}</a>
	{/if}
```
`BuilderApply.svelte`: add `export let year = null;` and inside `{#if done}` after the success status: `{#if year}<a class="pill-link" href="/{year}/announce">{t('announce.link')}</a>{/if}` with a `.pill-link` style like the page's (tokens only). The builder page passes `{year}` to both `BuilderApply` usages (the `done` branch and the step-3 one).
- [ ] **Step 4: Run green**, whole suite, build. **Step 5: Commit** `[FEAT] announce: links from the builder's done screen and the ranking page`.

### Task 7: Docs and the browser walk

**Files:** `CLAUDE.md`.

- [ ] **Step 1:** After the **Team builder** paragraph's front half (or as its own short paragraph right after it), add **Announcement visuals** (spec `2026-10-05-team-announcement-visuals-design.md`): the route and its guards, the front-only data (the year layout's summary: teams by id, rosters by last name, small photo URLs), `$lib/announce/` (what each module does and that `layout.js` is pure with an injected measurer, `draw.js` the only canvas code, `palette.js` pinned to the dark tokens by `palette.test.js` because the images are always dark, `zip.js` store-only, `export.js`), the poster (1600 wide, height from content, columns 2/3/4 by team count) and the cards (1080 squares), the photos switch remembered in `localStorage` (`announce.photos`), the 128px photo limit, the entry points (builder's done screen, ranking page), the tests. Check with `git grep -n "Announcement visuals" CLAUDE.md` that there is one paragraph.
- [ ] **Step 2: Commit** `[DOCS] CLAUDE.md: the announcement visuals`.
- [ ] **Step 3 (controller only, with Hugo's yes; subagents never touch the dev DB):** the demo edition 2040 has no teams until the builder's teams are applied: with Hugo's go-ahead, apply them (builder, as `demo-admin`), then open `/2040/announce`: the poster and the cards on screen with photos on and off (the demo players of the real 2026 edition have photos only if they uploaded one: check initials and photos both render), a long name, a team of 1 and of 8 players if the data allows (else rely on the layout tests), the three downloads (open the PNGs and the ZIP: `unzip -t` on the downloaded file), the logo drawing in Firefox and Chromium-based browsers (an SVG without intrinsic size would draw as nothing; the logo has `width`/`height`), phone width of the page, and French. Clean up (`seed_demo_edition --remove`) only when Hugo says so.

---

## Self-review against the spec

- Poster 1600 wide with content-driven height and 2/3/4 columns; header; per-team blocks with title and rows; names shrink then truncate; photos switch changes row height → Task 1. Card 1080 square, logo, event line, large name, 1/2/3 columns by roster, portrait size by room, stacked layout in 3 columns, photos off → names larger → Task 1. Players ordered by last name, teams by id → Task 1 (`orderedPlayers`, the sort in both layouts).
- Painter with the logo/title, photo clipped to a circle, initials fallback, never throws on a missing image → Task 3. Fixed dark palette pinned to the tokens (the one deviation from the spec) → Task 3 and the deviation note.
- Image and font loading, failures tolerated → Task 4. ZIP store-only, UTF-8 names, CRC-32 → Task 2. PNG, file names, downloads, ZIP download → Task 4.
- Page guards (visitor, non-organiser, non-latest, no-store), no fetch, previews, photos switch remembered, empty state with the builder link, three downloads, error message, French → Task 5. `NO_TAB_BAR` → Task 5.
- Entry points: builder's done screen and ranking page → Task 6. `CLAUDE.md` and the walk → Task 7.
- Known limit stated in the spec and kept: photos are the 128px variant.
