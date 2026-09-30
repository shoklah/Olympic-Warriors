import { fireEvent, screen, within } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { badgeCollection } from '$lib/badges';
import BadgeSheet from './BadgeSheet.svelte';

/** Whether `b` comes after `a` in document order. */
const follows = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

/** The slot badgeCollection would build for `code`, from a handful of raw badge entries. */
const slotFor = (code, badges) =>
	badgeCollection(badges)
		.families.flatMap((f) => f.slots)
		.find((s) => s.code === code);

afterEach(() => {
	document.body.style.overflow = '';
});

describe('BadgeSheet', () => {
	it('shows the medallion, the name as the title, the status and the rule', () => {
		const badges = [{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null }];
		renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true });

		const dialog = screen.getByRole('dialog', { name: 'Veteran' });
		expect(dialog).toHaveTextContent('Badge earned');
		expect(dialog).toHaveTextContent('Play 3, 5, then 10 editions');
		expect(dialog).toHaveTextContent('Tier 1');
		expect(dialog).toHaveTextContent('Next tier: 5 editions');
	});

	it('shows each entry\'s years with no count: the status line says that once, on its own', () => {
		const badges = [{ code: 'clean-sweep', tier: 0, years: [2023, 2026], discipline: null, partner: null }];
		renderWith(BadgeSheet, { slot: slotFor('clean-sweep', badges), open: true });

		const dialog = screen.getByRole('dialog', { name: 'Clean sweep' });
		expect(dialog).toHaveTextContent('Badge earned · ×2');
		const detail = screen.getByTestId('badge-sheet-detail');
		expect(detail).not.toHaveTextContent('×2');
		expect(detail.textContent.replace(/\s+/g, ' ').trim()).toBe('2023 · 2026');
	});

	it("hides the status line's ×N from assistive tech and gives it a spoken count instead", () => {
		const badges = [{ code: 'clean-sweep', tier: 0, years: [2023, 2026], discipline: null, partner: null }];
		const { container } = renderWith(BadgeSheet, { slot: slotFor('clean-sweep', badges), open: true });

		const status = container.querySelector('.status');
		expect(status).toHaveTextContent('Badge earned · ×2');
		const spoken = (el) => {
			const copy = el.cloneNode(true);
			copy.querySelectorAll('[aria-hidden="true"]').forEach((node) => node.remove());
			return copy.textContent.replace(/\s+/g, ' ').trim();
		};
		expect(spoken(status)).toBe('Badge earned 2 times');
	});

	it('hides the detail separators from assistive tech, keeping the words apart', () => {
		const badges = [{ code: 'clean-sweep', tier: 0, years: [2023, 2026], discipline: null, partner: null }];
		renderWith(BadgeSheet, { slot: slotFor('clean-sweep', badges), open: true });

		const detail = screen.getByTestId('badge-sheet-detail');
		const copy = detail.cloneNode(true);
		copy.querySelectorAll('[aria-hidden="true"]').forEach((node) => node.remove());
		expect(copy.textContent.replace(/\s+/g, ' ').trim()).toBe('2023 2026');
	});

	it("shows a specialist entry's discipline before the tier and the year", () => {
		const badges = [{ code: 'specialist', tier: 1, years: [2026], discipline: 'Rugby', partner: null }];
		renderWith(BadgeSheet, { slot: slotFor('specialist', badges), open: true });

		const detail = screen.getByTestId('badge-sheet-detail');
		expect(detail.textContent.replace(/\s+/g, ' ').trim()).toBe('Rugby · Tier 1 · 2026');
	});

	it('shows the partner link first, with no trailing separator, when the entry has no year', () => {
		const lea = { id: 12, first_name: 'Léa', last_name: 'Martin' };
		const badges = [{ code: 'comrades', tier: 0, years: [], discipline: null, partner: lea }];
		renderWith(BadgeSheet, { slot: slotFor('comrades', badges), open: true });

		const detail = screen.getByTestId('badge-sheet-detail');
		// LM: the partner's avatar without a photo, aria-hidden (the link is named Léa Martin).
		expect(detail).toHaveTextContent(/^with\s*LM\s*Léa Martin$/);
		expect(within(detail).getByRole('link', { name: 'Léa Martin' })).toHaveAttribute('href', '/players/12');
		// Links sitting among text carry quiet-link (underlined on hover and focus, #92).
		expect(within(detail).getByRole('link', { name: 'Léa Martin' })).toHaveClass('quiet-link');
	});

	it("draws the partner's small photo before the partner link", () => {
		const lea = { id: 12, first_name: 'Léa', last_name: 'Martin', photo: '/media/avatars/12-4f1c2a9b7e3d-sm.webp' };
		const badges = [{ code: 'comrades', tier: 0, years: [2026], discipline: null, partner: lea }];
		renderWith(BadgeSheet, { slot: slotFor('comrades', badges), open: true });

		const detail = screen.getByTestId('badge-sheet-detail');
		const photo = detail.querySelector('img');
		expect(photo).toHaveAttribute('src', '/media/avatars/12-4f1c2a9b7e3d-sm.webp');
		expect(photo).toHaveAttribute('alt', '');
		expect(photo.closest('[aria-hidden="true"]')).not.toBeNull();
		const link = within(detail).getByRole('link', { name: 'Léa Martin' });
		expect(photo.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		expect(link.contains(photo)).toBe(false);
		expect(detail.textContent.replace(/\s+/g, ' ').trim()).toBe('with Léa Martin · 2026');
	});

	it('renders no detail line for an entry with nothing to show', () => {
		const badges = [{ code: 'champion', tier: 0, years: [], discipline: null, partner: null }];
		renderWith(BadgeSheet, { slot: slotFor('champion', badges), open: true });

		expect(screen.queryByTestId('badge-sheet-detail')).toBeNull();
		const dialog = screen.getByRole('dialog', { name: 'Champion' });
		expect(dialog).toHaveTextContent('Badge earned');
		expect(dialog).toHaveTextContent('Win an edition');
		expect(dialog).not.toHaveTextContent('×');
	});

	it('shows the first-tier goal of a locked tiered slot', () => {
		renderWith(BadgeSheet, { slot: slotFor('networker', []), open: true });
		const dialog = screen.getByRole('dialog', { name: 'Networker' });
		expect(dialog).toHaveTextContent('Badge locked');
		expect(dialog).toHaveTextContent('First tier: 5 teammates');
	});

	it('shows nothing extra for a locked untiered slot', () => {
		renderWith(BadgeSheet, { slot: slotFor('wooden-spoon', []), open: true });
		const dialog = screen.getByRole('dialog', { name: 'Wooden spoon' });
		expect(dialog).toHaveTextContent('Badge locked');
		expect(dialog).not.toHaveTextContent('tier');
	});

	it('shows "Top tier" instead of a next goal at tier 3', () => {
		const badges = [{ code: 'veteran', tier: 3, years: [2020, 2022, 2027], discipline: null, partner: null }];
		renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true });
		expect(screen.getByRole('dialog', { name: 'Veteran' })).toHaveTextContent('Top tier');
	});

	it('closes on Escape, the backdrop and the close button', async () => {
		const badges = [{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null }];
		const { component } = renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true });
		const closed = vi.fn();
		component.$on('close', closed);

		await fireEvent.keyDown(window, { key: 'Escape' });
		await fireEvent.click(screen.getByTestId('backdrop'));
		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));
		expect(closed).toHaveBeenCalledTimes(3);
	});

	it('traps Tab focus inside the sheet, wrapping both ways', async () => {
		const lea = { id: 12, first_name: 'Léa', last_name: 'Martin' };
		const badges = [{ code: 'comrades', tier: 0, years: [2026], discipline: null, partner: lea }];
		renderWith(BadgeSheet, { slot: slotFor('comrades', badges), open: true });
		// Let the sheet's own opening focus (like ScoreSheet's) settle first, so it doesn't
		// steal focus back after the manual moves below.
		await new Promise((resolve) => setTimeout(resolve, 0));

		const link = screen.getByRole('link', { name: 'Léa Martin' });
		const closeBtn = screen.getByRole('button', { name: 'Close' });

		closeBtn.focus();
		await fireEvent.keyDown(window, { key: 'Tab' });
		expect(link).toHaveFocus();

		link.focus();
		await fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
		expect(closeBtn).toHaveFocus();
	});

	it('wraps Shift+Tab to the last focusable when the sheet itself has focus', async () => {
		const lea = { id: 12, first_name: 'Léa', last_name: 'Martin' };
		const badges = [{ code: 'comrades', tier: 0, years: [2026], discipline: null, partner: lea }];
		renderWith(BadgeSheet, { slot: slotFor('comrades', badges), open: true });
		// The opening focus lands on the sheet itself (see ScoreSheet's own pattern).
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(screen.getByRole('dialog')).toHaveFocus();

		const closeBtn = screen.getByRole('button', { name: 'Close' });
		await fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
		expect(closeBtn).toHaveFocus();
	});

	it('pulls focus back inside on Tab when focus has landed outside the sheet', async () => {
		const outside = document.createElement('button');
		outside.textContent = 'Outside';
		document.body.appendChild(outside);
		const badges = [{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null }];
		renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true });
		await new Promise((resolve) => setTimeout(resolve, 0));

		outside.focus();
		expect(outside).toHaveFocus();
		const closeBtn = screen.getByRole('button', { name: 'Close' });
		await fireEvent.keyDown(window, { key: 'Tab' });
		expect(closeBtn).toHaveFocus();

		outside.remove();
	});

	it('locks the page scroll while open and restores it when it closes', async () => {
		document.body.style.overflow = '';
		const badges = [{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null }];
		const { component } = renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true });
		expect(document.body.style.overflow).toBe('hidden');

		component.$set({ open: false });
		await tick();
		expect(document.body.style.overflow).toBe('');
	});

	it('restores the page scroll if the sheet is destroyed while still open', () => {
		document.body.style.overflow = '';
		const badges = [{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null }];
		const { unmount } = renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true });
		expect(document.body.style.overflow).toBe('hidden');

		unmount();
		expect(document.body.style.overflow).toBe('');
	});

	it('renders nothing when closed', () => {
		const badges = [{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null }];
		const { container } = renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: false });
		expect(container.querySelector('[role="dialog"]')).toBeNull();
	});

	it('speaks French: the rule, the wording and "d\'affilée" for ever-present', () => {
		const badges = [{ code: 'ever-present', tier: 1, years: [2026], discipline: null, partner: null }];
		renderWith(BadgeSheet, { slot: slotFor('ever-present', badges), open: true }, 'fr');
		const dialog = screen.getByRole('dialog', { name: 'Pénélope' });
		expect(dialog).toHaveTextContent('Badge obtenu');
		expect(dialog).toHaveTextContent("Prochain niveau : 6 éditions d'affilée");
	});

	describe('progress', () => {
		/** A progress entry of /profile/<id>/, as the badge refresh stores it. */
		const progressEntry = (code, extra = {}) => ({
			code, value: 0, best: null, reachable: true, discipline: null, partner: null, year: null, ...extra
		});
		const hugo = { id: 7, first_name: 'Hugo', last_name: 'Maurinier', photo: null };

		/** An element's text as seen: the visually hidden copies left out, the spaces squeezed. */
		const seen = (el) => {
			const copy = el.cloneNode(true);
			copy.querySelectorAll('.visually-hidden').forEach((node) => node.remove());
			return copy.textContent.replace(/\s+/g, ' ').trim();
		};
		/** An element's text as read out: the aria-hidden parts left out. */
		const spoken = (el) => {
			const copy = el.cloneNode(true);
			copy.querySelectorAll('[aria-hidden="true"]').forEach((node) => node.remove());
			return copy.textContent.replace(/\s+/g, ' ').trim();
		};
		const count = () => screen.getByTestId('badge-progress-count');
		const ticks = () => screen.getAllByTestId('badge-progress-tick');
		const lit = () => ticks().map((tick) => tick.dataset.lit === 'true');
		const fill = () => screen.getByTestId('badge-progress-fill');

		it('shows the count toward the next tier under the status line, above the rule', () => {
			const badges = [{ code: 'veteran', tier: 2, years: [2024, 2026], discipline: null, partner: null }];
			const progress = [progressEntry('legend', { value: 1 }), progressEntry('veteran', { value: 7 })];
			const { container } = renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true, progress });

			expect(seen(count())).toBe('7 / 10 editions');
			const block = screen.getByTestId('badge-progress');
			expect(follows(container.querySelector('.status'), block)).toBe(true);
			expect(follows(block, screen.getByText('Play 3, 5, then 10 editions'))).toBe(true);
		});

		it('speaks the fraction in words, the seen one hidden from assistive tech', () => {
			const badges = [{ code: 'veteran', tier: 2, years: [2024, 2026], discipline: null, partner: null }];
			const progress = [progressEntry('veteran', { value: 7 })];
			renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true, progress });

			expect(seen(count())).toBe('7 / 10 editions');
			expect(spoken(count())).toBe('7 of 10 editions');
		});

		it('hides the track, lights its ticks by its own count and fills it in the metal of the highest one lit', () => {
			const badges = [{ code: 'veteran', tier: 2, years: [2024, 2026], discipline: null, partner: null }];
			const progress = [progressEntry('veteran', { value: 7 })];
			renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true, progress });

			const track = screen.getByTestId('badge-progress-track');
			expect(track).toHaveAttribute('aria-hidden', 'true');
			expect(lit()).toEqual([true, true, false]);
			expect(ticks().map((tick) => tick.dataset.metal)).toEqual(['bronze', 'silver', 'gold']);
			expect(ticks().map((tick) => tick.style.getPropertyValue('--at'))).toEqual(['0.3', '0.5', '1']);
			expect(fill().dataset.metal).toBe('silver');
			expect(fill().style.getPropertyValue('--share')).toBe('0.7');
		});

		it("lights only a specialist bar's own ticks, whatever the other disciplines hold, and names its discipline", () => {
			const badges = [
				{ code: 'specialist', tier: 3, years: [2026], discipline: 'Relay', partner: null },
				{ code: 'specialist', tier: 1, years: [2025], discipline: 'Darts', partner: null }
			];
			const progress = [progressEntry('specialist', { value: 2, discipline: 'Darts' })];
			renderWith(BadgeSheet, { slot: slotFor('specialist', badges), open: true, progress });

			expect(lit()).toEqual([true, false, false]);
			expect(fill().dataset.metal).toBe('bronze');
			expect(seen(count())).toBe('2 / 3 wins · Darts');
			expect(spoken(count())).toBe('2 of 3 wins Darts');
		});

		it("keeps specialist's next goal on its entry lines: one per discipline, while the bar follows one", () => {
			const badges = [
				{ code: 'specialist', tier: 3, years: [2026], discipline: 'Relay', partner: null },
				{ code: 'specialist', tier: 1, years: [2025], discipline: 'Darts', partner: null }
			];
			const progress = [progressEntry('specialist', { value: 2, discipline: 'Darts' })];
			renderWith(BadgeSheet, { slot: slotFor('specialist', badges), open: true, progress });

			const dialog = screen.getByRole('dialog', { name: 'Specialist' });
			expect(dialog).toHaveTextContent('Next tier: 3 titles in the discipline');
			expect(dialog).toHaveTextContent('Top tier');
		});

		it('drops the next goal of an earned tiered badge, which the bar now says', () => {
			const badges = [{ code: 'veteran', tier: 2, years: [2024, 2026], discipline: null, partner: null }];
			const progress = [progressEntry('veteran', { value: 7 })];
			renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true, progress });

			const dialog = screen.getByRole('dialog', { name: 'Veteran' });
			expect(dialog).toHaveTextContent('Tier 2');
			expect(dialog).not.toHaveTextContent('Next tier');
		});

		it("replaces a locked tiered slot's first goal", () => {
			const progress = [progressEntry('networker', { value: 4 })];
			renderWith(BadgeSheet, { slot: slotFor('networker', []), open: true, progress });

			const dialog = screen.getByRole('dialog', { name: 'Networker' });
			expect(dialog).toHaveTextContent('Badge locked');
			expect(seen(count())).toBe('4 / 5 teammates');
			expect(dialog).not.toHaveTextContent('First tier');
			expect(lit()).toEqual([false, false, false]);
			expect(fill().dataset.metal).toBe('muted');
		});

		it("draws ever-present's short run below its best tier: no tick lit, the best run in a note", () => {
			const badges = [{ code: 'ever-present', tier: 2, years: [2022, 2024], discipline: null, partner: null }];
			const progress = [progressEntry('ever-present', { value: 1, best: 6 })];
			renderWith(BadgeSheet, { slot: slotFor('ever-present', badges), open: true, progress });

			expect(seen(count())).toBe('1 / 8 editions in a row');
			expect(lit()).toEqual([false, false, false]);
			expect(fill().dataset.metal).toBe('muted');
			expect(screen.getByRole('dialog', { name: 'Ever-present' })).toHaveTextContent('Best run: 6');
		});

		it('shows the top tier full: every tick lit, the fill gold, the count alone with "Top tier"', () => {
			const badges = [{ code: 'veteran', tier: 3, years: [2020, 2022, 2027], discipline: null, partner: null }];
			const progress = [progressEntry('veteran', { value: 12 })];
			renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true, progress });

			expect(seen(count())).toBe('12 editions · Top tier');
			expect(spoken(count())).toBe('12 editions Top tier');
			expect(lit()).toEqual([true, true, true]);
			expect(fill().dataset.metal).toBe('gold');
			expect(fill().style.getPropertyValue('--share')).toBe('1');
			// "Top tier" once, on the count line: the entry line drops its own.
			expect(screen.getAllByText(/Top tier/)).toHaveLength(1);
		});

		it('shows ever-present full at the top tier by its best run, whatever the current one, with no note', () => {
			const badges = [{ code: 'ever-present', tier: 3, years: [2020, 2022, 2024], discipline: null, partner: null }];
			const progress = [progressEntry('ever-present', { value: 2, best: 9 })];
			renderWith(BadgeSheet, { slot: slotFor('ever-present', badges), open: true, progress });

			expect(seen(count())).toBe('9 editions in a row · Top tier');
			expect(lit()).toEqual([true, true, true]);
			expect(fill().dataset.metal).toBe('gold');
			expect(screen.getByRole('dialog', { name: 'Ever-present' })).not.toHaveTextContent('Best run');
		});

		it('names the discipline before "Top tier" when both are there', () => {
			const badges = [{ code: 'specialist', tier: 3, years: [2026], discipline: 'Relay', partner: null }];
			const progress = [progressEntry('specialist', { value: 4, discipline: 'Relay' })];
			renderWith(BadgeSheet, { slot: slotFor('specialist', badges), open: true, progress });

			expect(seen(count())).toBe('4 wins · Relay · Top tier');
		});

		it('draws a plain bar, with no tick, for a badge without tiers', () => {
			const progress = [progressEntry('legend', { value: 1 })];
			renderWith(BadgeSheet, { slot: slotFor('legend', []), open: true, progress });

			expect(seen(count())).toBe('1 / 3 editions won');
			expect(spoken(count())).toBe('1 of 3 editions won');
			expect(screen.queryAllByTestId('badge-progress-tick')).toHaveLength(0);
			expect(fill().dataset.metal).toBe('gold');
			expect(Number(fill().style.getPropertyValue('--share'))).toBeCloseTo(1 / 3);
		});

		it("notes a streak's best run under the count line when it beats the current run", () => {
			const progress = [progressEntry('podium-regular', { value: 1, best: 2 })];
			renderWith(BadgeSheet, { slot: slotFor('podium-regular', []), open: true, progress });

			expect(seen(count())).toBe('1 / 3 podiums in a row');
			const note = screen.getByText('Best run: 2');
			expect(follows(count(), note)).toBe(true);
		});

		it('leaves the note out when the current run is the best', () => {
			const progress = [progressEntry('back-to-back', { value: 1, best: 1 })];
			renderWith(BadgeSheet, { slot: slotFor('back-to-back', []), open: true, progress });

			expect(seen(count())).toBe('1 / 2 editions won in a row');
			expect(screen.getByRole('dialog', { name: 'Back-to-back' })).not.toHaveTextContent('Best run');
		});

		it("names comrades' closest partner, their link outside the hidden fraction", () => {
			const lea = { id: 12, first_name: 'Léa', last_name: 'Martin' };
			const badges = [{ code: 'comrades', tier: 0, years: [2026], discipline: null, partner: lea }];
			const progress = [progressEntry('comrades', { value: 2, partner: hugo })];
			renderWith(BadgeSheet, { slot: slotFor('comrades', badges), open: true, progress });

			// HM: the partner's avatar without a photo, aria-hidden like the entry line's.
			expect(seen(count())).toBe('2 / 3 editions together with HM Hugo Maurinier');
			expect(spoken(count())).toBe('2 of 3 editions together with Hugo Maurinier');
			const link = within(count()).getByRole('link', { name: 'Hugo Maurinier' });
			expect(link).toHaveAttribute('href', '/players/7');
			expect(link).toHaveClass('quiet-link');
			expect(link.closest('[aria-hidden="true"]')).toBeNull();
			expect(link.closest('.visually-hidden')).toBeNull();
		});

		it("draws the partner's small photo before their link", () => {
			const photo = '/media/avatars/7-1a2b3c4d5e6f-sm.webp';
			const progress = [progressEntry('comrades', { value: 1, partner: { ...hugo, photo } })];
			renderWith(BadgeSheet, { slot: slotFor('comrades', []), open: true, progress });

			const img = count().querySelector('img');
			expect(img).toHaveAttribute('src', photo);
			expect(img.closest('[aria-hidden="true"]')).not.toBeNull();
			expect(follows(img, within(count()).getByRole('link', { name: 'Hugo Maurinier' }))).toBe(true);
		});

		it("gives clean-sweep's best edition its year", () => {
			const progress = [progressEntry('clean-sweep', { value: 2, year: 2025 })];
			renderWith(BadgeSheet, { slot: slotFor('clean-sweep', []), open: true, progress });

			expect(seen(count())).toBe('2 / 3 disciplines won in 2025');
			expect(spoken(count())).toBe('2 of 3 disciplines won in 2025');
		});

		it('says a badge that can no longer be earned is out of reach, with no track', () => {
			const progress = [progressEntry('eternal-second', { value: null, reachable: false })];
			renderWith(BadgeSheet, { slot: slotFor('eternal-second', []), open: true, progress });

			const dialog = screen.getByRole('dialog', { name: 'Eternal second' });
			expect(dialog).toHaveTextContent('Out of reach: already won an edition');
			expect(screen.queryByTestId('badge-progress-track')).toBeNull();
			expect(screen.queryByTestId('badge-progress-count')).toBeNull();
		});

		it('says argonaut is out of reach for those who missed the first edition', () => {
			const progress = [progressEntry('argonaut', { value: null, reachable: false })];
			renderWith(BadgeSheet, { slot: slotFor('argonaut', []), open: true, progress });

			expect(screen.getByRole('dialog', { name: 'Argonaut' })).toHaveTextContent(
				'Out of reach: only for the players of the first edition'
			);
		});

		it("keeps today's lines without an entry for the slot's code", () => {
			const progress = [progressEntry('veteran', { value: 7 })];
			renderWith(BadgeSheet, { slot: slotFor('networker', []), open: true, progress });

			expect(screen.getByRole('dialog', { name: 'Networker' })).toHaveTextContent('First tier: 5 teammates');
			expect(screen.queryByTestId('badge-progress')).toBeNull();
		});

		it("keeps an earned tiered badge's next goal without an entry", () => {
			const badges = [{ code: 'veteran', tier: 1, years: [2026], discipline: null, partner: null }];
			renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true, progress: [] });

			expect(screen.getByRole('dialog', { name: 'Veteran' })).toHaveTextContent('Next tier: 5 editions');
			expect(screen.queryByTestId('badge-progress')).toBeNull();
		});

		it('speaks French: the fraction, its words, the discipline, the partner and the out-of-reach line', () => {
			const badges = [{ code: 'specialist', tier: 1, years: [2025], discipline: 'Relay', partner: null }];
			const progress = [
				progressEntry('comrades', { value: 2, partner: hugo }),
				progressEntry('specialist', { value: 2, discipline: 'Relay' }),
				progressEntry('lucky-charm', { value: null, reachable: false })
			];
			const { unmount } = renderWith(
				BadgeSheet,
				{ slot: slotFor('specialist', badges), open: true, progress },
				'fr'
			);
			expect(seen(count())).toBe('2 / 3 victoires · Relais');
			expect(spoken(count())).toBe('2 sur 3 victoires Relais');
			unmount();

			const second = renderWith(BadgeSheet, { slot: slotFor('comrades', []), open: true, progress }, 'fr');
			expect(seen(count())).toBe('2 / 3 éditions ensemble avec HM Hugo Maurinier');
			second.unmount();

			renderWith(BadgeSheet, { slot: slotFor('lucky-charm', []), open: true, progress }, 'fr');
			expect(screen.getByRole('dialog', { name: 'Porte-bonheur' })).toHaveTextContent(
				'Plus atteignable : une des trois premières éditions classées hors du podium'
			);
		});

		it('speaks French at the top tier and for the best run', () => {
			const badges = [{ code: 'veteran', tier: 3, years: [2020, 2022, 2027], discipline: null, partner: null }];
			const progress = [
				progressEntry('veteran', { value: 12 }),
				progressEntry('dynasty', { value: 1, best: 3 })
			];
			const { unmount } = renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true, progress }, 'fr');
			expect(seen(count())).toBe('12 éditions · Niveau maximum');
			unmount();

			renderWith(BadgeSheet, { slot: slotFor('dynasty', []), open: true, progress }, 'fr');
			expect(seen(count())).toBe("1 / 4 éditions gagnées d'affilée");
			expect(screen.getByRole('dialog', { name: 'Dynastie' })).toHaveTextContent('Meilleure série : 3');
		});
	});

	describe('rarity', () => {
		it("shows an earned untiered badge's share of players", () => {
			const badges = [{ code: 'champion', tier: 0, years: [2026], discipline: null, partner: null }];
			const badgeStats = { players: 47, holders: { champion: 12 } };
			renderWith(BadgeSheet, { slot: slotFor('champion', badges), open: true, badgeStats });

			const dialog = screen.getByRole('dialog', { name: 'Champion' });
			expect(dialog).toHaveTextContent('26% of players have it (12 of 47)');
		});

		it('shows "Nobody has it yet" for a locked badge with 0 holders', () => {
			const badgeStats = { players: 47, holders: {} };
			renderWith(BadgeSheet, { slot: slotFor('wooden-spoon', []), open: true, badgeStats });

			const dialog = screen.getByRole('dialog', { name: 'Wooden spoon' });
			expect(dialog).toHaveTextContent('Nobody has it yet');
		});

		it('shows the under-1% wording when holders round to 0%', () => {
			const badges = [{ code: 'mvp', tier: 0, years: [2026], discipline: null, partner: null }];
			const badgeStats = { players: 1000, holders: { mvp: 1 } };
			renderWith(BadgeSheet, { slot: slotFor('mvp', badges), open: true, badgeStats });

			expect(screen.getByRole('dialog', { name: 'MVP' })).toHaveTextContent('Less than 1% of players (1 of 1000)');
		});

		it("shows the badge line and a second line at the profile owner's tier for an earned tiered badge", () => {
			const badges = [{ code: 'veteran', tier: 2, years: [2024, 2026], discipline: null, partner: null }];
			const badgeStats = { players: 47, holders: { veteran: 20 }, tiers: { veteran: [20, 3, 1] } };
			renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true, badgeStats });

			const dialog = screen.getByRole('dialog', { name: 'Veteran' });
			expect(dialog).toHaveTextContent('43% of players have it (20 of 47)');
			expect(dialog).toHaveTextContent('6% at tier 2 or above (3 of 47)');
		});

		it('shows no second tier line for a locked tiered badge', () => {
			const badgeStats = { players: 47, holders: { networker: 10 }, tiers: { networker: [10, 4, 1] } };
			renderWith(BadgeSheet, { slot: slotFor('networker', []), open: true, badgeStats });

			const dialog = screen.getByRole('dialog', { name: 'Networker' });
			expect(dialog).toHaveTextContent('21% of players have it (10 of 47)');
			expect(dialog).not.toHaveTextContent('or above');
		});

		it('hides the tier line rather than say "0 of" when badge_stats has no holder at that tier', () => {
			// slot.medal.tier reads 2 from the earned entry below, but the stats say 0 people
			// (including the profile owner) hold at least tier 2 — a stale/inconsistent
			// badge_stats snapshot the sheet must not turn into "Less than 1% ... (0 of 47)".
			const badges = [{ code: 'veteran', tier: 2, years: [2024, 2026], discipline: null, partner: null }];
			const badgeStats = { players: 47, holders: { veteran: 20 }, tiers: { veteran: [20, 0, 0] } };
			renderWith(BadgeSheet, { slot: slotFor('veteran', badges), open: true, badgeStats });

			const dialog = screen.getByRole('dialog', { name: 'Veteran' });
			expect(dialog).toHaveTextContent('43% of players have it (20 of 47)');
			expect(dialog).not.toHaveTextContent('or above');
		});

		it('shows no rarity line at all without badge_stats', () => {
			const badges = [{ code: 'champion', tier: 0, years: [2026], discipline: null, partner: null }];
			renderWith(BadgeSheet, { slot: slotFor('champion', badges), open: true });

			const dialog = screen.getByRole('dialog', { name: 'Champion' });
			expect(dialog).not.toHaveTextContent('of players');
		});

		it('speaks French with a no-break space before the percent sign', () => {
			const badges = [{ code: 'champion', tier: 0, years: [2026], discipline: null, partner: null }];
			const badgeStats = { players: 47, holders: { champion: 12 } };
			renderWith(BadgeSheet, { slot: slotFor('champion', badges), open: true, badgeStats }, 'fr');

			const dialog = screen.getByRole('dialog', { name: 'Champion' });
			expect(dialog).toHaveTextContent("26 % des joueurs l'ont obtenu (12 sur 47)");
			expect(dialog.textContent).toContain('26 %');
		});
	});
});
