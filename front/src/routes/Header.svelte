<script>
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import logo from '$lib/img/logo.svg';
	import { switchYearPath } from '$lib/edition';
	import Menu from './menu.svelte';

	$: editions = $page.data.editions ?? [];
	$: year = Number($page.params.year ?? $page.data.latestYear);
	$: edition = editions.find((e) => e.year === year);
	$: tabs = [
		{ name: 'Ranking', url: `/${year}/ranking` },
		{ name: 'Teams', url: `/${year}/teams` },
		{ name: 'Disciplines', url: `/${year}/disciplines` },
		...(edition?.photos_url ? [{ name: 'Photos', url: edition.photos_url, external: true }] : [])
	];

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
					<option value={e.year}>{e.year}</option>
				{/each}
			</select>
		{/if}
	</div>

	<nav>
		<ul>
			{#each tabs as tab}
				<li aria-current={$page.url.pathname === tab.url ? 'page' : undefined}>
					{#if tab.external}
						<a href={tab.url} target="_blank" rel="noopener">{tab.name}</a>
					{:else}
						<a href={tab.url}>{tab.name}</a>
					{/if}
				</li>
			{/each}
		</ul>
	</nav>
	<Menu {tabs} {editions} {year} />
</header>

<style>
	header {
		display: flex;
		z-index: 10;
		padding: 2em clamp(0em, 2vw, 5em);
		justify-content: space-between;
	}

	.logo {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.logo a {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
	}

	.logo img {
		margin-left: 2vw;
		height: 3em;
		object-fit: contain;
	}

	select {
		background: transparent;
		color: var(--color-theme-1);
		border: 2px solid var(--color-theme-1);
		border-radius: 2em;
		padding: 0.3em 0.8em;
		font-weight: 700;
		font-size: 1rem;
		letter-spacing: 0.1em;
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

	nav a {
		display: flex;
		height: 90%;
		align-items: center;
		padding: 0 2em;
		color: var(--color-theme-1);
		font-weight: 700;
		font-size: 1rem;
		text-transform: uppercase;
		letter-spacing: 0.2em;
		text-decoration: none;
	}

	ul {
		display: flex;
		justify-content: center;
		align-items: center;
		padding: 0;
		margin: 0;
		height: 3em;
	}

	li {
		position: relative;
		height: 100%;
	}

	li[aria-current='page']::before {
		content: '';
		width: 30px;
		height: 3px;
		position: absolute;
		top: 0;
		left: calc(50% - 15px);
		background-color: var(--color-theme-1);
		view-transition-name: indicator;
	}

	a:hover {
		color: var(--color-theme-1);
	}

	@media (max-width: 1000px) {
		ul {
			display: none;
		}
	}
</style>
