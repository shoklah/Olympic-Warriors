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
		color: var(--text);
		text-align: center;
	}

	h1 {
		font-size: 4rem;
		margin: 0;
	}

	a {
		background: var(--accent);
		color: var(--bg);
		font-family: var(--font-display);
		letter-spacing: 0.15em;
		padding: 0.6rem 2rem;
		border-radius: var(--radius);
		text-decoration: none;
		transition: 0.3s;
	}

	a:hover,
	a:focus-visible {
		opacity: 0.8;
	}
</style>
