import { fireEvent, screen, within } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { badgeCollection } from '$lib/badges';
import BadgeSheet from './BadgeSheet.svelte';

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
		expect(spoken(status)).toBe('Badge earned badge earned 2 times');
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
		expect(detail).toHaveTextContent(/^with Léa Martin$/);
		expect(within(detail).getByRole('link', { name: 'Léa Martin' })).toHaveAttribute('href', '/players/12');
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
});
