<script>
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import logo from '$lib/img/logo.svg';
	import { switchYearPath } from '$lib/edition';

	$: editions = $page.data.editions ?? [];
	// On an error page the year in the URL may be one with no edition, so fall back to the latest.
	$: year = Number(($page.error ? null : $page.params.year) ?? $page.data.latestYear);
	$: edition = editions.find((e) => e.year === year);
	$: tabs = year
		? [
				{ name: 'Ranking', url: `/${year}/ranking` },
				{ name: 'Teams', url: `/${year}/teams` },
				{ name: 'Disciplines', url: `/${year}/disciplines` },
				...(edition?.photos_url
					? [{ name: 'Photos', url: edition.photos_url, external: true }]
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
			<select aria-label="Edition" value={year} on:change={switchYear}>
				{#each editions as e}
					<!-- Svelte 4 SSR ignores `value` on the select, so mark the option itself. -->
					<option value={e.year} selected={e.year === year}>{e.year}</option>
				{/each}
			</select>
		{/if}
	</div>

	<nav>
		<ul>
			{#if year}
				{#each tabs as tab}
					<li
						aria-current={!tab.external && $page.url.pathname.startsWith(tab.url)
							? 'page'
							: undefined}
					>
						{#if tab.external}
							<a href={tab.url} target="_blank" rel="noopener">{tab.name}</a>
						{:else}
							<a href={tab.url}>{tab.name}</a>
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
		padding: 0.15em 0.9em;
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.08em;
		cursor: pointer;
	}

	select option {
		color: black;
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

	li[aria-current='page'] a {
		color: var(--accent);
	}

	@media (max-width: 999px) {
		ul {
			display: none;
		}
	}
</style>
