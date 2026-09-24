import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';

const ready = { state: 'ready', first_name: 'Léa', username: 'leamartin' };

const stubClipboard = (clipboard) =>
	Object.defineProperty(navigator, 'clipboard', { value: clipboard, configurable: true });

describe('claim page', () => {
	afterEach(() => {
		stubClipboard(undefined);
		window.getSelection()?.removeAllRanges();
	});

	it('greets the person, shows their username and asks for a new password twice', () => {
		const { container } = renderWith(Page, { data: ready, form: null });

		expect(screen.getByRole('heading', { level: 1, name: 'Hello Léa' })).toBeInTheDocument();
		expect(screen.getByTestId('username')).toHaveTextContent('Your username: leamartin');
		expect(screen.getByRole('button', { name: 'Copy the username' })).toHaveTextContent('Copy');

		const password = screen.getByLabelText('Password');
		const confirmation = screen.getByLabelText('Confirm the password');
		for (const field of [password, confirmation]) {
			expect(field).toHaveAttribute('type', 'password');
			expect(field).toHaveAttribute('autocomplete', 'new-password');
			expect(field).not.toHaveAttribute('aria-invalid');
		}
		expect(password).toHaveAttribute('name', 'password');
		expect(confirmation).toHaveAttribute('name', 'confirmation');

		// A plain POST to the claim action, so the redirect reloads the whole layout.
		const form = container.querySelector('form');
		expect(form).toHaveAttribute('method', 'POST');
		expect(form).toHaveAttribute('action', '?/claim');
		expect(screen.getByRole('button', { name: 'Activate my account' })).toBeInTheDocument();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('copies the username with the Clipboard API', async () => {
		const writeText = vi.fn().mockResolvedValue(undefined);
		stubClipboard({ writeText });
		renderWith(Page, { data: ready, form: null });

		await fireEvent.click(screen.getByRole('button', { name: 'Copy the username' }));

		expect(writeText).toHaveBeenCalledWith('leamartin');
		await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Username copied'));
	});

	it('selects the username instead when the browser cannot copy', async () => {
		stubClipboard(undefined);
		renderWith(Page, { data: ready, form: null });

		await fireEvent.click(screen.getByRole('button', { name: 'Copy the username' }));

		await waitFor(() =>
			expect(screen.getByRole('status')).toHaveTextContent('Could not copy: the username is selected')
		);
		expect(window.getSelection().toString()).toBe('leamartin');
	});

	it('ties each error to its field', () => {
		renderWith(Page, {
			data: ready,
			form: {
				password: ['claim.error.password_too_short', 'claim.error.password_too_common'],
				confirmation: ['claim.error.mismatch']
			}
		});

		const password = screen.getByLabelText('Password');
		expect(password).toHaveAttribute('aria-invalid', 'true');
		expect(password).toHaveAccessibleDescription(
			'Password too short: 8 characters minimum Password too common'
		);
		const confirmation = screen.getByLabelText('Confirm the password');
		expect(confirmation).toHaveAttribute('aria-invalid', 'true');
		expect(confirmation).toHaveAccessibleDescription('The two passwords do not match');
	});

	it('shows a throttled or failed attempt above the form', () => {
		renderWith(Page, { data: ready, form: { error: 'login.throttled' } });

		expect(screen.getByRole('alert')).toHaveTextContent('Too many attempts: try again later');
		expect(screen.getByLabelText('Password')).toBeInTheDocument();
	});

	it('says the link is no longer valid, with no form', () => {
		renderWith(Page, { data: { state: 'invalid' }, form: null });

		expect(screen.getByText('This link is no longer valid: ask an organiser for a new one')).toBeInTheDocument();
		expect(screen.queryByLabelText('Password')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Activate my account' })).toBeNull();
	});

	it('switches to the invalid-link state when the link died before the submit', () => {
		renderWith(Page, { data: ready, form: { invalid: true } });

		expect(screen.getByText('This link is no longer valid: ask an organiser for a new one')).toBeInTheDocument();
		expect(screen.queryByText(/Hello/)).toBeNull();
		expect(screen.queryByLabelText('Password')).toBeNull();
	});

	it('asks to wait, with no form, when even the greeting was throttled', () => {
		renderWith(Page, { data: { state: 'throttled' }, form: null });

		expect(screen.getByText('Too many attempts: try again later')).toBeInTheDocument();
		expect(screen.queryByLabelText('Password')).toBeNull();
	});

	it('speaks French under fr', () => {
		renderWith(
			Page,
			{ data: ready, form: { password: ['claim.error.password_entirely_numeric'] } },
			'fr'
		);

		expect(screen.getByRole('heading', { level: 1, name: 'Bonjour Léa' })).toBeInTheDocument();
		expect(screen.getByTestId('username')).toHaveTextContent('Votre identifiant : leamartin');
		expect(screen.getByRole('button', { name: "Copier l'identifiant" })).toHaveTextContent('Copier');
		expect(screen.getByLabelText('Mot de passe')).toHaveAccessibleDescription(
			'Le mot de passe ne peut pas être composé uniquement de chiffres'
		);
		expect(screen.getByLabelText('Confirmer le mot de passe')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Activer mon compte' })).toBeInTheDocument();
	});

	it('words the invalid link in French by default', () => {
		render(Page, { props: { data: { state: 'invalid' }, form: null } });

		expect(
			screen.getByText("Ce lien n'est plus valide : demandez-en un nouveau à un organisateur")
		).toBeInTheDocument();
	});
});
