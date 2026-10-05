import { fireEvent, screen, waitFor } from '@testing-library/svelte';
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
	vi.mocked(download).mockReset();
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
		// the photo is loaded: without one in the map the avatar falls back to initials
		vi.mocked(loadImages).mockResolvedValueOnce(new Map([['/media/avatars/11-7c3e9a1f5b2d-sm.webp', {}]]));
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
