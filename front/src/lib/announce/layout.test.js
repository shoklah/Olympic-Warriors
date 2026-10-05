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
		expect(poster(manyTeams(3)).height).toBeGreaterThan(poster(manyTeams(2)).height);
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
