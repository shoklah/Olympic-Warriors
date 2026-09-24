import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import Layout from './+layout.svelte';

// The page store as the layout reads it: each test sets the route before rendering, and
// Svelte reads the store's current value synchronously at init.
const pageState = vi.hoisted(() => ({
	route: { id: '/players' },
	params: {},
	url: new URL('http://localhost/players'),
	data: { editions: [{ id: 1, year: 2026, host: 'Paris', photos_url: null }], latestYear: 2026 },
	error: null
}));

vi.mock('$app/stores', () => ({
	page: {
		subscribe(run) {
			run(pageState);
			return () => {};
		}
	}
}));
vi.mock('$app/navigation', () => ({ goto: vi.fn(), afterNavigate: vi.fn(), onNavigate: vi.fn() }));

const data = { locale: 'en', organiser: false, me: null, editions: pageState.data.editions, latestYear: 2026 };

const renderAt = (routeId, pathname) => {
	pageState.route = { id: routeId };
	pageState.url = new URL(`http://localhost${pathname}`);
	return render(Layout, { props: { data } });
};

describe('root layout', () => {
	it('gives a section page the bottom tab bar', () => {
		const { container } = renderAt('/players', '/players');

		expect(container.querySelector('.app')).toHaveClass('has-tabbar');
		expect(screen.getAllByRole('link', { name: 'Players' }).length).toBeGreaterThan(1);
	});

	it('gives the login and claim pages no tab bar', () => {
		for (const [routeId, pathname] of [
			['/login', '/login'],
			['/claim/[uid]/[token]', '/claim/MzQ/cxqh2p-3f9a8b7c6d5e4f3a2b1c']
		]) {
			const { container, unmount } = renderAt(routeId, pathname);

			expect(container.querySelector('.app'), routeId).not.toHaveClass('has-tabbar');
			// Only the header's own tab is left.
			expect(screen.getAllByRole('link', { name: 'Players' }), routeId).toHaveLength(1);
			unmount();
		}
	});
});
