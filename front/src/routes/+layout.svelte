<script>
	import Header from './Header.svelte';
	import './styles.css';
	import { onNavigate } from '$app/navigation';
	import { page } from '$app/stores';

	onNavigate((navigation) => {
		if (!document.startViewTransition) return;

		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await navigation.complete;
			});
		});
	});

	const HUB_ROUTES = new Set(['/', '/[year=year]']);
	$: isHub = HUB_ROUTES.has($page.route.id);

	$: if (typeof document !== 'undefined') {
		document.documentElement.style.setProperty('--color-bg-0', isHub ? 'black' : 'white');
		document.documentElement.style.setProperty('--color-theme-1', isHub ? '#F9F3C1' : 'black');
	}
</script>

<div class="app">
	<Header />

	<main>
		<slot />
	</main>
</div>

<style>
	.app {
		position: relative;
		display: flex;
		flex-direction: column;
		min-height: 100vh;
	}

	main {
		flex: 1;
		display: flex;
		flex-direction: column;
		width: 100%;
		margin: 0;
	}
</style>
