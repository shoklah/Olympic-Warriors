<script>
	import { page } from '$app/stores';
	import { afterNavigate, goto } from '$app/navigation';
	import logo from '$lib/img/logo.svg';
	import { switchYearPath } from '$lib/edition';
	import { useLocale, useT } from '$lib/i18n';
	import { useOrganiser } from '$lib/session';

	const locale = useLocale();
	const t = useT();
	const organiser = useOrganiser();

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
			class="menu-toggle"
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
					<input type="hidden" name="redirectTo" value={$page.url.pathname + $page.url.search} />
					<!-- The accessible name must contain the visible text (WCAG 2.5.3). -->
					<button aria-label="{t('orga.pill')} · {t('orga.logout')}">
						<span class="pill">{t('orga.pill')}</span>
						<span class="menu-text">{t('orga.logout')}</span>
					</button>
				</form>
			{:else}
				<!-- Same slot as the pill: a visitor gets the way in, an organiser the way out. -->
				<a class="login" href="/login">{t('header.login')}</a>
			{/if}
			<!-- A plain POST (no use:enhance): the redirect reloads the page in the new language. -->
			<form method="POST" action="/lang" class="lang" aria-label={t('header.language')}>
				<input type="hidden" name="redirectTo" value={$page.url.pathname + $page.url.search} />
				<!-- The menu's row label; the form already carries the name. -->
				<span class="menu-label" aria-hidden="true">{t('header.language')}</span>
				<span class="pill">
					<button name="lang" value="fr" aria-current={locale === 'fr' ? 'true' : undefined}>FR</button>
					<button name="lang" value="en" aria-current={locale === 'en' ? 'true' : undefined}>EN</button>
				</span>
			</form>
			<!-- A plain POST like the language switch. Only the browser knows which theme is on
			     screen while the device setting decides, so both buttons are rendered and
			     styles.css shows the one leading away from it. -->
			<form method="POST" action="/theme" class="theme" aria-label={t('header.theme')}>
				<input type="hidden" name="redirectTo" value={$page.url.pathname + $page.url.search} />
				<span class="menu-label" aria-hidden="true">{t('header.theme')}</span>
				<button class="to-light" name="theme" value="light" aria-label={t('header.toLight')}>
					<svg viewBox="0 0 24 24" aria-hidden="true">
						<circle cx="12" cy="12" r="4" />
						<path
							d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
						/>
					</svg>
					<span class="menu-text">{t('header.light')}</span>
				</button>
				<button class="to-dark" name="theme" value="dark" aria-label={t('header.toDark')}>
					<svg viewBox="0 0 24 24" aria-hidden="true">
						<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
					</svg>
					<span class="menu-text">{t('header.dark')}</span>
				</button>
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

	.theme {
		margin: 0;
	}

	/* The hub stays dark whatever the choice, so it offers no switch. */
	:global(:root:has([data-always-dark])) .theme {
		display: none;
	}

	/* Round and quiet like the login pill; `display` comes from the theme tokens. */
	.theme button {
		align-items: center;
		justify-content: center;
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

	.theme .to-light {
		display: var(--switch-to-light);
	}

	.theme .to-dark {
		display: var(--switch-to-dark);
	}

	.theme button:hover {
		color: var(--accent);
		border-color: var(--accent);
	}

	.theme button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.menu-toggle {
		align-items: center;
		justify-content: center;
		flex: none;
		width: 44px;
		height: 44px;
		padding: 0;
		background: transparent;
		color: var(--muted);
		border: 1px solid var(--line-strong);
		border-radius: 50%;
		cursor: pointer;
	}

	.menu-toggle:hover,
	.menu-toggle[aria-expanded='true'] {
		color: var(--accent);
		border-color: var(--accent);
	}

	.menu-toggle:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.menu-toggle svg,
	.theme svg {
		width: 20px;
		height: 20px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
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
		.orga button {
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

		.orga .pill {
			padding: 0.15em 0.8em;
			background: var(--accent);
			color: var(--bg);
			border-radius: var(--radius-pill);
		}

		/* A pill naming the theme it leads to, beside its icon. */
		.theme button {
			width: auto;
			padding: 0 1em;
			border-radius: var(--radius-pill);
			font-family: var(--font-display);
			font-size: 1.1rem;
			letter-spacing: 0.08em;
		}
	}
</style>
