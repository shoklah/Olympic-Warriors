import { fireEvent, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import ScoreSheet from './ScoreSheet.svelte';

vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }));

afterEach(() => {
	vi.unstubAllGlobals();
	document.body.style.overflow = '';
});

const game = {
	id: 201,
	team1Id: 3,
	team1Name: 'Cerfs',
	team2Id: 2,
	team2Name: 'Bisons',
	refereeName: 'Aigles',
	isPlayed: false,
	score1: 0,
	score2: 0
};

describe('ScoreSheet', () => {
	it('renders both teams, the round and the referee, and posts the game id', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });

		const dialog = screen.getByRole('dialog', { name: 'Round 1 · ref: Aigles' });
		expect(dialog).toHaveTextContent(/Cerfs/);
		expect(dialog).toHaveTextContent(/Bisons/);
		const form = dialog.querySelector('form');
		expect(form).toHaveAttribute('action', '?/score');
		expect(form.querySelector('input[name="game"]')).toHaveValue('201');
	});

	it('steps the scores and never below zero', async () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });

		const minus1 = screen.getByRole('button', { name: 'One point less for Cerfs' });
		const plus1 = screen.getByRole('button', { name: 'One point more for Cerfs' });
		const score1 = screen.getByLabelText('Cerfs');
		await fireEvent.click(plus1);
		await fireEvent.click(plus1);
		expect(score1).toHaveValue(2);
		await fireEvent.click(minus1);
		await fireEvent.click(minus1);
		await fireEvent.click(minus1);
		expect(score1).toHaveValue(0);
	});

	it('starts the played switch on for an unplayed game', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		expect(screen.getByRole('checkbox', { name: 'Played' })).toBeChecked();
	});

	it('reflects the loaded score of a played game', () => {
		renderWith(ScoreSheet, { game: { ...game, isPlayed: true, score1: 12, score2: 9 }, roundNumber: 2, open: true });
		expect(screen.getByLabelText('Cerfs')).toHaveValue(12);
		expect(screen.getByLabelText('Bisons')).toHaveValue(9);
		expect(screen.getByRole('checkbox', { name: 'Played' })).toBeChecked();
	});

	it('closes on cancel, on Escape and on the backdrop', async () => {
		const { component } = renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		const closed = vi.fn();
		component.$on('close', closed);

		await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
		await fireEvent.keyDown(window, { key: 'Escape' });
		await fireEvent.click(screen.getByTestId('backdrop'));
		expect(closed).toHaveBeenCalledTimes(3);
	});

	it('focuses the sheet itself on a phone, so opening it does not pop the keyboard', async () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(screen.getByRole('dialog')).toHaveFocus();
	});

	it('focuses the first score field on desktop when it opens', async () => {
		vi.stubGlobal('matchMedia', () => ({ matches: true }));
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(screen.getByLabelText('Cerfs')).toHaveFocus();
	});

	// The same keyboard handling as BadgeSheet, through the shared `modal` action. The form's
	// hidden game input is no Tab stop, so the first minus button is the first one.
	it('traps Tab focus inside the sheet, wrapping both ways', async () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		// Let the opening focus settle first, so it doesn't steal focus back afterwards.
		await new Promise((resolve) => setTimeout(resolve, 0));

		const minus1 = screen.getByRole('button', { name: 'One point less for Cerfs' });
		const save = screen.getByRole('button', { name: 'Save' });

		save.focus();
		await fireEvent.keyDown(window, { key: 'Tab' });
		expect(minus1).toHaveFocus();

		await fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
		expect(save).toHaveFocus();
	});

	it('wraps Shift+Tab to Save when the sheet itself has focus, as it does on a phone', async () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(screen.getByRole('dialog')).toHaveFocus();

		await fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
		expect(screen.getByRole('button', { name: 'Save' })).toHaveFocus();
	});

	it('pulls focus back inside on Tab when focus has landed outside the sheet', async () => {
		const outside = document.createElement('button');
		outside.textContent = 'Outside';
		document.body.appendChild(outside);
		try {
			renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
			await new Promise((resolve) => setTimeout(resolve, 0));

			outside.focus();
			await fireEvent.keyDown(window, { key: 'Tab' });
			expect(screen.getByRole('button', { name: 'One point less for Cerfs' })).toHaveFocus();
		} finally {
			outside.remove();
		}
	});

	it('locks the page scroll while open and restores it when it closes', async () => {
		document.body.style.overflow = '';
		const { component } = renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		expect(document.body.style.overflow).toBe('hidden');

		component.$set({ open: false });
		await tick();
		expect(document.body.style.overflow).toBe('');
	});

	it('restores the page scroll if the sheet is destroyed while still open', () => {
		document.body.style.overflow = '';
		const { unmount } = renderWith(ScoreSheet, { game, roundNumber: 1, open: true });
		expect(document.body.style.overflow).toBe('hidden');

		unmount();
		expect(document.body.style.overflow).toBe('');
	});

	it('renders nothing when closed and shows the error line when given', () => {
		const { container } = renderWith(ScoreSheet, { game, roundNumber: 1, open: false });
		expect(container.querySelector('[role="dialog"]')).toBeNull();

		renderWith(ScoreSheet, { game, roundNumber: 1, open: true, error: 'orga.error.conflict' });
		expect(screen.getByRole('alert')).toHaveTextContent(
			'Not possible right now: round incomplete, already closed or past edition'
		);
	});

	it('speaks French under fr', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true }, 'fr');
		expect(screen.getByRole('dialog', { name: 'Tour 1 · arbitre : Aigles' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeInTheDocument();
		expect(screen.getByRole('checkbox', { name: 'Joué' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Un point de moins pour Cerfs' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Un point de plus pour Bisons' })).toBeInTheDocument();
	});

	it('words a failed save in French', () => {
		renderWith(ScoreSheet, { game, roundNumber: 1, open: true, error: 'orga.error.unauthorised' }, 'fr');
		expect(screen.getByRole('alert')).toHaveTextContent('Session expirée, reconnectez-vous');
	});
});
