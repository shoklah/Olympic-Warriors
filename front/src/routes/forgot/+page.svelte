<script>
	import { useT } from '$lib/i18n';

	export let form;

	const t = useT();
</script>

{#if form?.sent}
	<section class="notice">
		<h1>{t('forgot.title')}</h1>
		<p role="status">{t('forgot.sent')}</p>
		<a class="quiet-link" href="/login">{t('forgot.back')}</a>
	</section>
{:else}
	<!-- A plain POST, like the login form. -->
	<form method="POST" action="?/request">
		<h1>{t('forgot.title')}</h1>

		{#if form?.error}<p class="error" id="forgot-error" role="alert">{t(form.error)}</p>{/if}

		<label class="visually-hidden" for="forgot-email">{t('forgot.email')}</label>
		<input
			id="forgot-email"
			type="email"
			name="email"
			autocomplete="email"
			placeholder={t('forgot.email')}
			aria-invalid={form?.error ? 'true' : undefined}
			aria-describedby={form?.error ? 'forgot-error' : undefined}
		/>

		<button class="submit">{t('forgot.submit')}</button>
		<a class="quiet-link" href="/login">{t('forgot.back')}</a>
	</form>
{/if}

<style>
	form,
	.notice {
		width: min(30rem, 80vw);
		display: flex;
		flex-direction: column;
		align-items: center;
		margin: 5rem auto;
		gap: 2rem;
	}

	h1,
	p {
		margin: 0;
		text-align: center;
	}

	.notice p {
		color: var(--text);
		font-size: 1.1rem;
	}

	.error {
		color: var(--loss);
		font-size: 1rem;
		font-weight: 600;
	}

	input {
		background: transparent;
		color: var(--text);
		border: 0;
		border-bottom: 2px solid var(--line);
		width: 100%;
		padding: 0.5rem 1rem;
		font-family: inherit;
		font-size: 1.25rem;
		font-weight: 600;
		transition: 0.5s;
	}

	input:focus-visible {
		outline: none;
		border-bottom-color: var(--accent);
	}

	input[aria-invalid='true'],
	input[aria-invalid='true']:focus-visible {
		border-bottom-color: var(--loss);
	}

	.submit {
		background: var(--accent);
		color: var(--bg);
		font-family: var(--font-display);
		letter-spacing: 0.15em;
		padding: 0.7rem 3rem;
		border: none;
		border-radius: var(--radius);
		font-size: 1.2rem;
		cursor: pointer;
		transition: 0.3s;
	}

	.submit:hover,
	.submit:focus-visible {
		opacity: 0.8;
	}

	.submit:focus-visible {
		outline: 2px solid var(--ink);
		outline-offset: 2px;
	}
</style>
