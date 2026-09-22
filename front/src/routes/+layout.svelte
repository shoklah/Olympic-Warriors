<script>
	import Header from '$lib/components/Header.svelte';
	import TabBar from '$lib/components/TabBar.svelte';
	import './styles.css';
	import { onNavigate } from '$app/navigation';
	import { page } from '$app/stores';

	// The hub and the login page carry no section, so they get no bottom tab bar.
	const HUB_OR_LOGIN = new Set(['/', '/[year=year]', '/login']);

	$: showTabBar = !HUB_OR_LOGIN.has($page.route.id);
	// On an error page the year in the URL may be one with no edition, so fall back to the latest.
	$: year = ($page.error ? null : $page.params.year) ?? $page.data.latestYear;
	$: photosUrl =
		($page.data.editions ?? []).find((e) => e.year === Number(year))?.photos_url ?? null;

	onNavigate((navigation) => {
		if (!document.startViewTransition) return;

		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await navigation.complete;
			});
		});
	});
</script>

<div class="app" class:has-tabbar={showTabBar}>
	<Header />

	<main>
		<slot />
	</main>

	{#if showTabBar}
		<TabBar {year} pathname={$page.url.pathname} {photosUrl} />
	{/if}
</div>

<style>
	.app {
		position: relative;
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		min-height: 100dvh;
	}

	main {
		flex: 1;
		display: flex;
		flex-direction: column;
		width: 100%;
		margin: 0;
	}
</style>
