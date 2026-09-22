<script>
	import { useT } from '$lib/i18n';

	/**
	 * Year of the edition the tabs point at; nothing renders without one.
	 * @type {number | string | null}
	 */
	export let year = null;
	/** Current pathname, used to mark the active section. */
	export let pathname = '';
	/** External album of the edition, when it has one. */
	export let photosUrl = null;

	const t = useT();

	$: current = Number(year);
	$: visible = year !== null && year !== undefined && !Number.isNaN(current);
	$: items = visible
		? [
				{ name: t('nav.ranking'), url: `/${current}/ranking` },
				{ name: t('nav.teams'), url: `/${current}/teams` },
				{ name: t('nav.disciplines'), url: `/${current}/disciplines` },
				...(photosUrl ? [{ name: t('nav.photos'), url: photosUrl, external: true }] : [])
			]
		: [];
</script>

{#if visible}
	<nav class="tabbar" aria-label={t('nav.sections')}>
		{#each items as item}
			{#if item.external}
				<a href={item.url} target="_blank" rel="noopener">
					<span class="icon" aria-hidden="true"></span>
					<span class="name">{item.name}</span>
				</a>
			{:else}
				<a
					href={item.url}
					aria-current={pathname.startsWith(item.url) ? 'page' : undefined}
				>
					<span class="icon" aria-hidden="true"></span>
					<span class="name">{item.name}</span>
				</a>
			{/if}
		{/each}
	</nav>
{/if}

<style>
	.tabbar {
		position: fixed;
		z-index: 20;
		bottom: 0;
		left: 0;
		right: 0;
		height: var(--tabbar);
		display: flex;
		align-items: center;
		background: var(--bg-raised);
		border-top: 1px solid var(--line);
	}

	a {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 4px;
		height: 100%;
		color: var(--muted);
		text-decoration: none;
	}

	a:hover {
		text-decoration: none;
	}

	a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	a[aria-current='page'] {
		color: var(--accent);
	}

	.icon {
		width: 18px;
		height: 18px;
		border: 2px solid currentColor;
		border-radius: 3px;
	}

	.name {
		font-family: var(--font-display);
		font-size: 0.95rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		line-height: 1;
	}

	@media (min-width: 1000px) {
		.tabbar {
			display: none;
		}
	}
</style>
