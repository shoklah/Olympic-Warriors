import { fireEvent, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { profile, profileUnranked } from '$lib/fixtures/players.js';

// A mutable holder so each test can point $page.url at a different query string. Svelte's
// auto-subscription ($page) reads the store's current value synchronously at component
// init, so mutating this object before renderWith is enough: no reactive updates needed.
const pageState = vi.hoisted(() => ({ url: new URL('http://localhost/players/34') }));

// The collection's showcase forms use use:enhance; the photo editor still needs the real
// deserialize.
vi.mock('$app/forms', async (importOriginal) => ({
	...(await importOriginal()),
	enhance: () => ({ destroy() {} })
}));

vi.mock('$app/stores', () => ({
	page: {
		subscribe(run) {
			run(pageState);
			return () => {};
		}
	}
}));

const setSearch = (search = '') => {
	pageState.url = new URL(`http://localhost/players/34${search}`);
};

/** Whether `b` comes after `a` in document order. */
const follows = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

/** A slot button of the collection, in its family's section: the showcase above the tabs
    has buttons of the same names. */
const collectionSlot = (family, name) =>
	within(screen.getByRole('heading', { level: 3, name: new RegExp(`^${family}`) }).closest('section')).getByRole(
		'button',
		{ name }
	);

/** The root layout's `me` for Xavier Baby, whose profile the `profile` fixture is (id 34). */
const xavier = {
	id: 34,
	first_name: 'Xavier',
	last_name: 'Baby',
	photo: profile.photo,
	is_person: true,
	photo_locked: false
};

const camera = () => screen.queryByRole('button', { name: 'Change my photo' });

describe('player profile page', () => {
	beforeEach(() => {
		setSearch();
	});

	it('shows the name, the all-time position and the average rank figure', () => {
		renderWith(Page, { data: { profile } });

		expect(screen.getByRole('heading', { level: 1, name: 'Xavier Baby' })).toBeInTheDocument();
		const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
		expect(within(breadcrumb).getByRole('link', { name: 'Players' })).toHaveAttribute('href', '/players');
		const position = screen.getByTestId('position');
		expect(position).toHaveTextContent(/3\s*all-time/);
		expect(position).toHaveAttribute('href', '/players');
		expect(
			screen.getByRole('link', { name: '3 all-time · position on the players leaderboard' })
		).toBe(position);
		expect(screen.getByTestId('average-rank')).toHaveTextContent(/Average rank\s*2\.5/);
		expect(screen.queryByTestId('beaten')).toBeNull();
		expect(screen.queryByText(/%/)).toBeNull();
		expect(screen.queryByText('Teams beaten')).toBeNull();
		expect(screen.queryByText('Équipes battues')).toBeNull();
		expect(screen.getByText('4 editions · 2 counted')).toBeInTheDocument();
		expect(screen.queryByText('No ranked edition yet')).toBeNull();
	});

	it('shows the header avatar from the large photo, before the name', () => {
		renderWith(Page, { data: { profile } });

		const img = screen.getByTestId('portrait').querySelector('img');
		expect(img).toHaveAttribute('src', '/media/avatars/34-9b8a7c6d5e4f.webp');
		expect(img).toHaveAttribute('alt', '');
		// Above the fold: never lazy.
		expect(img).not.toHaveAttribute('loading');
		expect(follows(img, screen.getByRole('heading', { level: 1 }))).toBe(true);
	});

	it('shows the initials in the header without a photo, and without the photo key (an older API)', () => {
		const { unmount } = renderWith(Page, { data: { profile: profileUnranked } });
		expect(screen.getByTestId('portrait')).toHaveTextContent(/^AP$/);
		expect(screen.getByTestId('portrait').querySelector('img')).toBeNull();
		unmount();

		const { photo, showcase, ...older } = profile;
		renderWith(Page, { data: { profile: older } });
		expect(screen.getByTestId('portrait')).toHaveTextContent(/^XB$/);
		expect(screen.queryByRole('list', { name: 'Showcase' })).toBeNull();
	});

	it('shows the showcase under the name and above the tabs, its buttons named like the collection slots', () => {
		renderWith(Page, { data: { profile } });

		const list = screen.getByRole('list', { name: 'Showcase' });
		expect(within(list).getAllByRole('button').map((b) => b.getAttribute('aria-label'))).toEqual([
			'Clean sweep, badge earned 2 times',
			'Specialist, badge earned',
			'Comrades in arms, badge earned'
		]);
		expect(follows(screen.getByRole('heading', { level: 1 }), list)).toBe(true);
		expect(follows(list, screen.getByRole('navigation', { name: 'Profile sections' }))).toBe(true);
	});

	it("opens a showcase badge's sheet, the partner's avatar before the partner link", async () => {
		renderWith(Page, { data: { profile } });

		const button = screen.getByRole('button', { name: 'Comrades in arms, badge earned' });
		await fireEvent.click(button);
		const dialog = screen.getByRole('dialog', { name: 'Comrades in arms' });
		expect(dialog).toHaveTextContent('17% of players have it (8 of 47)');
		const link = within(dialog).getByRole('link', { name: 'Léa Martin' });
		const avatar = dialog.querySelector('img[src^="/media/"]');
		expect(avatar).toHaveAttribute('src', '/media/avatars/12-4f1c2a9b7e3d-sm.webp');
		expect(follows(avatar, link)).toBe(true);

		await fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }));
		expect(button).toHaveFocus();
	});

	it('keeps the showcase on the Badges tab', () => {
		setSearch('?tab=badges');
		renderWith(Page, { data: { profile } });

		expect(screen.getByRole('list', { name: 'Showcase' })).toBeInTheDocument();
		expect(screen.getAllByRole('button', { name: 'Comrades in arms, badge earned' })).toHaveLength(2);
	});

	it('shows no showcase line for a person without a badge', () => {
		renderWith(Page, { data: { profile: profileUnranked } });

		expect(screen.queryByRole('list', { name: 'Showcase' })).toBeNull();
		expect(screen.queryAllByRole('button')).toHaveLength(0);
	});

	it('lists every edition newest first: running, ranked, without a team', () => {
		renderWith(Page, { data: { profile } });

		const rows = screen.getAllByTestId('edition-row');
		expect(rows).toHaveLength(4);
		expect(rows[0]).toHaveTextContent(/2030\s*Les Aigles\s*In progress/);
		expect(rows[1]).toHaveTextContent(/2026\s*MxM\s*2\s*\/ 6/);
		expect(rows[2]).toHaveTextContent(/2024\s*No team recorded\s*—/);
		expect(rows[3]).toHaveTextContent(/2023\s*Bisons\s*3\s*\/ 8/);
		expect(within(rows[1]).getByRole('link', { name: 'MxM' })).toHaveAttribute('href', '/2026/teams/21');
		expect(within(rows[1]).getByRole('link', { name: '2026' })).toHaveAttribute('href', '/2026');
		expect(within(rows[2]).queryAllByRole('link').map((a) => a.textContent.trim())).toEqual(['2024']);
	});

	it('marks the links sitting among text: the edition year and team', () => {
		renderWith(Page, { data: { profile } });

		const row = screen.getAllByTestId('edition-row')[1];
		for (const link of within(row).getAllByRole('link')) expect(link).toHaveClass('quiet-link');
	});

	it('has a tabs nav named "Profile sections" with Profile and Badges links', () => {
		renderWith(Page, { data: { profile } });

		const nav = screen.getByRole('navigation', { name: 'Profile sections' });
		const profileLink = within(nav).getByRole('link', { name: 'Profile' });
		expect(profileLink).toHaveAttribute('href', '?');
		expect(profileLink).toHaveAttribute('data-sveltekit-keepfocus');
		const badgesLink = within(nav).getByRole('link', { name: 'Badges' });
		expect(badgesLink).toHaveAttribute('href', '?tab=badges');
		expect(badgesLink).toHaveAttribute('data-sveltekit-keepfocus');
	});

	it('defaults to the Profile tab: Profile current, Éditions shown, no badge slots', () => {
		renderWith(Page, { data: { profile } });

		expect(screen.getByRole('link', { name: 'Profile' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('link', { name: 'Badges' })).not.toHaveAttribute('aria-current');
		expect(screen.getByRole('heading', { level: 2, name: 'Editions' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /^Champion,/ })).toBeNull();
	});

	it('shows the Badges tab under ?tab=badges: current, the collection, no Éditions heading', () => {
		setSearch('?tab=badges');
		renderWith(Page, { data: { profile } });

		expect(screen.getByRole('link', { name: 'Badges' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('link', { name: 'Profile' })).not.toHaveAttribute('aria-current');
		expect(screen.getByText('4 badges out of 62')).toBeInTheDocument();
		expect(screen.getByRole('heading', { level: 3, name: /Podiums/ })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /^Champion,/ })).toBeInTheDocument();
		expect(screen.queryByRole('heading', { level: 2, name: 'Editions' })).toBeNull();
	});

	it("threads badge_stats down to the sheet's rarity line on the Badges tab", async () => {
		setSearch('?tab=badges');
		renderWith(Page, { data: { profile } });

		await fireEvent.click(collectionSlot('Teammates', /^Comrades in arms/));
		expect(screen.getByRole('dialog', { name: 'Comrades in arms' })).toHaveTextContent(
			'17% of players have it (8 of 47)'
		);
	});

	it('does not crash and shows no rarity line for a profile without badge_stats, like an older API', async () => {
		setSearch('?tab=badges');
		const { badge_stats, ...older } = profile;
		renderWith(Page, { data: { profile: older } });

		await fireEvent.click(collectionSlot('Teammates', /^Comrades in arms/));
		expect(screen.getByRole('dialog', { name: 'Comrades in arms' })).not.toHaveTextContent('of players');
	});

	it('shows the badge-count card linking to the Badges tab, its accessible name in shown-text order', () => {
		renderWith(Page, { data: { profile } });

		const card = screen.getByTestId('badge-count');
		expect(card).toHaveAttribute('href', '?tab=badges');
		expect(screen.getByRole('link', { name: 'Badges 4 / 62 see the collection' })).toBe(card);
	});

	it('shows 0/62 in the badge-count card for a profile with no badge', () => {
		renderWith(Page, { data: { profile: profileUnranked } });

		expect(screen.getByTestId('badge-count')).toHaveTextContent(/Badges\s*0\s*\/\s*62/);
	});

	it('does not crash for a payload without the badges key, like an older API', () => {
		const older = { ...profileUnranked };
		delete older.badges;
		renderWith(Page, { data: { profile: older } });

		expect(screen.getByRole('heading', { level: 1, name: 'Ana Petit' })).toBeInTheDocument();
		expect(screen.getByTestId('badge-count')).toHaveTextContent(/Badges\s*0\s*\/\s*62/);
	});

	it('dashes the figures and says so when nothing is counted yet', () => {
		renderWith(Page, { data: { profile: profileUnranked } });

		expect(screen.queryByTestId('position')).toBeNull();
		expect(screen.getByTestId('average-rank')).toHaveTextContent(/Average rank\s*—/);
		expect(screen.queryByTestId('beaten')).toBeNull();
		expect(screen.getByText('No ranked edition yet')).toBeInTheDocument();
		expect(screen.getByText('1 edition · 0 counted')).toBeInTheDocument();
	});

	it('speaks French under fr', () => {
		renderWith(Page, { data: { profile } }, 'fr');

		const breadcrumb = screen.getByRole('navigation', { name: "Fil d'Ariane" });
		expect(within(breadcrumb).getByRole('link', { name: 'Joueurs' })).toHaveAttribute('href', '/players');
		expect(screen.getByRole('heading', { level: 2, name: 'Éditions' })).toBeInTheDocument();
		expect(screen.getByTestId('position')).toHaveTextContent(/3\s*général/);
		expect(screen.getByTestId('average-rank')).toHaveTextContent(/Classement moyen\s*2,5/);
		expect(screen.queryByTestId('beaten')).toBeNull();
		expect(screen.getByText('4 éditions · 2 classées')).toBeInTheDocument();
		const rows = screen.getAllByTestId('edition-row');
		expect(rows[0]).toHaveTextContent(/2030\s*Les Aigles\s*En cours/);
		expect(rows[1]).toHaveTextContent(/2026\s*MxM\s*2\s*\/ 6/);
		expect(rows[2]).toHaveTextContent(/2024\s*Pas d'équipe/);
	});

	it('speaks French for the showcase', () => {
		renderWith(Page, { data: { profile } }, 'fr');

		const list = screen.getByRole('list', { name: 'Vitrine' });
		expect(within(list).getAllByRole('button').map((b) => b.getAttribute('aria-label'))).toEqual([
			'Razzia, badge obtenu 2 fois',
			'Spécialiste, badge obtenu',
			"Compagnons d'armes, badge obtenu"
		]);
	});

	it('says nothing is ranked yet, in French too', () => {
		renderWith(Page, { data: { profile: profileUnranked } }, 'fr');

		expect(screen.getByText("Aucune édition classée pour l'instant")).toBeInTheDocument();
	});

	it('speaks French for the tabs and the badge-count card', () => {
		renderWith(Page, { data: { profile } }, 'fr');

		const nav = screen.getByRole('navigation', { name: 'Sections du profil' });
		expect(within(nav).getByRole('link', { name: 'Profil' })).toBeInTheDocument();
		expect(within(nav).getByRole('link', { name: 'Badges' })).toHaveAttribute('href', '?tab=badges');
		expect(screen.getByRole('link', { name: 'Badges 4 / 62 voir la collection' })).toBe(
			screen.getByTestId('badge-count')
		);
	});

	it('shows the best-discipline card with the top discipline', () => {
		renderWith(Page, { data: { profile } });

		const card = screen.getByTestId('best-discipline');
		expect(card).toHaveTextContent(/Signature event\s*Relay/);
		expect(card.querySelector('img')).toHaveAttribute('src', expect.stringMatching(/relay\.svg$/));
		expect(card).not.toHaveTextContent('Crossfit');
		expect(card).not.toHaveTextContent('Darts');
	});

	it('lists every tied best discipline with the plural label and no +N', () => {
		const tied = {
			...profile,
			disciplines: [
				{ name: 'Relay', position: 1, places: [{ year: 2026, rank: 1 }] },
				{ name: 'Darts', position: 1, places: [{ year: 2026, rank: 1 }] }
			]
		};
		renderWith(Page, { data: { profile: tied } });

		const card = screen.getByTestId('best-discipline');
		expect(card).toHaveTextContent('Signature events');
		expect(card).toHaveTextContent('Relay');
		expect(card).toHaveTextContent('Darts');
		expect(card).not.toHaveTextContent('+');
	});

	it('dashes the best-discipline card and hides the section without any discipline place', () => {
		renderWith(Page, { data: { profile: profileUnranked } });

		expect(screen.getByTestId('best-discipline')).toHaveTextContent(/Signature event\s*—/);
		expect(screen.queryByRole('heading', { name: 'By discipline' })).toBeNull();
	});

	it('lists the places per discipline, best discipline first', () => {
		renderWith(Page, { data: { profile } });

		expect(screen.getByRole('heading', { name: 'By discipline' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('discipline-row');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveTextContent(/Relay\s*1\s*2026\s*2\s*2023/);
		expect(within(rows[0]).getByText('1st place in 2026, 2nd place in 2023')).toBeInTheDocument();

		const rankFour = within(rows[1]).getByText('4');
		expect(rankFour).not.toHaveClass('gold');
		expect(rankFour).not.toHaveClass('silver');
		expect(rankFour).not.toHaveClass('bronze');

		expect(rows[0].querySelector('.places')).toHaveAttribute('aria-hidden', 'true');
	});

	it("links each discipline row to the discipline's all-time table, on its newest edition", () => {
		renderWith(Page, { data: { profile } });

		const rows = screen.getAllByTestId('discipline-row');
		const relay = within(rows[0]).getByRole('link', { name: 'Relay 1st place in 2026, 2nd place in 2023' });
		expect(relay).toHaveAttribute('href', '/2026/disciplines/10?tab=all-time');
		expect(within(rows[2]).getByRole('link')).toHaveAttribute('href', '/2026/disciplines/12?tab=all-time');
	});

	it('keeps a discipline row plain without a latest place from the server', () => {
		const older = { ...profile, disciplines: profile.disciplines.map(({ latest, ...d }) => d) };
		renderWith(Page, { data: { profile: older } });

		const rows = screen.getAllByTestId('discipline-row');
		expect(rows[0]).toHaveTextContent(/Relay\s*1\s*2026\s*2\s*2023/);
		expect(within(rows[0]).queryByRole('link')).toBeNull();
	});

	it('gives the best-discipline icons an empty alt (decorative)', () => {
		renderWith(Page, { data: { profile } });

		const card = screen.getByTestId('best-discipline');
		const imgs = card.querySelectorAll('img');
		expect(imgs.length).toBeGreaterThan(0);
		imgs.forEach((img) => expect(img).toHaveAttribute('alt', ''));
	});

	// Class assertions on purpose here: colour (not text shape) is what's under test.
	it('colours the top three discipline-row ranks gold, silver and bronze', () => {
		renderWith(Page, { data: { profile } });

		const rows = screen.getAllByTestId('discipline-row');
		const relayRanks = rows[0].querySelectorAll('.place-rank');
		expect(relayRanks[0]).toHaveTextContent('1');
		expect(relayRanks[0]).toHaveClass('gold');
		expect(relayRanks[1]).toHaveTextContent('2');
		expect(relayRanks[1]).toHaveClass('silver');

		const dartsRank = rows[2].querySelector('.place-rank');
		expect(dartsRank).toHaveTextContent('3');
		expect(dartsRank).toHaveClass('bronze');
	});

	it('renders every place of a discipline even with many of them', () => {
		const manyPlaces = {
			...profile,
			disciplines: [
				{
					name: 'Relay',
					position: 1,
					places: Array.from({ length: 6 }, (_, i) => ({ year: 2026 - i, rank: i + 1 }))
				}
			]
		};
		renderWith(Page, { data: { profile: manyPlaces } });

		const row = screen.getByTestId('discipline-row');
		const ranks = row.querySelectorAll('.place-rank');
		expect(ranks).toHaveLength(6);
		expect(Array.from(ranks).map((el) => el.textContent)).toEqual(['1', '2', '3', '4', '5', '6']);
		expect(row.querySelectorAll('.place-year')).toHaveLength(6);
	});

	it('gives the best-discipline "+N" a spoken context', () => {
		const tied = {
			...profile,
			disciplines: ['Relay', 'Darts', 'Crossfit', 'Petanque'].map((name) => ({
				name,
				position: 1,
				places: [{ year: 2026, rank: 1 }]
			}))
		};
		renderWith(Page, { data: { profile: tied } });

		const card = screen.getByTestId('best-discipline');
		const more = within(card).getByText('+1');
		expect(more).toHaveAttribute('aria-hidden', 'true');
		expect(within(card).getByText('and 1 more discipline')).toBeInTheDocument();
	});

	it('speaks French for the best-discipline card and the by-discipline section', () => {
		renderWith(Page, { data: { profile } }, 'fr');

		const card = screen.getByTestId('best-discipline');
		expect(card).toHaveTextContent(/Épreuve fétiche\s*Relais/);
		expect(screen.getByRole('heading', { name: 'Par épreuve' })).toBeInTheDocument();
		const rows = screen.getAllByTestId('discipline-row');
		expect(rows[0]).toHaveTextContent(/Relais\s*1\s*2026\s*2\s*2023/);
		expect(within(rows[0]).getByText('1re place en 2026, 2e place en 2023')).toBeInTheDocument();
	});

	it('breaks a tie by the French displayed name, not the server database-name order', () => {
		const tied = {
			...profile,
			disciplines: ['Dodgeball', 'Blindtest', 'Hide and Seek', 'Petanque'].map((name) => ({
				name,
				position: 1,
				places: [{ year: 2026, rank: 1 }]
			}))
		};
		renderWith(Page, { data: { profile: tied } }, 'fr');

		const card = screen.getByTestId('best-discipline');
		const shown = Array.from(card.querySelectorAll('.best')).map((el) => el.textContent);
		expect(shown).toEqual(['Balle au prisonnier', 'Blindtest', 'Cache-cache']);
		expect(card).not.toHaveTextContent('Pétanque');
		expect(within(card).getByText('+1')).toBeInTheDocument();
	});

	describe('owner view: the photo', () => {
		afterEach(() => {
			document.body.style.overflow = '';
		});

		it('gives the owner a camera button on the header avatar, opening the photo editor', async () => {
			renderWith(Page, { data: { profile, me: xavier } });

			const button = within(screen.getByTestId('portrait')).getByRole('button', { name: 'Change my photo' });
			expect(button).toHaveAttribute('aria-haspopup', 'dialog');
			await fireEvent.click(button);
			const dialog = screen.getByRole('dialog', { name: 'My photo' });
			expect(dialog).toHaveTextContent('Your photo will be publicly visible on the site.');
			expect(within(dialog).getByRole('button', { name: 'Delete my photo' })).toBeInTheDocument();
			expect(within(dialog).getByLabelText('Choose a photo')).toBeInTheDocument();

			await fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
			expect(screen.queryByRole('dialog')).toBeNull();
			expect(button).toHaveFocus();
		});

		it('shows no camera to a visitor, or to someone logged in on another profile', () => {
			const { unmount } = renderWith(Page, { data: { profile, me: null } });
			expect(camera()).toBeNull();
			unmount();

			renderWith(Page, { data: { profile, me: { ...xavier, id: 12 } } });
			expect(camera()).toBeNull();
			expect(screen.queryByRole('dialog')).toBeNull();
		});

		it("offers no delete button in the editor of an owner without a photo", async () => {
			renderWith(Page, { data: { profile: { ...profileUnranked, id: 34 }, me: { ...xavier, photo: null } } });

			await fireEvent.click(camera());
			expect(screen.queryByRole('button', { name: 'Delete my photo' })).toBeNull();
		});

		it('opens the locked editor when an organiser turned uploads off', async () => {
			renderWith(Page, { data: { profile, me: { ...xavier, photo_locked: true } } });

			await fireEvent.click(camera());
			const dialog = screen.getByRole('dialog', { name: 'My photo' });
			expect(dialog).toHaveTextContent('Photo uploads have been turned off by an organiser');
			expect(within(dialog).queryByLabelText('Choose a photo')).toBeNull();
			expect(within(dialog).getByRole('button', { name: 'Delete my photo' })).toBeInTheDocument();
		});

		it('follows `data` from one profile to the next, the page staying mounted', async () => {
			const { component } = renderWith(Page, { data: { profile, me: xavier } });
			expect(camera()).toBeInTheDocument();

			await component.$set({ data: { profile: profileUnranked, me: xavier } });
			expect(camera()).toBeNull();
			await component.$set({ data: { profile, me: xavier } });
			expect(camera()).toBeInTheDocument();
			// Logged out in another tab: the next load carries no `me`.
			await component.$set({ data: { profile, me: null } });
			expect(camera()).toBeNull();
		});

		it("closes the editor on the way to someone else's profile, and does not reopen it", async () => {
			const { component } = renderWith(Page, { data: { profile, me: xavier } });
			await fireEvent.click(camera());
			expect(screen.getByRole('dialog', { name: 'My photo' })).toBeInTheDocument();

			await component.$set({ data: { profile: profileUnranked, me: xavier } });
			expect(screen.queryByRole('dialog')).toBeNull();
			await component.$set({ data: { profile, me: xavier } });
			expect(screen.queryByRole('dialog')).toBeNull();
		});

		it('speaks French for the camera and the editor', async () => {
			renderWith(Page, { data: { profile, me: xavier } }, 'fr');

			await fireEvent.click(screen.getByRole('button', { name: 'Changer ma photo' }));
			const dialog = screen.getByRole('dialog', { name: 'Ma photo' });
			expect(dialog).toHaveTextContent('Votre photo sera visible publiquement sur le site.');
			expect(within(dialog).getByRole('button', { name: 'Supprimer ma photo' })).toBeInTheDocument();
			expect(within(dialog).getByLabelText('Choisir une photo')).toBeInTheDocument();
		});
	});

	describe('owner view: the showcase', () => {
		const choose = () => screen.queryByRole('button', { name: 'Choose my showcase' });
		const hint = () => screen.queryByText('Automatic: your rarest badges');
		/** Xavier's profile with the showcase he pinned: comrades first, then specialist. */
		const pinnedProfile = {
			...profile,
			showcase: {
				auto: false,
				badges: [
					{ code: 'comrades', tier: 0, discipline: null },
					{ code: 'specialist', tier: 1, discipline: 'Relay' }
				]
			}
		};

		it('gives the owner « Choose my showcase » on the Badges tab, and the hint under an automatic showcase', () => {
			setSearch('?tab=badges');
			renderWith(Page, { data: { profile, me: xavier } });

			expect(choose()).toBeInTheDocument();
			const list = screen.getByRole('list', { name: 'Showcase' });
			expect(follows(list, hint())).toBe(true);
			expect(follows(hint(), screen.getByRole('navigation', { name: 'Profile sections' }))).toBe(true);
		});

		it('keeps the hint on the Profile tab, where the collection and its button are not', () => {
			renderWith(Page, { data: { profile, me: xavier } });

			expect(hint()).toBeInTheDocument();
			expect(choose()).toBeNull();
		});

		it('shows neither to a visitor, or to someone logged in on another profile', () => {
			setSearch('?tab=badges');
			const { unmount } = renderWith(Page, { data: { profile, me: null } });
			expect(choose()).toBeNull();
			expect(hint()).toBeNull();
			unmount();

			renderWith(Page, { data: { profile, me: { ...xavier, id: 12 } } });
			expect(choose()).toBeNull();
			expect(hint()).toBeNull();
		});

		it('drops the hint over pins, and starts the selection from them', async () => {
			setSearch('?tab=badges');
			renderWith(Page, { data: { profile: pinnedProfile, me: xavier } });
			expect(hint()).toBeNull();

			await fireEvent.click(choose());
			expect(collectionSlot('Teammates', /^Comrades in arms/)).toHaveAttribute('aria-pressed', 'true');
			expect(collectionSlot('Disciplines', /^Specialist/)).toHaveAttribute('aria-pressed', 'true');
			expect(collectionSlot('Loyalty', /^Veteran/)).toHaveAttribute('aria-pressed', 'false');
			expect(screen.getByRole('button', { name: 'Back to automatic' })).toBeInTheDocument();
		});

		it('offers nothing to choose, and no hint, to an owner without a badge', () => {
			setSearch('?tab=badges');
			renderWith(Page, { data: { profile: { ...profileUnranked, id: 34 }, me: xavier } });

			expect(choose()).toBeNull();
			expect(hint()).toBeNull();
		});

		it('speaks French for the button and the hint', () => {
			setSearch('?tab=badges');
			renderWith(Page, { data: { profile, me: xavier } }, 'fr');

			expect(screen.getByRole('button', { name: 'Choisir ma vitrine' })).toBeInTheDocument();
			expect(screen.getByText('Automatique : vos badges les plus rares')).toBeInTheDocument();
		});
	});
});
