import { screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import StaffBar from './StaffBar.svelte';

vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }));

describe('StaffBar', () => {
	it('offers to reveal a hidden discipline and says what is missing', () => {
		renderWith(StaffBar, { disciplineId: 12, revealed: false, missing: '2 teams without a result' });

		expect(screen.getByText('Results hidden from the public')).toBeInTheDocument();
		expect(screen.getByText('2 teams without a result')).toBeInTheDocument();
		const form = screen.getByRole('button', { name: 'Reveal' }).closest('form');
		expect(form).toHaveAttribute('action', '?/reveal');
		expect(form.querySelector('input[name="discipline"]')).toHaveValue('12');
		expect(form.querySelector('input[name="reveal_score"]')).toHaveValue('true');
	});

	it('offers to hide a revealed one', () => {
		renderWith(StaffBar, { disciplineId: 12, revealed: true, missing: null });

		expect(screen.getByText('Results are public')).toBeInTheDocument();
		const form = screen.getByRole('button', { name: 'Hide' }).closest('form');
		expect(form.querySelector('input[name="reveal_score"]')).toHaveValue('false');
	});

	it('shows the error line and speaks French', () => {
		renderWith(StaffBar, { disciplineId: 12, revealed: false, missing: null, error: 'orga.error.failed' }, 'fr');
		expect(screen.getByText('Résultats masqués pour le public')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Dévoiler' })).toBeInTheDocument();
		expect(screen.getByRole('alert')).toHaveTextContent("Échec de l'enregistrement");
	});
});
