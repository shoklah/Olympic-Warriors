import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Login from './login.svelte';

describe('login form', () => {
	it('speaks French under fr and ties a missing-field message to its input', () => {
		renderWith(Login, { form: { missing: { username: true }, username: '' } }, 'fr');

		const username = screen.getByPlaceholderText('Identifiant');
		expect(username).toHaveAttribute('aria-invalid', 'true');
		expect(username).toHaveAccessibleDescription('Champ obligatoire');
		expect(screen.getByPlaceholderText('Mot de passe')).not.toHaveAttribute('aria-invalid');
		expect(screen.getByRole('button', { name: 'Se connecter' })).toBeInTheDocument();
	});

	it('words a failed login from the dictionary, never the server message', () => {
		renderWith(Login, { form: { error: 'Authentication failed: token not received', username: 'ana' } }, 'en');

		expect(screen.getByText('Login failed: check your credentials')).toBeInTheDocument();
		expect(screen.queryByText(/token not received/)).toBeNull();
		expect(screen.getByPlaceholderText('Username')).toHaveValue('ana');
	});

	it('asks to wait, not to check the credentials, once the API throttles the attempts', () => {
		renderWith(Login, { form: { error: 'Request was throttled.', throttled: true, username: 'ana' } }, 'fr');

		expect(screen.getByText('Trop de tentatives : réessayez plus tard')).toBeInTheDocument();
		expect(screen.queryByText(/vérifiez vos identifiants/)).toBeNull();
	});

	it('links to the password reset page', () => {
		renderWith(Login, { form: null }, 'en');
		expect(screen.getByRole('link', { name: 'Forgot password?' })).toHaveAttribute('href', '/forgot');
	});

	it('words the reset link in French', () => {
		renderWith(Login, { form: null }, 'fr');
		expect(screen.getByRole('link', { name: 'Mot de passe oublié ?' })).toHaveAttribute('href', '/forgot');
	});

	it('carries next to the action in a hidden field', () => {
		const { container } = renderWith(Login, { form: null, next: '/account' }, 'en');
		expect(container.querySelector('input[name="next"]')).toHaveValue('/account');
	});

	it('carries whatever next it is given, as given: the action validates it', () => {
		const { container } = renderWith(Login, { form: null, next: '/players/12?tab=badges' }, 'en');
		expect(container.querySelector('input[name="next"]')).toHaveValue('/players/12?tab=badges');
	});

	it('sends an empty next by default', () => {
		const { container } = renderWith(Login, { form: null }, 'en');
		expect(container.querySelector('input[name="next"]')).toHaveValue('');
	});

	it('explains that registration is by invitation when the login leads to /register', () => {
		renderWith(Login, { form: null, next: '/register' });

		expect(screen.getByText(/Registration is by invitation/)).toBeInTheDocument();
	});

	it('says nothing of it for any other destination, and words it in French', () => {
		const other = renderWith(Login, { form: null, next: '/account' });
		expect(screen.queryByText(/Registration is by invitation/)).toBeNull();
		other.unmount();

		renderWith(Login, { form: null, next: '/register' }, 'fr');
		expect(screen.getByText(/Les inscriptions se font sur invitation/)).toBeInTheDocument();
	});
});
