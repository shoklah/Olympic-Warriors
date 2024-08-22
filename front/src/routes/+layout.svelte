<script>
	import Header from './Header.svelte';
	import Footer from './Footer.svelte';
	import './styles.css';
	import { onNavigate } from "$app/navigation";
	import { page } from '$app/stores';

	onNavigate((navigation) => {
		if (!document.startViewTransition) return;

		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve()
				await navigation.complete
			})
		});
	});

	$: {
		if (typeof document !== 'undefined'){
			if (document && $page.url.pathname === '/') {
				document.documentElement.style.setProperty('--color-bg-0', 'black');
				document.documentElement.style.setProperty('--color-theme-1', '#F9F3C1');
			} else {
				document.documentElement.style.setProperty('--color-bg-0', 'white');
				document.documentElement.style.setProperty('--color-theme-1', 'black');
			}
		}
	}

</script>

<div class="app">
	<Header />

	<main>
		<slot />
	</main>

<!--	<Footer />-->
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
