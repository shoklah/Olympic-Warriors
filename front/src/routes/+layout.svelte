<script>
	import Header from './Header.svelte';
	import Footer from './Footer.svelte';
	import './styles.css';
	import { onNavigate } from "$app/navigation";

	onNavigate((navigation) => {
		if (!document.startViewTransition) return;

		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve()
				await navigation.complete
			})
		});
	});
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
