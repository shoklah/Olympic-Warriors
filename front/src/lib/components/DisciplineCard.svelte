<script>
	import { iconFor } from '$lib/icons';

	/** Where the card leads. */
	export let href;
	/** The database discipline name, for the icon. */
	export let discipline;
	/** The name shown, already translated. */
	export let name;
	/** The small line under the name. */
	export let subtitle = '';
	/**
	 * The link's accessible name, the shown name when null: the whole card is the link, so the
	 * name is pinned rather than read with the subtitle. Resolved on render, not as a prop
	 * default, which would keep the first name when an each block reuses the card.
	 */
	export let label = null;
	/** A discipline whose scores are hidden: only its icon dims, it stays reachable. */
	export let unrevealed = false;
</script>

<a class="card" class:unrevealed {href} aria-label={label ?? name} {...$$restProps}>
	<span class="icon">
		<img src={iconFor(discipline)} alt="" />
	</span>
	<span class="text">
		<span class="name">{name}</span>
		<span class="label subtitle">{subtitle}</span>
	</span>
</a>

<style>
	.card {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--text);
		text-decoration: none;
		transition:
			transform 0.2s ease,
			background 0.2s ease;
	}

	.card:hover {
		background: var(--line);
		transform: translateY(-2px);
		text-decoration: none;
	}

	.card:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	.icon {
		flex: none;
		display: flex;
		align-items: center;
		justify-content: center;
		height: 44px;
		width: 44px;
		border-radius: var(--radius);
		background: var(--bg-sunken);
		border: 1px solid var(--line);
	}

	.icon img {
		height: 76%;
		width: 76%;
		filter: var(--icon-filter);
	}

	/* Only the tile dims: the name and the subtitle stay readable. */
	.unrevealed .icon {
		opacity: 0.35;
	}

	.text {
		min-width: 0;
	}

	.name {
		display: block;
		font-family: var(--font-display);
		font-size: 1.4rem;
		letter-spacing: 0.06em;
		line-height: 1;
		color: var(--ink);
		overflow-wrap: anywhere;
	}

	.subtitle {
		display: block;
		margin-top: 4px;
	}
</style>
