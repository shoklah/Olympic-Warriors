import { screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import LoginPage from './+page.svelte';

const state = {};

vi.mock('$app/stores', async () => {
	const { readable } = await import('svelte/store');
	return { page: readable(new Proxy({}, { get: (_, key) => state[key] })) };
});

const nextField = (container) => container.querySelector('input[name="next"]');

describe('login page', () => {
	beforeEach(() => {
		state.url = new URL('http://x/login');
	});

	it('fills next from the ?next= of the URL', () => {
		state.url = new URL('http://x/login?next=/account');
		const { container } = renderWith(LoginPage, { form: null }, 'en');
		expect(nextField(container)).toHaveValue('/account');
	});

	it('prefers the next the failed attempt gave back', () => {
		state.url = new URL('http://x/login?next=/account');
		const { container } = renderWith(LoginPage, { form: { error: 'x', username: 'ana', next: '/players/3' } }, 'en');
		expect(nextField(container)).toHaveValue('/players/3');
	});

	it('sends an empty next without one in the URL', () => {
		const { container } = renderWith(LoginPage, { form: null }, 'en');
		expect(nextField(container)).toHaveValue('');
	});

	it('carries a crafted next as given, adding no scheme or host: the action validates it', () => {
		state.url = new URL('http://x/login?next=//evil.example');
		const { container } = renderWith(LoginPage, { form: null }, 'en');
		expect(nextField(container)).toHaveValue('//evil.example');
	});
});
