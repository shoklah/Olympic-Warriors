import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import TabBar from './TabBar.svelte';

describe('TabBar', () => {
	it('links the three sections of the year', () => {
		render(TabBar, { year: 2026, pathname: '/2026/teams/1' });

		expect(screen.getByRole('link', { name: 'Ranking' })).toHaveAttribute(
			'href',
			'/2026/ranking'
		);
		expect(screen.getByRole('link', { name: 'Teams' })).toHaveAttribute('href', '/2026/teams');
		expect(screen.getByRole('link', { name: 'Disciplines' })).toHaveAttribute(
			'href',
			'/2026/disciplines'
		);
	});

	it('marks the section of the current path', () => {
		render(TabBar, { year: 2026, pathname: '/2026/teams/1' });

		expect(screen.getByRole('link', { name: 'Teams' })).toHaveAttribute('aria-current', 'page');
		expect(screen.getByRole('link', { name: 'Ranking' })).not.toHaveAttribute('aria-current');
		expect(screen.getByRole('link', { name: 'Disciplines' })).not.toHaveAttribute(
			'aria-current'
		);
	});

	it('renders nothing without a year', () => {
		const { container } = render(TabBar, { year: null, pathname: '/' });

		expect(container.querySelector('nav')).toBeNull();
	});

	it('adds an external photos item when the edition has an album', () => {
		render(TabBar, {
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
		render(TabBar, { year: 2026, pathname: '/2026/ranking' });

		expect(screen.queryByRole('link', { name: 'Photos' })).toBeNull();
	});
});
