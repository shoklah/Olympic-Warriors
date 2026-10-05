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
	vi.mocked(loadImages).mockReset();
	vi.mocked(loadImages).mockImplementation(async () => new Map());
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

	it('loads the logo at mount and the photos only once the switch is on', async () => {
		const PHOTO = '/media/avatars/11-7c3e9a1f5b2d-sm.webp';
		renderWith(Page, { data: data() });
		await waitFor(() => expect(screen.queryByText('Preparing the images…')).toBeNull());
		const requested = () => vi.mocked(loadImages).mock.calls.flatMap(([urls]) => urls);
		expect(requested()).toHaveLength(1); // the brand logo alone
		expect(requested()).not.toContain(PHOTO);

		await fireEvent.click(screen.getByLabelText('Show photos'));

		await waitFor(() => expect(requested()).toContain(PHOTO));
	});

	it('loads a photo that appears in the data afterwards, once', async () => {
		localStorage.setItem('announce.photos', 'on');
		vi.mocked(loadImages).mockImplementation(async (urls) => new Map(urls.map((u) => [u, {}])));
		const { component } = renderWith(Page, { data: data() });
		await waitFor(() => expect(loadImages).toHaveBeenCalledTimes(2));
		const requested = () => vi.mocked(loadImages).mock.calls.flatMap(([urls]) => urls);

		const teams = structuredClone(summary.teams);
		teams[0].players[1].photo = '/media/avatars/12-new-sm.webp';
		component.$set({ data: data(teams) });

		await waitFor(() => expect(requested()).toContain('/media/avatars/12-new-sm.webp'));
		expect(requested().filter((u) => u === '/media/avatars/11-7c3e9a1f5b2d-sm.webp')).toHaveLength(1);
	});

	it('shows the photos, with the reminder, when the switch is turned on, and remembers it', async () => {
		// the photo is loaded: without one in the map the avatar falls back to initials
		vi.mocked(loadImages).mockImplementation(async (urls) => new Map(urls.filter((u) => u.includes('avatars')).map((u) => [u, {}])));
		renderWith(Page, { data: data() });
		await waitFor(() => expect(screen.queryByText('Preparing the images…')).toBeNull());

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

	it('disables the downloads while one is under way, so a double click downloads once', async () => {
		let release;
		vi.mocked(download).mockImplementation(() => {});
		const { toPng } = await import('$lib/announce/export.js');
		vi.mocked(toPng).mockImplementationOnce(() => new Promise((resolve) => (release = () => resolve(new Blob(['png'])))));
		renderWith(Page, { data: data() });
		await waitFor(() => expect(screen.queryByText('Preparing the images…')).toBeNull());
		const button = screen.getByRole('button', { name: 'Download the poster' });

		await fireEvent.click(button);
		await fireEvent.click(button);
		expect(button).toHaveAttribute('aria-disabled', 'true');
		expect(screen.getByRole('button', { name: 'Download everything (ZIP)' })).toHaveAttribute('aria-disabled', 'true');
		release();

		await waitFor(() => expect(download).toHaveBeenCalledTimes(1));
		await waitFor(() => expect(button).not.toHaveAttribute('aria-disabled'));
	});

	it('keeps the downloads disabled while photos load, then enables them', async () => {
		localStorage.setItem('announce.photos', 'on');
		let resolve;
		vi.mocked(loadImages).mockImplementation((urls) =>
			urls.length === 1 && urls[0].includes('logo') ? Promise.resolve(new Map()) : new Promise((r) => (resolve = r))
		);
		renderWith(Page, { data: data() });

		await waitFor(() => expect(resolve).toBeDefined());
		expect(screen.getByRole('button', { name: 'Download the poster' })).toBeDisabled();
		expect(screen.getByRole('status')).toHaveTextContent('Preparing the images…');
		resolve(new Map());

		await waitFor(() => expect(screen.getByRole('button', { name: 'Download the poster' })).not.toBeDisabled());
		expect(screen.queryByRole('status')).toBeNull();
	});

	it('asks again for a photo that failed to load when the switch is toggled', async () => {
		const PHOTO = '/media/avatars/11-7c3e9a1f5b2d-sm.webp';
		localStorage.setItem('announce.photos', 'on');
		renderWith(Page, { data: data() });
		const requested = () => vi.mocked(loadImages).mock.calls.flatMap(([urls]) => urls).filter((u) => u === PHOTO);
		await waitFor(() => expect(requested()).toHaveLength(1));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Download the poster' })).not.toBeDisabled());

		await fireEvent.click(screen.getByLabelText('Show photos'));
		await fireEvent.click(screen.getByLabelText('Show photos'));

		await waitFor(() => expect(requested()).toHaveLength(2));
	});

	it('keeps focus on a button while a download is under way', async () => {
		let release;
		const { toPng } = await import('$lib/announce/export.js');
		vi.mocked(toPng).mockImplementationOnce(() => new Promise((resolve) => (release = () => resolve(new Blob(['png'])))));
		renderWith(Page, { data: data() });
		await waitFor(() => expect(screen.queryByText('Preparing the images…')).toBeNull());
		const button = screen.getByRole('button', { name: 'Download the poster' });
		button.focus();

		await fireEvent.click(button);

		expect(button).toHaveAttribute('aria-disabled', 'true');
		expect(button).not.toBeDisabled();
		expect(document.activeElement).toBe(button);
		release();
		await waitFor(() => expect(button).not.toHaveAttribute('aria-disabled'));
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
