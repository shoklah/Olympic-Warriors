import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import TabBar from './TabBar.svelte';

describe('TabBar', () => {
	it('links the two sections of the year', () => {
		renderWith(TabBar, { year: 2026, pathname: '/2026/teams/1' });

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute(
			'href',
			'/2026/ranking'
		);
		expect(screen.queryByRole('link', { name: 'Teams' })).toBeNull();
		expect(screen.getByRole('link', { name: 'Disciplines' })).toHaveAttribute(
			'href',
			'/2026/disciplines'
		);
	});

	it('marks the section of the current path, ranking for a team page', () => {
		renderWith(TabBar, { year: 2026, pathname: '/2026/teams/1' });

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('link', { name: 'Disciplines' })).not.toHaveAttribute(
			'aria-current'
		);
	});

	it('marks disciplines on a discipline page only', () => {
		renderWith(TabBar, { year: 2026, pathname: '/2026/disciplines/10' });

		expect(screen.getByRole('link', { name: 'Disciplines' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('link', { name: 'Ranking' })).not.toHaveAttribute('aria-current');
	});

	it('renders nothing without a year', () => {
		const { container } = renderWith(TabBar, { year: null, pathname: '/' });

		expect(container.querySelector('nav')).toBeNull();
	});

	it('renders nothing when the year is missing', () => {
		const { container } = renderWith(TabBar, { year: undefined, pathname: '/' });

		expect(container.querySelector('nav')).toBeNull();
	});

	it('renders nothing when the year is not a number', () => {
		const { container } = renderWith(TabBar, { year: 'abc', pathname: '/abc/teams' });

		expect(container.querySelector('nav')).toBeNull();
	});

	it('adds an external photos item when the edition has an album', () => {
		renderWith(TabBar, {
			year: 2026,
			pathname: '/2026/ranking',
			photosUrl: 'https://photos.example/2026'
		});

		const photos = screen.getByRole('link', { name: 'Photos' });
		expect(photos).toHaveAttribute('href', 'https://photos.example/2026');
		expect(photos).toHaveAttribute('target', '_blank');
		expect(photos).not.toHaveAttribute('aria-current');
	});

	it('has no photos item by default', () => {
		renderWith(TabBar, { year: 2026, pathname: '/2026/ranking' });

		expect(screen.queryByRole('link', { name: 'Photos' })).toBeNull();
	});

	it('speaks French under fr', () => {
		renderWith(TabBar, { year: 2026, pathname: '/2026/teams/1' }, 'fr');

		expect(screen.getByRole('navigation', { name: 'Rubriques' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Classement' })).toHaveAttribute('aria-current', 'page');
	});

	it('speaks French without any locale in context', () => {
		render(TabBar, { year: 2026, pathname: '/2026/ranking' });

		expect(screen.getByRole('link', { name: 'Classement' })).toBeInTheDocument();
	});
});
