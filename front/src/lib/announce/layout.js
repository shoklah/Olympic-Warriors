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
	// Cut by code points so an emoji is never split. When even one character plus the ellipsis is
	// too wide the ellipsis alone is returned, and nothing at all if that is too wide too.
	const chars = Array.from(text);
	while (chars.length > 1 && width(current, `${chars.join('')}…`) > maxWidth) chars.pop();
	const cut = `${chars.join('').trimEnd()}…`;
	if (width(current, cut) <= maxWidth) return { text: cut, size: current };
	return { text: width(current, '…') <= maxWidth ? '…' : '', size: current };
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
				// A portrait under 24px is not worth drawing: a crowded card falls back to names only.
				const a = photos ? Math.max(0, Math.min(cellH - 56, 110)) : 0;
				const withPortrait = a >= 24;
				if (withPortrait) items.push(avatar(cx + (cellW - a) / 2, cy + 4, a, p));
				const fit = fitText(measure, label, { family: 'body', weight: 700, size: 32, min: 20, maxWidth: cellW });
				items.push(text(cx + cellW / 2, cy + (withPortrait ? a + 36 : cellH / 2), fit.text, { size: fit.size }, { family: 'body', weight: 700, color: 'ink', align: 'center', baseline: withPortrait ? 'alphabetic' : 'middle' }));
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
