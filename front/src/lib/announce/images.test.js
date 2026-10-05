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

describe('timeouts', () => {
	afterEach(() => vi.useRealTimers());

	it('gives up on an image that never answers', async () => {
		vi.useFakeTimers();
		vi.stubGlobal('Image', class { set src(_) {} });

		const pending = loadImage('/media/hang.webp');
		await vi.advanceTimersByTimeAsync(10000);

		expect(await pending).toBeNull();
	});

	it('loadImages leaves out the hanging one and keeps the others', async () => {
		vi.useFakeTimers();
		vi.stubGlobal('Image', class extends FakeImage { set src(url) { if (!url.includes('hang')) super.src = url; } get src() { return super.src; } });

		const pending = loadImages(['/a.webp', '/hang.webp']);
		await vi.advanceTimersByTimeAsync(10000);

		expect([...(await pending).keys()]).toEqual(['/a.webp']);
	});

	it('fontsReady resolves after the timeout when a face never loads', async () => {
		vi.useFakeTimers();
		vi.stubGlobal('document', { fonts: { load: () => new Promise(() => {}) } });
		let done = false;

		const pending = fontsReady().then(() => (done = true));
		await vi.advanceTimersByTimeAsync(9999);
		expect(done).toBe(false);
		await vi.advanceTimersByTimeAsync(1);
		await pending;

		expect(done).toBe(true);
	});
});
