import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';
import { profile } from '$lib/fixtures/players.js';

// The collection's showcase forms use use:enhance; the photo editor still needs the real
// deserialize.
vi.mock('$app/forms', async (importOriginal) => ({
	...(await importOriginal()),
	enhance: () => ({ destroy() {} })
}));

/** The root layout's `me` for Xavier Baby, whose profile the `profile` fixture is (id 34). */
const me = {
	id: 34,
	first_name: 'Xavier',
	last_name: 'Baby',
	photo: profile.photo ?? null,
	is_person: true,
	photo_locked: false
};

const data = { account: { id: 34, username: 'xavierbaby', email: 'x@mail.example' }, profile, me };

/** The section under the h2 named `name`. */
const section = (name) => screen.getByRole('heading', { level: 2, name }).closest('section');

describe('account page', () => {
	it('shows the heading, the username and a breadcrumb back to the profile', () => {
		renderWith(Page, { data, form: null });

		expect(screen.getByRole('heading', { level: 1, name: 'My account' })).toBeInTheDocument();
		expect(screen.getByText('Username: xavierbaby')).toBeInTheDocument();
		const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
		expect(within(breadcrumb).getByRole('link', { name: 'Players' })).toHaveAttribute('href', '/players');
		expect(within(breadcrumb).getByRole('link', { name: 'Xavier Baby' })).toHaveAttribute('href', '/players/34');
	});

	it('shows every section', () => {
		renderWith(Page, { data, form: null });

		for (const name of ['Photo', 'Badge showcase', 'Email address', 'Password', 'Session', 'Delete my account']) {
			expect(screen.getByRole('heading', { level: 2, name })).toBeInTheDocument();
		}
	});

	it('opens the photo editor from the photo section', async () => {
		renderWith(Page, { data, form: null });

		expect(screen.queryByRole('dialog')).toBeNull();
		await fireEvent.click(within(section('Photo')).getByRole('button', { name: 'Change my photo' }));
		expect(screen.getByRole('dialog', { name: 'My photo' })).toBeInTheDocument();
	});

	it('offers the showcase picker', () => {
		renderWith(Page, { data, form: null });

		expect(within(section('Badge showcase')).getByRole('button', { name: 'Choose my showcase' })).toBeInTheDocument();
	});

	it('prefills the email form and posts it to ?/email', () => {
		renderWith(Page, { data, form: null });

		const email = screen.getByRole('textbox', { name: 'Email address' });
		expect(email).toHaveValue('x@mail.example');
		expect(email).toHaveAttribute('autocomplete', 'email');
		const form = email.closest('form');
		expect(form).toHaveAttribute('method', 'POST');
		expect(form).toHaveAttribute('action', '?/email');
		expect(within(form).getByLabelText('Current password')).toHaveAttribute('autocomplete', 'current-password');
		expect(within(form).getByRole('button', { name: 'Save the address' })).toBeInTheDocument();
	});

	it('gives the password form a username hint for password managers', () => {
		renderWith(Page, { data, form: null });

		const form = within(section('Password')).getByRole('button', { name: 'Change the password' }).closest('form');
		expect(form).toHaveAttribute('action', '?/password');
		const username = form.querySelector('input[name="username"]');
		expect(username).toHaveValue('xavierbaby');
		expect(username).toHaveAttribute('autocomplete', 'username');
		expect(username).toHaveAttribute('readonly');
		expect(within(form).getByLabelText('Current password')).toHaveAttribute('autocomplete', 'current-password');
		expect(within(form).getByLabelText('New password')).toHaveAttribute('autocomplete', 'new-password');
		expect(within(form).getByLabelText('Confirm the new password')).toHaveAttribute('autocomplete', 'new-password');
	});

	it('logs out through a plain POST to /logout', () => {
		renderWith(Page, { data, form: null });

		const form = within(section('Session')).getByRole('button', { name: 'Log out' }).closest('form');
		expect(form).toHaveAttribute('method', 'POST');
		expect(form).toHaveAttribute('action', '/logout');
		expect(form.querySelector('input[name="redirectTo"]')).toHaveValue('/');
	});

	it('asks for the typed word and the password before deleting', () => {
		renderWith(Page, { data, form: null });

		const danger = section('Delete my account');
		const form = within(danger).getByRole('button', { name: 'Delete my account' }).closest('form');
		expect(form).toHaveAttribute('action', '?/deactivate');
		expect(within(form).getByLabelText('Type DELETE to confirm')).toHaveAttribute('placeholder', 'DELETE');
		expect(within(form).getByLabelText('Current password')).toHaveAttribute('type', 'password');
		expect(within(danger).getByText(/Your account will be deactivated/)).toBeInTheDocument();
	});

	it("shows an action's error under its own section only", () => {
		renderWith(Page, { data, form: { action: 'email', error: 'account.error.wrong_password' } });

		const alert = screen.getByRole('alert');
		expect(alert).toHaveTextContent('Wrong current password');
		expect(section('Email address')).toContainElement(alert);
		expect(within(section('Password')).queryByText('Wrong current password')).toBeNull();
		expect(within(section('Delete my account')).queryByText('Wrong current password')).toBeNull();
	});

	it("lists the password validators' refusals", () => {
		renderWith(Page, {
			data,
			form: { action: 'password', errors: ['claim.error.password_too_short', 'claim.error.password_too_common'] }
		});

		const password = section('Password');
		expect(within(password).getByText('Password too short: 8 characters minimum')).toBeInTheDocument();
		expect(within(password).getByText('Password too common')).toBeInTheDocument();
		expect(within(section('Email address')).queryByRole('alert')).toBeNull();
	});

	it('confirms a saved change in its own section', () => {
		renderWith(Page, { data, form: { ok: true, action: 'password' } });

		expect(within(section('Password')).getByRole('status')).toHaveTextContent('Changes saved');
		expect(within(section('Email address')).queryByText('Changes saved')).toBeNull();
	});

	it('shows a deletion refusal in the danger zone', () => {
		renderWith(Page, { data, form: { action: 'deactivate', error: 'account.error.confirmation' } });

		expect(within(section('Delete my account')).getByRole('alert')).toHaveTextContent(
			'Type the requested word to confirm'
		);
	});

	it('renders in French', () => {
		render(Page, { props: { data, form: null } });

		expect(screen.getByRole('heading', { level: 1, name: 'Mon compte' })).toBeInTheDocument();
		expect(screen.getByRole('textbox', { name: 'Adresse e-mail' })).toHaveValue('x@mail.example');
		expect(screen.getByText('Identifiant : xavierbaby')).toBeInTheDocument();
		expect(screen.getByLabelText('Tapez SUPPRIMER pour confirmer')).toHaveAttribute('placeholder', 'SUPPRIMER');
		expect(screen.getByRole('button', { name: 'Supprimer mon compte' })).toBeInTheDocument();
	});
});
