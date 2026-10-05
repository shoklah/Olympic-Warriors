import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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

	it('shows an organiser who plays every section but the deletion', () => {
		const staff = { ...data, account: { ...data.account, is_staff: true } };
		renderWith(Page, { data: staff, form: null });

		for (const name of ['Photo', 'Badge showcase', 'Email address', 'Password', 'Session']) {
			expect(screen.getByRole('heading', { level: 2, name })).toBeInTheDocument();
		}
		expect(screen.queryByRole('heading', { level: 2, name: 'Delete my account' })).toBeNull();
		expect(screen.queryByRole('button', { name: 'Delete my account' })).toBeNull();
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
		expect(within(form).getByLabelText('Type “Delete” to confirm')).toHaveAttribute('placeholder', 'Delete');
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

	it('leaves focus alone when nothing was posted', () => {
		renderWith(Page, { data, form: null });

		expect(document.activeElement).toBe(document.body);
		expect(document.querySelector('[aria-invalid]')).toBeNull();
	});

	it('ties a refused address to the email field, focuses it and keeps what was typed', () => {
		renderWith(Page, {
			data,
			form: { action: 'email', error: 'account.error.invalid_email', email: 'typo@mail' }
		});

		const email = screen.getByRole('textbox', { name: 'Email address' });
		expect(email).toHaveValue('typo@mail');
		expect(email).toHaveAttribute('aria-invalid', 'true');
		expect(email).toHaveAccessibleDescription('Invalid email address');
		expect(within(section('Email address')).getByLabelText('Current password')).not.toHaveAttribute('aria-invalid');
		expect(document.activeElement).toBe(email);
	});

	it('ties a wrong password to the current-password field of its own form', () => {
		for (const [action, name] of [
			['email', 'Email address'],
			['password', 'Password'],
			['deactivate', 'Delete my account']
		]) {
			const { unmount } = renderWith(Page, { data, form: { action, error: 'account.error.wrong_password' } });

			const current = within(section(name)).getByLabelText('Current password');
			expect(current, action).toHaveAttribute('aria-invalid', 'true');
			expect(current, action).toHaveAccessibleDescription('Wrong current password');
			expect(document.activeElement, action).toBe(current);
			expect(document.querySelectorAll('[aria-invalid]'), action).toHaveLength(1);
			unmount();
		}
	});

	it('ties a mismatch to the confirmation field', () => {
		renderWith(Page, { data, form: { action: 'password', error: 'account.error.mismatch' } });

		const confirmation = screen.getByLabelText('Confirm the new password');
		expect(confirmation).toHaveAttribute('aria-invalid', 'true');
		expect(confirmation).toHaveAccessibleDescription('The two passwords do not match');
		expect(document.activeElement).toBe(confirmation);
	});

	it("ties the validators' refusals to the new password and focuses it", () => {
		renderWith(Page, {
			data,
			form: { action: 'password', errors: ['claim.error.password_too_short', 'claim.error.password_too_common'] }
		});

		const fresh = screen.getByLabelText('New password');
		expect(fresh).toHaveAttribute('aria-invalid', 'true');
		expect(fresh).toHaveAccessibleDescription('Password too short: 8 characters minimum Password too common');
		expect(document.activeElement).toBe(fresh);
	});

	it('ties a missing confirmation word to its field', () => {
		renderWith(Page, { data, form: { action: 'deactivate', error: 'account.error.confirmation' } });

		const word = screen.getByLabelText('Type “Delete” to confirm');
		expect(word).toHaveAttribute('aria-invalid', 'true');
		expect(word).toHaveAccessibleDescription('Type the requested word to confirm');
		expect(document.activeElement).toBe(word);
	});

	it('focuses the message itself when no field is to blame', () => {
		renderWith(Page, { data, form: { action: 'password', error: 'account.error.throttled' } });

		const alert = within(section('Password')).getByRole('alert');
		expect(alert).toHaveAttribute('tabindex', '-1');
		expect(document.activeElement).toBe(alert);
		expect(document.querySelector('[aria-invalid]')).toBeNull();
	});

	it('focuses the saved confirmation after a successful change', () => {
		renderWith(Page, { data, form: { ok: true, action: 'email' } });

		expect(document.activeElement).toBe(within(section('Email address')).getByRole('status'));
	});

	it('renders in French', () => {
		render(Page, { props: { data, form: null } });

		expect(screen.getByRole('heading', { level: 1, name: 'Mon compte' })).toBeInTheDocument();
		expect(screen.getByRole('textbox', { name: 'Adresse e-mail' })).toHaveValue('x@mail.example');
		expect(screen.getByText('Identifiant : xavierbaby')).toBeInTheDocument();
		expect(screen.getByLabelText('Tapez « Supprimer » pour confirmer')).toHaveAttribute('placeholder', 'Supprimer');
		expect(screen.getByRole('button', { name: 'Supprimer mon compte' })).toBeInTheDocument();
	});
});

describe('account page for an invited newcomer', () => {
	const invitee = {
		account: { id: 41, username: 'newbie', email: 'n@mail.example', is_staff: false, is_person: false },
		profile: null,
		registration: null,
		me: { id: 41, first_name: 'Nina', last_name: 'Neuf', photo: null, is_person: false, can_register: true, photo_locked: false }
	};

	it('shows the email, password and session sections but no photo or showcase', () => {
		renderWith(Page, { data: invitee, form: null });

		expect(screen.getByRole('heading', { level: 1, name: 'My account' })).toBeInTheDocument();
		for (const name of ['Email address', 'Password', 'Session']) {
			expect(screen.getByRole('heading', { level: 2, name })).toBeInTheDocument();
		}
		expect(screen.queryByRole('heading', { level: 2, name: 'Photo' })).toBeNull();
		expect(screen.queryByRole('heading', { level: 2, name: 'Badge showcase' })).toBeNull();
	});

	it('has no profile crumb to link to', () => {
		renderWith(Page, { data: invitee, form: null });

		const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' });
		expect(within(breadcrumb).getByRole('link', { name: 'Players' })).toBeInTheDocument();
		expect(within(breadcrumb).queryByRole('link', { name: /Nina/ })).toBeNull();
	});
});

describe('the registration link', () => {
	const open = {
		...data,
		me: { ...data.me, can_register: true },
		latestYear: 2027,
		editions: [{ year: 2027, start_date: '2027-09-18', registration_opens: '2027-01-01', registration_closes: null }]
	};

	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('links the registration while it is open', () => {
		vi.setSystemTime(new Date('2027-06-01T10:00:00Z'));
		renderWith(Page, { data: open, form: null });

		expect(within(section('Registration')).getByRole('link', { name: 'Registration 2027' })).toHaveAttribute('href', '/register');
	});

	it('shows no section once it is closed, for someone who cannot register, or without a window', () => {
		vi.setSystemTime(new Date('2027-09-18T10:00:00Z'));
		const closed = renderWith(Page, { data: open, form: null });
		expect(screen.queryByRole('heading', { level: 2, name: 'Registration' })).toBeNull();
		closed.unmount();

		vi.setSystemTime(new Date('2027-06-01T10:00:00Z'));
		const cannot = renderWith(Page, { data: { ...open, me: { ...open.me, can_register: false } }, form: null });
		expect(screen.queryByRole('heading', { level: 2, name: 'Registration' })).toBeNull();
		cannot.unmount();

		renderWith(Page, { data: { ...open, editions: [] }, form: null });
		expect(screen.queryByRole('heading', { level: 2, name: 'Registration' })).toBeNull();
	});

	it('words it in French', () => {
		vi.setSystemTime(new Date('2027-06-01T10:00:00Z'));
		renderWith(Page, { data: open, form: null }, 'fr');

		expect(screen.getByRole('heading', { level: 2, name: 'Inscription' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Inscription 2027' })).toBeInTheDocument();
	});
});
