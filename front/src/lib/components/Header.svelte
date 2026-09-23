<script>
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
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
				...(edition?.photos_url
					? [{ name: t('nav.photos'), url: edition.photos_url, external: true }]
					: [])
			]
		: [];

	const switchYear = (event) => goto(switchYearPath($page.url.pathname, event.target.value));
</script>

<header>
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
		{#if organiser}
			<!-- A plain POST like the language switch: the redirect reloads the page as a visitor. -->
			<form method="POST" action="/logout" class="orga" aria-label={t('orga.logout')}>
				<input type="hidden" name="redirectTo" value={$page.url.pathname + $page.url.search} />
				<!-- One tap logs out; the accessible name says so, the visible text stays the short pill. -->
				<button aria-label={t('orga.logout')}>{t('orga.pill')}</button>
			</form>
		{/if}
		<!-- A plain POST (no use:enhance): the redirect reloads the page in the new language. -->
		<form method="POST" action="/lang" class="lang" aria-label={t('header.language')}>
			<input type="hidden" name="redirectTo" value={$page.url.pathname + $page.url.search} />
			<button name="lang" value="fr" aria-current={locale === 'fr' ? 'true' : undefined}>FR</button>
			<button name="lang" value="en" aria-current={locale === 'en' ? 'true' : undefined}>EN</button>
		</form>
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
		/* The only control in the phone top bar: keep a 44px touch target. */
		min-height: 44px;
		padding: 0.15em 0.9em;
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		cursor: pointer;
	}

	select option {
		color: black;
	}

	.lang {
		display: flex;
		margin: 0;
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
</style>
