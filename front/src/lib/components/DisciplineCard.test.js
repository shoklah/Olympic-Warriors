import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import DisciplineCard from './DisciplineCard.svelte';

const props = { href: '/2026/disciplines/10', discipline: 'Relay', name: 'Relay', subtitle: '2 rounds' };

describe('DisciplineCard', () => {
	it('is one link named after the discipline, its subtitle shown', () => {
		renderWith(DisciplineCard, props);

		const card = screen.getByRole('link', { name: 'Relay' });
		expect(card).toHaveAttribute('href', '/2026/disciplines/10');
		expect(card).toHaveTextContent('Relay 2 rounds');
		expect(card).not.toHaveClass('unrevealed');
	});

	it('takes another accessible name when given one', () => {
		renderWith(DisciplineCard, { ...props, label: 'Relay, all-time table' });

		expect(screen.getByRole('link', { name: 'Relay, all-time table' })).toBeInTheDocument();
	});

	it('follows a new name when reused without a label', async () => {
		const { component } = renderWith(DisciplineCard, props);

		await component.$set({ name: 'Rugby', discipline: 'Rugby' });

		expect(screen.getByRole('link', { name: 'Rugby' })).toBeInTheDocument();
	});

	it('marks an unrevealed discipline', () => {
		renderWith(DisciplineCard, { ...props, unrevealed: true });

		expect(screen.getByRole('link', { name: 'Relay' })).toHaveClass('unrevealed');
	});
});
