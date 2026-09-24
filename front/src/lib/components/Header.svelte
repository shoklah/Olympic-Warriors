<script>
	import { page } from '$app/stores';
	import { afterNavigate, goto } from '$app/navigation';
	import logo from '$lib/img/logo.svg';
	import { switchYearPath } from '$lib/edition';
	import { useLocale, useT } from '$lib/i18n';
	import { useMe, useOrganiser } from '$lib/session';
	import Avatar from './Avatar.svelte';

	const locale = useLocale();
	const t = useT();
	const organiser = useOrganiser();
	// Who is logged in, or null. An organiser keeps the ORGA pill, with their avatar in it
	// when they also play; anyone else logged in gets the account pill.
	const me = useMe();
	const smallPhoto = me?.photo?.small ?? null;
	// The accessible name starts with the visible first name (WCAG 2.5.3).
	const accountName = me?.first_name ? `${me.first_name} · ${t('account.profile')}` : t('account.profile');

	$: editions = $page.data.editions ?? [];
	// On an error page the year in the URL may be one with no edition, so fall back to the latest.
	$: year = Number(($page.error ? null : $page.params.year) ?? $page.data.latestYear);
	$: edition = editions.find((e) => e.year === year);
	$: tabs = year
		? [
				// A team page is reached from the ranking, so it lights that tab.
				{ name: t('nav.ranking'), url: `/${year}/ranking`, also: `/${year}/teams` },
				{ name: t('nav.disciplines'), url: `/${year}/disciplines` },
				// Spans every edition, so it points outside the year segment.
				{ name: t('nav.players'), url: '/players' },
				...(edition?.photos_url
					? [{ name: t('nav.photos'), url: edition.photos_url, external: true }]
					: [])
			]
		: [];

	const switchYear = (event) => goto(switchYearPath($page.url.pathname, event.target.value));

	// Where the header's forms (logout, language, theme) come back to.
	$: here = $page.url.pathname + $page.url.search;

	// Each direction twice, the stylesheet showing one of the four: the direction leads away
	// from the theme on screen, and a switch leading to the device's own theme posts `system`,
	// forgetting the choice instead of storing it, so the cookie only records a departure.
	const SWITCHES = [
		{ to: 'light', value: 'light' },
		{ to: 'light', value: 'system' },
		{ to: 'dark', value: 'dark' },
		{ to: 'dark', value: 'system' }
	];

	// Below 600px the account, language and theme controls fold behind a menu button.
	let open = false;
	let header;
	let toggle;

	// The login link navigates client-side and the header stays: close the menu with it.
	afterNavigate(() => (open = false));

	const onKeydown = (event) => {
		if (open && event.key === 'Escape') {
			open = false;
			toggle.focus();
		}
	};

	// The path, not `header.contains(target)`: the toggle's own click re-renders its icon before
	// this listener runs, detaching the clicked <path>, which would read as a click outside.
	const onClick = (event) => {
		if (open && !event.composedPath().includes(header)) open = false;
	};
</script>

<svelte:window on:keydown={onKeydown} on:click={onClick} />

<header bind:this={header}>
	<div class="logo">
		<a href="/">
			<img src={logo} alt="OW" />
		</a>
		{#if editions.length > 0}
			<select aria-label={t('header.edition')} value={year} on:change={switchYear}>
				{#each editions as e}
					<!-- Svelte 4 SSR ignores `value` on the select, so mark the option itself. -->
					<option value={e.year} selected={e.year === year}>{e.year}</option>
				{/each}
			</select>
		{/if}
		<button
			bind:this={toggle}
			class="round menu-toggle"
			type="button"
			aria-label={t('header.menu')}
			aria-expanded={open}
			aria-controls="header-settings"
			on:click={() => (open = !open)}
		>
			<svg viewBox="0 0 24 24" aria-hidden="true">
				{#if open}
					<path d="M6 6l12 12M18 6L6 18" />
				{:else}
					<path d="M4 7h16M4 12h16M4 17h16" />
				{/if}
			</svg>
		</button>
		<!-- One set of controls for both layouts: inline in the bar from 600px up
		     (`display: contents`), a panel under the bar behind the menu button below. -->
		<div id="header-settings" class="settings" class:open>
			{#if organiser}
				<!-- A plain POST like the language switch: the redirect reloads the page as a visitor. -->
				<form method="POST" action="/logout" class="orga">
					<input type="hidden" name="redirectTo" value={here} />
					<!-- The accessible name must contain the visible text (WCAG 2.5.3). -->
					<button class:with-avatar={me?.is_person} aria-label="{t('orga.pill')} · {t('orga.logout')}">
						<!-- One group, so the phone menu keeps the avatar beside the pill. -->
						<span class="who">
							{#if me?.is_person}
								<Avatar photo={smallPhoto} name={me} size={24} />
							{/if}
							<span class="pill">{t('orga.pill')}</span>
						</span>
						<span class="menu-text">{t('orga.logout')}</span>
					</button>
				</form>
			{:else if me}
				<!-- A logged-in player: the way to their own profile, and the way out beside it. -->
				<div class="account">
					{#if me.is_person}
						<a class="who" href="/players/{me.id}" aria-label={accountName}>
							<Avatar photo={smallPhoto} name={me} size={24} />
							<span class="name">{me.first_name || t('account.profile')}</span>
						</a>
					{:else}
						<!-- No active player row any more, so no profile page to link to. -->
						<span class="who">
							<Avatar photo={smallPhoto} name={me} size={24} />
							<span class="name">{me.first_name}</span>
						</span>
					{/if}
					<!-- The same plain POST as the ORGA pill. -->
					<form method="POST" action="/logout">
						<input type="hidden" name="redirectTo" value={here} />
						<button class="round logout" aria-label={t('account.logout')}>
							<svg viewBox="0 0 24 24" aria-hidden="true">
								<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
							</svg>
							<span class="menu-text">{t('account.logout')}</span>
						</button>
					</form>
				</div>
			{:else}
				<!-- Same slot as the pills: a visitor gets the way in, anyone logged in the way out. -->
				<a class="login" href="/login">{t('header.login')}</a>
			{/if}
			<!-- A plain POST (no use:enhance): the redirect reloads the page in the new language. -->
			<form method="POST" action="/lang" class="lang" aria-label={t('header.language')}>
				<input type="hidden" name="redirectTo" value={here} />
				<!-- The menu's row label; the form already carries the name. -->
				<span class="menu-label" aria-hidden="true">{t('header.language')}</span>
				<span class="pill">
					<button name="lang" value="fr" aria-current={locale === 'fr' ? 'true' : undefined}>FR</button>
					<button name="lang" value="en" aria-current={locale === 'en' ? 'true' : undefined}>EN</button>
				</span>
			</form>
			<!-- A plain POST like the language switch. Only the browser knows which theme is on
			     screen and which one the device prefers, so every switch is rendered and the
			     stylesheet shows the right one (see SWITCHES). -->
			<form method="POST" action="/theme" class="theme" aria-label={t('header.theme')}>
				<input type="hidden" name="redirectTo" value={here} />
				<span class="menu-label" aria-hidden="true">{t('header.theme')}</span>
				{#each SWITCHES as { to, value }}
					<button
						class="round"
						class:to-light={to === 'light'}
						class:to-dark={to === 'dark'}
						class:device={value === 'system'}
						name="theme"
						{value}
						aria-label={t(to === 'light' ? 'header.toLight' : 'header.toDark')}
					>
						<svg viewBox="0 0 24 24" aria-hidden="true">
							{#if to === 'light'}
								<circle cx="12" cy="12" r="4" />
								<path
									d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
								/>
							{:else}
								<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
							{/if}
						</svg>
						<span class="menu-text">{t(to === 'light' ? 'header.light' : 'header.dark')}</span>
					</button>
				{/each}
			</form>
		</div>
	</div>

	<nav aria-label={t('nav.sections')}>
		<ul>
			{#if year}
				{#each tabs as tab}
					<li>
						{#if tab.external}
							<a href={tab.url} target="_blank" rel="noopener">{tab.name}</a>
						{:else}
							<a
								href={tab.url}
								aria-current={[tab.url, tab.also].some((u) => u && $page.url.pathname.startsWith(u))
									? 'page'
									: undefined}
							>
								{tab.name}
							</a>
						{/if}
					</li>
				{/each}
			{/if}
		</ul>
	</nav>
</header>

<style>
	header {
		display: flex;
		z-index: 10;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 12px 18px;
		border-bottom: 1px solid var(--line);
	}

	.logo {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		/* Lets a long first name in the account pill shrink to an ellipsis rather than overflow
		   the bar (at 600px, or at 1000px beside the tabs): every other control keeps its width. */
		min-width: 0;
	}

	.logo a {
		display: flex;
		align-items: center;
	}

	.logo img {
		height: 2.2rem;
		object-fit: contain;
	}

	select {
		background: transparent;
		color: var(--accent);
		border: 1px solid var(--accent);
		border-radius: var(--radius-pill);
		/* Stays in the phone top bar beside the menu button: keep a 44px touch target. */
		min-height: 44px;
		padding: 0.15em 0.9em;
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		cursor: pointer;
	}

	/* The option list is the browser's own popup: its system colours follow the theme's color-scheme. */
	select option {
		color: CanvasText;
		background-color: Canvas;
	}

	/* Only below 600px, where the menu button folds the settings into a panel. */
	.menu-toggle,
	.menu-label,
	.menu-text {
		display: none;
	}

	/* Inline in the bar: the controls lay out as if the wrapper were not there. */
	.settings {
		display: contents;
	}

	.lang {
		display: flex;
		margin: 0;
	}

	.lang .pill {
		display: flex;
		border: 1px solid var(--accent);
		border-radius: var(--radius-pill);
		overflow: hidden;
		/* Same height as the year select beside it, border included. */
		min-height: 44px;
	}

	.lang button {
		background: transparent;
		border: 0;
		color: var(--muted);
		padding: 0 0.9em;
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		cursor: pointer;
	}

	.lang button[aria-current='true'] {
		color: var(--accent);
		background: var(--bg-raised);
		cursor: default;
	}

	/* Round the outer ends so the focus ring follows the pill instead of being clipped. */
	.lang button:first-child {
		border-radius: var(--radius-pill) 0 0 var(--radius-pill);
	}

	.lang button:last-child {
		border-radius: 0 var(--radius-pill) var(--radius-pill) 0;
	}

	.lang button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -3px;
	}

	.orga {
		margin: 0;
	}

	.orga button {
		min-height: 44px;
		padding: 0 0.9em;
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		border-radius: var(--radius-pill);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		cursor: pointer;
	}

	.orga button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	/* The avatar sits in the rim: 10px round a 24px avatar in a 44px pill. */
	.orga button.with-avatar {
		padding-left: 9px;
	}

	.who {
		display: inline-flex;
		align-items: center;
		gap: 0.45em;
	}

	/* A logged-in player: avatar and first name, quiet like the login pill, then the round
	   logout button. */
	.account {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		min-width: 0;
	}

	.account form {
		margin: 0;
	}

	.account .who {
		min-width: 0;
		min-height: 44px;
		padding: 0 0.9em 0 9px;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius-pill);
		color: var(--text);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		text-decoration: none;
	}

	.account a.who:hover {
		color: var(--accent);
		border-color: var(--accent);
		text-decoration: none;
	}

	.account a.who:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.name {
		min-width: 0;
		max-width: 10em;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.logout {
		display: flex;
	}

	.login {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		padding: 0 0.9em;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius-pill);
		color: var(--muted);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		text-decoration: none;
	}

	.login:hover {
		color: var(--accent);
		border-color: var(--accent);
		text-decoration: none;
	}

	.login:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	/* The header's round icon buttons, menu and theme: quiet like the login pill. Neither
	   sets `display` here: the menu button has its own, the theme switches take theirs
	   from the theme tokens. */
	.round {
		align-items: center;
		justify-content: center;
		flex: none;
		gap: 0.5em;
		width: 44px;
		height: 44px;
		padding: 0;
		background: transparent;
		color: var(--muted);
		border: 1px solid var(--line-strong);
		border-radius: 50%;
		cursor: pointer;
	}

	.round:hover,
	.menu-toggle[aria-expanded='true'] {
		color: var(--accent);
		border-color: var(--accent);
	}

	.round:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.round svg {
		width: 20px;
		height: 20px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.theme {
		margin: 0;
	}

	/* The hub stays dark whatever the choice, so it offers no switch. */
	:global(:root:has([data-always-dark])) .theme {
		display: none;
	}

	.theme .to-light {
		display: var(--switch-to-light);
	}

	.theme .to-dark {
		display: var(--switch-to-dark);
	}

	/* The device's own theme is dark unless it prefers light. The switch leading there is
	   the one posting `system`; the other direction stores a choice. */
	@media not all and (prefers-color-scheme: light) {
		.theme .to-light.device,
		.theme .to-dark:not(.device) {
			display: none;
		}
	}

	@media (prefers-color-scheme: light) {
		.theme .to-light:not(.device),
		.theme .to-dark.device {
			display: none;
		}
	}

	nav {
		display: flex;
		justify-content: center;
		view-transition-name: navbar;
	}

	ul {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0;
		margin: 0;
	}

	nav a {
		display: block;
		padding: 0.2em 1.1em;
		color: var(--muted);
		font-family: var(--font-display);
		font-size: 1.1rem;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		text-decoration: none;
	}

	nav a:hover {
		color: var(--accent);
		text-decoration: none;
	}

	a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	select:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	a[aria-current='page'] {
		color: var(--accent);
	}

	/* The tab bar takes over on phones: hide the whole landmark, not just its list. */
	@media (max-width: 999.98px) {
		nav {
			display: none;
		}
	}

	/* Phones: the bar keeps the logo, the year and the menu button; the account, language
	   and theme controls open as a panel under it, one labelled row each. */
	@media (max-width: 599.98px) {
		header {
			position: relative;
			padding: 10px 12px;
		}

		/* The left cluster spans the bar, so the menu button sits at its right end. */
		.logo {
			flex: 1;
			gap: 0.5rem;
		}

		.menu-toggle {
			display: flex;
			margin-left: auto;
		}

		.settings {
			display: none;
		}

		.settings.open {
			display: flex;
			flex-direction: column;
			position: absolute;
			top: 100%;
			left: 0;
			right: 0;
			padding: 0 16px;
			background: var(--bg-raised);
			border-bottom: 1px solid var(--line);
		}

		.settings > * {
			display: flex;
			align-items: center;
			justify-content: space-between;
			gap: 1rem;
			min-height: 60px;
		}

		.settings > * + * {
			border-top: 1px solid var(--line);
		}

		.menu-label {
			display: inline;
			font-weight: 600;
			font-size: 0.75rem;
			letter-spacing: 0.1em;
			text-transform: uppercase;
			color: var(--muted);
		}

		.menu-text {
			display: inline;
		}

		/* The panel is --bg-raised, the inline current segment's own fill: swap to the page's. */
		.lang button[aria-current='true'] {
			background: var(--bg);
		}

		/* The whole row is the link. */
		.login {
			padding: 0;
			border: 0;
			border-radius: 0;
			color: var(--accent);
		}

		/* The whole row is the button: the ORGA pill on the left, the action on the right. */
		.orga button,
		.orga button.with-avatar {
			flex: 1;
			display: flex;
			align-items: center;
			justify-content: space-between;
			padding: 0;
			background: transparent;
			color: var(--accent);
			border: 0;
			border-radius: 0;
		}

		/* The account row: the profile link on the left, like the login row, the logout
		   button on the right. */
		.account .who {
			padding: 0;
			border: 0;
			border-radius: 0;
			color: var(--accent);
		}

		.orga .pill {
			padding: 0.15em 0.8em;
			background: var(--accent);
			color: var(--bg);
			border-radius: var(--radius-pill);
		}

		/* A pill naming the theme it leads to, or the logout, beside its icon. */
		.theme button,
		.account .logout {
			width: auto;
			padding: 0 1em;
			border-radius: var(--radius-pill);
			font-family: var(--font-display);
			font-size: 1.1rem;
			letter-spacing: 0.08em;
		}
	}

	/* Without :has() styles.css never leaves the dark theme: a switch would do nothing. Last in
	   the sheet so it also beats the menu's row rule. */
	@supports not selector(:has(a)) {
		.theme {
			display: none;
		}
	}
</style>
