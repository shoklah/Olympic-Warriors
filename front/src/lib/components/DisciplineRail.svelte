<script>
	import { iconFor } from '$lib/icons';
	import { disciplineName, useLocale, useT } from '$lib/i18n';

	export let year;
	export let disciplines;
	/** Id of the discipline whose page is showing, or null on the ranking page. */
	export let currentId = null;

	const locale = useLocale();
	const t = useT();
</script>

<nav aria-label={t('nav.disciplines')}>
	{#each disciplines as discipline}
		<a
			class="tile"
			class:unrevealed={!discipline.reveal_score}
			class:current={discipline.id === currentId}
			href="/{year}/disciplines/{discipline.id}"
			aria-current={discipline.id === currentId ? 'page' : undefined}
			aria-label={disciplineName(locale, discipline.name)}
		>
			<img src={iconFor(discipline.name)} alt="" />
		</a>
	{/each}
</nav>

<style>
	nav {
		display: flex;
		gap: 8px;
		overflow-x: auto;
		overflow-y: hidden;
		scroll-snap-type: x proximity;
		/* Room for the 2px hover lift, which `overflow-y: hidden` would clip. */
		padding-top: 2px;
		margin-top: -2px;
		-ms-overflow-style: none;
		scrollbar-width: none;
	}

	nav::-webkit-scrollbar {
		display: none;
	}

	.tile {
		flex: none;
		height: 44px;
		width: 44px;
		border-radius: var(--radius);
		background: var(--bg-raised);
		border: 1px solid var(--line);
		display: flex;
		align-items: center;
		justify-content: center;
		scroll-snap-align: start;
		transition:
			transform 0.2s ease,
			background 0.2s ease;
	}

	.tile:not(.unrevealed) {
		border-color: var(--accent);
	}

	/* Same rule as the disciplines grid: dimmed, but still a link to the pairings. */
	.tile.unrevealed {
		opacity: 0.35;
	}

	.tile img {
		height: 76%;
		width: 76%;
	}

	.tile:not(.current):hover {
		background: var(--line-strong);
		transform: translateY(-2px);
	}

	/* The icons are white SVGs, so the accent-filled current tile inverts them. */
	.tile.current {
		background: var(--accent);
		border-color: var(--accent);
	}

	.tile.current img {
		filter: invert(1);
	}

	.tile:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
</style>
