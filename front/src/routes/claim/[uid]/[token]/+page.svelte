<script>
	import { useT } from '$lib/i18n';

	export let data;
	export let form;

	const t = useT();

	// The action's 404 (the link was used or expired since the page loaded) wins over the load.
	$: invalid = data.state === 'invalid' || Boolean(form?.invalid);
	$: passwordErrors = form?.password ?? [];
	$: confirmationErrors = form?.confirmation ?? [];

	let usernameElement;
	let copyStatus = null;

	async function copyUsername() {
		try {
			await navigator.clipboard.writeText(data.username);
			copyStatus = 'claim.copied';
		} catch {
			// No Clipboard API (an insecure origin, an older browser) or a refused permission:
			// select the username instead, so it can be copied by hand.
			window.getSelection()?.selectAllChildren(usernameElement);
			copyStatus = 'claim.copyFailed';
		}
	}
</script>

<svelte:head>
	<!-- The link is a live credential until used: keep it out of other sites' Referer. -->
	<meta name="referrer" content="same-origin" />
</svelte:head>

{#if invalid}
	<section class="notice">
		<h1>{t('claim.title')}</h1>
		<p>{t('claim.invalidLink')}</p>
	</section>
{:else if data.state === 'throttled'}
	<section class="notice">
		<h1>{t('claim.title')}</h1>
		<p>{t('login.throttled')}</p>
	</section>
{:else}
	<!-- A plain POST, never use:enhance: the redirect after a claim then reloads the whole page,
	     so the root layout sets the organiser and me contexts from the new cookie, as /login does. -->
	<form method="POST" action="?/claim">
		<h1>{t('claim.greeting', { name: data.first_name })}</h1>

		<div class="identity">
			<div class="identifier">
				<p data-testid="username">
					{t('claim.username')} <strong bind:this={usernameElement}>{data.username}</strong>
				</p>
				<button type="button" class="copy" aria-label={t('claim.copyUsername')} on:click={copyUsername}>
					{t('claim.copy')}
				</button>
			</div>
			<p class="copy-status" role="status">{copyStatus ? t(copyStatus) : ''}</p>
		</div>

		{#if form?.error}<p class="error" role="alert">{t(form.error)}</p>{/if}

		<!-- Tells a password manager which account the new password belongs to. -->
		<input type="text" name="username" autocomplete="username" value={data.username} readonly hidden />

		<div class="field">
			<label class="visually-hidden" for="claim-password">{t('claim.password')}</label>
			{#if passwordErrors.length > 0}
				<div class="error" id="claim-password-errors">
					{#each passwordErrors as key}<p>{t(key)}</p>{/each}
				</div>
			{/if}
			<input
				id="claim-password"
				type="password"
				name="password"
				autocomplete="new-password"
				placeholder={t('claim.password')}
				class:invalid={passwordErrors.length > 0}
				aria-invalid={passwordErrors.length > 0 ? 'true' : undefined}
				aria-describedby={passwordErrors.length > 0 ? 'claim-password-errors' : undefined}
			/>
		</div>

		<div class="field">
			<label class="visually-hidden" for="claim-confirmation">{t('claim.confirmation')}</label>
			{#if confirmationErrors.length > 0}
				<div class="error" id="claim-confirmation-errors">
					{#each confirmationErrors as key}<p>{t(key)}</p>{/each}
				</div>
			{/if}
			<input
				id="claim-confirmation"
				type="password"
				name="confirmation"
				autocomplete="new-password"
				placeholder={t('claim.confirmation')}
				class:invalid={confirmationErrors.length > 0}
				aria-invalid={confirmationErrors.length > 0 ? 'true' : undefined}
				aria-describedby={confirmationErrors.length > 0 ? 'claim-confirmation-errors' : undefined}
			/>
		</div>

		<button class="submit">{t('claim.submit')}</button>
	</form>
{/if}

<style>
	/* The login form's look: one centred column, underlined fields, the accent button. */
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
	}

	h1,
	.notice p,
	.identity,
	.error {
		text-align: center;
	}

	h1 {
		overflow-wrap: anywhere;
	}

	.notice p {
		color: var(--text);
		font-size: 1.1rem;
	}

	.identity {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
	}

	.identifier {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: center;
		gap: 0.5rem 1rem;
		color: var(--text);
		font-size: 1.1rem;
	}

	strong {
		color: var(--ink);
		overflow-wrap: anywhere;
		/* One tap or click selects the whole username, for copying by hand. */
		user-select: all;
		-webkit-user-select: all;
	}

	/* Quiet like the header's login pill. */
	.copy {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		padding: 0 0.9em;
		background: transparent;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius-pill);
		color: var(--muted);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		cursor: pointer;
	}

	.copy:hover {
		color: var(--accent);
		border-color: var(--accent);
	}

	.copy:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.copy-status {
		min-height: 1.5em;
		color: var(--muted);
		font-size: 0.9rem;
	}

	.error {
		color: var(--loss);
		font-size: 1rem;
		font-weight: 600;
	}

	.field {
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
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

	input.invalid,
	input.invalid:focus-visible {
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
