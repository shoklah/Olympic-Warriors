import { screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import Page from './+page.svelte';

describe('forgot page', () => {
	it('asks for the email in a plain POST form', () => {
		const { container } = renderWith(Page, { form: null });

		expect(screen.getByRole('heading', { level: 1, name: 'Forgot password' })).toBeInTheDocument();
		const email = screen.getByLabelText('Email address');
		expect(email).toHaveAttribute('type', 'email');
		expect(email).toHaveAttribute('name', 'email');
		expect(email).toHaveAttribute('autocomplete', 'email');
		const form = container.querySelector('form');
		expect(form).toHaveAttribute('method', 'POST');
		expect(form).toHaveAttribute('action', '?/request');
		expect(screen.getByRole('button', { name: 'Send the link' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Back to login' })).toHaveAttribute('href', '/login');
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('replaces the form by the neutral confirmation once sent', () => {
		const { container } = renderWith(Page, { form: { sent: true } });

		expect(screen.getByRole('status')).toHaveTextContent(/a link has just been sent/);
		expect(container.querySelector('form')).toBeNull();
		expect(screen.getByRole('link', { name: 'Back to login' })).toBeInTheDocument();
	});

	it('shows the error line and ties it to the field', () => {
		renderWith(Page, { form: { error: 'forgot.error.missing' } });

		expect(screen.getByRole('alert')).toHaveTextContent('Enter your email address');
		expect(screen.getByLabelText('Email address')).toHaveAccessibleDescription('Enter your email address');
	});

	it('words a failed send', () => {
		renderWith(Page, { form: { error: 'forgot.error.failed' } }, 'fr');

		expect(screen.getByRole('alert')).toHaveTextContent("L'envoi a échoué : réessayez plus tard");
	});

	it('speaks French', () => {
		renderWith(Page, { form: null }, 'fr');

		expect(screen.getByRole('heading', { level: 1, name: 'Mot de passe oublié' })).toBeInTheDocument();
		expect(screen.getByLabelText('Adresse e-mail')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Envoyer le lien' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Retour à la connexion' })).toBeInTheDocument();
	});
});
