import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Breadcrumb from './Breadcrumb.svelte';
import { renderWith } from '$lib/test-utils';

const items = [
	{ label: '2026', href: '/2026' },
	{ label: 'Teams', href: '/2026/teams' },
	{ label: 'Bisons' }
];

describe('Breadcrumb', () => {
	it('renders a labelled navigation', () => {
		renderWith(Breadcrumb, { items });

		expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument();
	});

	it('links every item but the last', () => {
		renderWith(Breadcrumb, { items });

		expect(screen.getByRole('link', { name: '2026' })).toHaveAttribute('href', '/2026');
		expect(screen.getByRole('link', { name: 'Teams' })).toHaveAttribute('href', '/2026/teams');
		expect(screen.queryByRole('link', { name: 'Bisons' })).toBeNull();
		expect(screen.getByText('Bisons')).toBeInTheDocument();
	});

	it('separates the items with ›', () => {
		renderWith(Breadcrumb, { items });

		expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent(
			'2026 › Teams › Bisons'
		);
	});

	it('renders a single item without a separator', () => {
		renderWith(Breadcrumb, { items: [{ label: 'Ranking' }] });

		expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Ranking');
		expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).not.toHaveTextContent('›');
	});

	it('labels the landmark in French under fr', () => {
		renderWith(Breadcrumb, { items: [{ label: '2026', href: '/2026' }, { label: 'Classement' }] }, 'fr');
		expect(screen.getByRole('navigation', { name: "Fil d'Ariane" })).toBeInTheDocument();
	});
});
