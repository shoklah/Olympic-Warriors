<script>
	import { page } from '$app/stores';
</script>

<section>
	<h1>{$page.status}</h1>
	<p>{$page.error?.message ?? 'Something went wrong'}</p>
	<a href="/">Back to the Olympic Warriors</a>
</section>

<style>
	section {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		margin: 6rem 1rem;
		color: var(--color-theme-1);
		text-align: center;
	}

	h1 {
		font-size: 4rem;
		margin: 0;
	}

	a {
		color: var(--color-bg-0);
		background-color: var(--color-theme-1);
		padding: 0.6rem 2rem;
		border-radius: 2em;
		font-weight: 700;
	}
</style>
