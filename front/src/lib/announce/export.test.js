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

		await downloadZip([{ name: 'a.png', blob: { arrayBuffer: async () => new TextEncoder().encode('hello').buffer } }], 'equipes-2029.zip');

		expect(link._d).toBe('equipes-2029.zip');
		expect(archive.type).toBe('application/zip');
		expect(archive.size).toBeGreaterThan(5 + 30 + 46 + 22);
		expect(click).toHaveBeenCalled();
	});
});
