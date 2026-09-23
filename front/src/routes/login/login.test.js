import { screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Login from './login.svelte';

vi.mock('$app/forms', () => ({ enhance: () => ({ destroy() {} }) }));

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
});
