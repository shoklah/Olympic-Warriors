import { describe, expect, it, vi } from 'vitest';
import { drawLayout } from './draw.js';
import { PALETTE } from './palette.js';

/** A 2D context that records what is drawn. */
function fakeContext() {
	const calls = [];
	const ctx = new Proxy(
		{ font: '', fillStyle: '', strokeStyle: '', lineWidth: 0, textAlign: '', textBaseline: '' },
		{
			get: (target, key) =>
				key in target
					? target[key]
					: (...args) => {
							// a real canvas throws on a negative radius
							if (key === 'arc' && args[2] < 0) throw new DOMException('negative radius', 'IndexSizeError');
							calls.push([key, ...args]);
						},
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

	it('draws the logo when loaded and skips it when not', () => {
		const items = [{ type: 'logo', x: 1, y: 2, w: 10, h: 12 }];
		const withImages = fakeContext();
		const without = fakeContext();

		drawLayout(withImages.ctx, layout(items), { images: new Map([['logo', image]]) });
		drawLayout(without.ctx, layout(items), { images: new Map() });

		expect(withImages.drawn('drawImage')).toHaveLength(1);
		expect(without.drawn('drawImage')).toHaveLength(0);
	});

	it('clips a player photo to a circle', () => {
		const { ctx, calls, drawn } = fakeContext();

		drawLayout(ctx, layout([avatarItem('/media/avatars/1-sm.webp')]), { images: new Map([['/media/avatars/1-sm.webp', image]]) });

		expect(drawn('clip')).toHaveLength(1);
		expect(drawn('drawImage')).toEqual([['drawImage', image, 10, 20, 60, 60]]);
		expect(calls).toContainEqual(['set', 'imageSmoothingQuality', 'high']);
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

	it('skips an avatar of size 0 or less instead of throwing', () => {
		const { ctx, drawn } = fakeContext();
		const items = [0, -5].map((size) => ({ ...avatarItem(null), size }));

		expect(() => drawLayout(ctx, layout(items), { images: new Map() })).not.toThrow();
		expect(drawn('arc')).toHaveLength(0);
	});

	it('does not throw on an empty layout', () => {
		expect(() => drawLayout(fakeContext().ctx, layout([]), { images: new Map() })).not.toThrow();
	});
});
