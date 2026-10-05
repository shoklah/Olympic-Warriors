import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { registrationPayload } from '$lib/fixtures/registration.js';

describe('register page', () => {
	it('shows the title with the year and the form', () => {
		renderWith(Page, { data: { registration: registrationPayload }, form: null });

		expect(screen.getByRole('heading', { level: 1, name: 'Registration 2027' })).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toBeInTheDocument();
	});

	it('words the title in French', () => {
		renderWith(Page, { data: { registration: registrationPayload }, form: null }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Inscription 2027' })).toBeInTheDocument();
	});
});
