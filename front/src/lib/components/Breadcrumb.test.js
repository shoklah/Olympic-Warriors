import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Breadcrumb from './Breadcrumb.svelte';

const items = [
	{ label: '2026', href: '/2026' },
	{ label: 'Teams', href: '/2026/teams' },
	{ label: 'Bisons' }
];

describe('Breadcrumb', () => {
	it('renders a labelled navigation', () => {
		render(Breadcrumb, { items });

		expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument();
	});

	it('links every item but the last', () => {
		render(Breadcrumb, { items });

		expect(screen.getByRole('link', { name: '2026' })).toHaveAttribute('href', '/2026');
		expect(screen.getByRole('link', { name: 'Teams' })).toHaveAttribute('href', '/2026/teams');
		expect(screen.queryByRole('link', { name: 'Bisons' })).toBeNull();
		expect(screen.getByText('Bisons')).toBeInTheDocument();
	});

	it('separates the items with ›', () => {
		render(Breadcrumb, { items });

		expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent(
			'2026 › Teams › Bisons'
		);
	});

	it('renders a single item without a separator', () => {
		render(Breadcrumb, { items: [{ label: 'Ranking' }] });

		expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Ranking');
		expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).not.toHaveTextContent('›');
	});
});
