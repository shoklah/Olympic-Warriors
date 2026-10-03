<script>
	import { onMount } from 'svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import BadgeCollection from '$lib/components/BadgeCollection.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import PhotoEditor from '$lib/components/PhotoEditor.svelte';
	import { badgeCollection } from '$lib/badges';
	import { fullName } from '$lib/players';
	import { useT } from '$lib/i18n';

	export let data;
	export let form;

	const t = useT();

	$: account = data.account;
	$: profile = data.profile;
	$: name = fullName(profile);
	$: collection = badgeCollection(profile.badges ?? []);

	/** The result of `action` when the last post was that action's, else null. */
	$: resultOf = (action) => (form?.action === action ? form : null);
	$: emailResult = resultOf('email');
	$: passwordResult = resultOf('password');
	$: deleteResult = resultOf('deactivate');
	$: passwordErrors = passwordResult?.errors ?? [];

	/** Each form's message element, by action: what its blamed field reads out, and what gets
	 * focus when no field is to blame. */
	const MESSAGE = { email: 'email-message', password: 'password-message', deactivate: 'danger-message' };

	// The field each refusal blames, so it carries aria-invalid and reads the message out.
	$: emailError = emailResult?.error;
	$: passwordError = passwordResult?.error;
	$: deleteError = deleteResult?.error;
	$: blamed = {
		emailAddress: emailError === 'account.error.invalid_email',
		emailPassword: emailError === 'account.error.wrong_password',
		currentPassword: passwordError === 'account.error.wrong_password',
		newPassword: passwordErrors.length > 0,
		confirmation: passwordError === 'account.error.mismatch',
		word: deleteError === 'account.error.confirmation',
		deletePassword: deleteError === 'account.error.wrong_password'
	};
	/** The attributes of a field: invalid and described by its form's message when blamed. */
	const fieldState = (isBlamed, action) =>
		isBlamed ? { 'aria-invalid': 'true', 'aria-describedby': MESSAGE[action] } : {};

	/** Each action's section, where its posted result shows. */
	const sections = {};

	// Every form here is a plain POST, so a submit reloads the page with focus at the top and
	// a message screen readers do not reliably announce: focus the field the message blames,
	// else the message itself, as the claim and reset pages do.
	onMount(() => {
		const section = sections[form?.action];
		if (!section) return;
		const target =
			section.querySelector('[aria-invalid="true"]') ?? document.getElementById(MESSAGE[form.action]);
		if (!target) return;
		target.focus();
		target.scrollIntoView?.({ block: 'center' });
	});

	/** The photo editor is open. */
	let editing = false;
	/** The photo button, given focus back when the editor closes. */
	let camera = null;
</script>

<svelte:head>
	<title>{t('account.title')}</title>
</svelte:head>

<div class="page">
	<Breadcrumb
		items={[
			{ label: t('players.title'), href: '/players' },
			{ label: name, href: `/players/${profile.id}` },
			{ label: t('account.title') }
		]}
	/>
	<h1>{t('account.title')}</h1>
	<p class="username">{t('account.username', { name: account.username })}</p>

	<section aria-labelledby="account-photo">
		<h2 id="account-photo">{t('account.section.photo')}</h2>
		<div class="photo">
			<Avatar photo={profile.photo?.large ?? null} name={profile} />
			<button
				type="button"
				class="pill"
				aria-haspopup="dialog"
				bind:this={camera}
				on:click={() => (editing = true)}>{t('account.photoEdit')}</button
			>
		</div>
		<PhotoEditor
			open={editing}
			photo={profile.photo ?? null}
			locked={Boolean(data.me?.photo_locked)}
			name={profile}
			opener={camera}
			on:close={() => (editing = false)}
		/>
	</section>

	<section aria-labelledby="account-showcase">
		<h2 id="account-showcase">{t('account.section.showcase')}</h2>
		<BadgeCollection
			{collection}
			badgeStats={profile.badge_stats ?? null}
			progress={profile.progress ?? []}
			editable
			showcase={profile.showcase ?? null}
			heading={false}
		/>
	</section>

	<!-- Plain POSTs, never use:enhance: a password change stores a new token cookie, and a
	     deletion clears it, so the whole page reloads as after /login. -->
	<section aria-labelledby="account-email" bind:this={sections.email}>
		<h2 id="account-email">{t('account.email')}</h2>
		<form method="POST" action="?/email">
			<input type="text" name="username" autocomplete="username" value={account.username} readonly hidden />
			<div class="field">
				<label for="email-address">{t('account.email')}</label>
				<input
					id="email-address"
					type="email"
					name="email"
					autocomplete="email"
					value={emailResult?.email ?? account.email}
					class:invalid={blamed.emailAddress}
					{...fieldState(blamed.emailAddress, 'email')}
				/>
			</div>
			<div class="field">
				<label for="email-password">{t('account.currentPassword')}</label>
				<input
					id="email-password"
					type="password"
					name="password"
					autocomplete="current-password"
					class:invalid={blamed.emailPassword}
					{...fieldState(blamed.emailPassword, 'email')}
				/>
			</div>
			{#if emailResult?.error}
				<p class="error" id="email-message" tabindex="-1" role="alert">{t(emailResult.error)}</p>
			{:else if emailResult?.ok}
				<p class="saved" id="email-message" tabindex="-1" role="status">{t('account.saved')}</p>
			{/if}
			<button class="submit">{t('account.saveEmail')}</button>
		</form>
	</section>

	<section aria-labelledby="account-password" bind:this={sections.password}>
		<h2 id="account-password">{t('account.section.password')}</h2>
		<form method="POST" action="?/password">
			<!-- Tells a password manager which account the new password belongs to. -->
			<input type="text" name="username" autocomplete="username" value={account.username} readonly hidden />
			<div class="field">
				<label for="password-current">{t('account.currentPassword')}</label>
				<input
					id="password-current"
					type="password"
					name="current"
					autocomplete="current-password"
					class:invalid={blamed.currentPassword}
					{...fieldState(blamed.currentPassword, 'password')}
				/>
			</div>
			<div class="field">
				<label for="password-new">{t('account.newPassword')}</label>
				<input
					id="password-new"
					type="password"
					name="new"
					autocomplete="new-password"
					class:invalid={blamed.newPassword}
					{...fieldState(blamed.newPassword, 'password')}
				/>
			</div>
			<div class="field">
				<label for="password-confirmation">{t('account.newPasswordConfirmation')}</label>
				<input
					id="password-confirmation"
					type="password"
					name="confirmation"
					autocomplete="new-password"
					class:invalid={blamed.confirmation}
					{...fieldState(blamed.confirmation, 'password')}
				/>
			</div>
			{#if passwordErrors.length > 0}
				<div class="error" id="password-message" tabindex="-1" role="alert">
					{#each passwordErrors as key}<p>{t(key)}</p>{/each}
				</div>
			{:else if passwordResult?.error}
				<p class="error" id="password-message" tabindex="-1" role="alert">{t(passwordResult.error)}</p>
			{:else if passwordResult?.ok}
				<p class="saved" id="password-message" tabindex="-1" role="status">{t('account.saved')}</p>
			{/if}
			<button class="submit">{t('account.savePassword')}</button>
		</form>
	</section>

	<section aria-labelledby="account-session">
		<h2 id="account-session">{t('account.section.session')}</h2>
		<form method="POST" action="/logout">
			<input type="hidden" name="redirectTo" value="/" />
			<button class="pill">{t('account.logout')}</button>
		</form>
	</section>

	<section class="danger-zone" aria-labelledby="account-danger" bind:this={sections.deactivate}>
		<h2 id="account-danger">{t('account.delete')}</h2>
		<form method="POST" action="?/deactivate">
			<p class="text">{t('account.dangerText')}</p>
			<input type="text" name="username" autocomplete="username" value={account.username} readonly hidden />
			<div class="field">
				<label for="danger-confirmation">{t('account.confirmWord')}</label>
				<input
					id="danger-confirmation"
					type="text"
					name="confirmation"
					autocomplete="off"
					autocapitalize="characters"
					spellcheck="false"
					placeholder={t('account.confirmWordValue')}
					class:invalid={blamed.word}
					{...fieldState(blamed.word, 'deactivate')}
				/>
			</div>
			<div class="field">
				<label for="danger-password">{t('account.currentPassword')}</label>
				<input
					id="danger-password"
					type="password"
					name="password"
					autocomplete="current-password"
					class:invalid={blamed.deletePassword}
					{...fieldState(blamed.deletePassword, 'deactivate')}
				/>
			</div>
			{#if deleteResult?.error}
				<p class="error" id="danger-message" tabindex="-1" role="alert">{t(deleteResult.error)}</p>
			{/if}
			<button class="danger">{t('account.delete')}</button>
		</form>
	</section>
</div>

<style>
	h1 {
		margin: 0.2rem 0 0.4rem;
		overflow-wrap: anywhere;
	}

	.username {
		margin: 0 0 1.4rem;
		color: var(--muted);
		overflow-wrap: anywhere;
	}

	section {
		margin: 0 0 1rem;
		padding: 16px;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	h2 {
		margin: 0 0 1rem;
	}

	/* A picture, so px, as on the profile header. */
	.photo {
		--avatar-size: 96px;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 16px;
	}

	form {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 1rem;
		max-width: 30rem;
	}

	.field {
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}

	label {
		color: var(--muted);
		font-size: 0.9rem;
		font-weight: 600;
	}

	/* The claim page's underlined fields. */
	input {
		background: transparent;
		color: var(--text);
		border: 0;
		border-bottom: 2px solid var(--line);
		width: 100%;
		padding: 0.5rem 0.25rem;
		font-family: inherit;
		font-size: 1.1rem;
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

	.error,
	.saved {
		margin: 0;
		font-weight: 600;
	}

	.error {
		color: var(--loss);
	}

	/* Messages take focus only from the script, after a submit: no ring around a sentence. */
	.error:focus,
	.saved:focus {
		outline: none;
	}

	.error p {
		margin: 0;
	}

	.saved {
		color: var(--win);
	}

	.text {
		margin: 0;
		color: var(--text);
	}

	button {
		min-height: 44px;
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		cursor: pointer;
	}

	button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.submit {
		padding: 0 2rem;
		background: var(--accent);
		color: var(--bg);
		border: none;
		border-radius: var(--radius);
	}

	.submit:hover {
		opacity: 0.8;
	}

	/* Quiet like the header's pills. */
	.pill {
		padding: 0 0.9em;
		background: transparent;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius-pill);
		color: var(--muted);
	}

	.pill:hover {
		color: var(--accent);
		border-color: var(--accent);
	}

	.danger-zone {
		border-color: var(--loss);
	}

	.danger {
		padding: 0 2rem;
		background: transparent;
		border: 1px solid var(--loss);
		border-radius: var(--radius);
		color: var(--loss);
	}

	.danger:hover {
		background: var(--loss);
		color: var(--bg);
	}

	.danger:focus-visible {
		outline-color: var(--loss);
	}
</style>
