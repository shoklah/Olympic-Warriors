<script>
	/**
	 * Trail of the current page, root first. The last item is the current page
	 * and is never a link, whether or not it carries a href.
	 * @type {{label: string, href?: string}[]}
	 */
	export let items = [];
</script>

<nav class="breadcrumb label" aria-label="Breadcrumb">
	{#each items as item, i}
		{#if i > 0}
			<span class="separator" aria-hidden="true">{' › '}</span>
		{/if}
		{#if item.href && i < items.length - 1}
			<a href={item.href}>{item.label}</a>
		{:else}
			<span class="current">{item.label}</span>
		{/if}
	{/each}
</nav>

<style>
	.breadcrumb {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		margin: 1.4rem 0 0.6rem;
	}

	a {
		color: var(--muted);
		text-decoration: none;
	}

	a:hover {
		color: var(--accent);
		text-decoration: none;
	}

	a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	.separator {
		color: var(--ghost);
	}

	.current {
		color: var(--accent);
	}
</style>
