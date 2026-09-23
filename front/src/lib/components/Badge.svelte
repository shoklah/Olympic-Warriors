<script>
	import { badgeGlyph, badgeMetal, isTiered } from '$lib/badges';

	/** A badge of the profile payload: { code, tier, years, discipline, partner }. */
	export let badge;

	$: metal = badgeMetal(badge);
	$: tiered = isTiered(badge.code);
</script>

<!-- Purely visual: the tile around it writes the name and, for a tiered badge, the tier. -->
<span class="badge {metal}" data-metal={metal} aria-hidden="true">
	<span class="medal"><img src={badgeGlyph(badge)} alt="" /></span>
	{#if tiered}
		<span class="pips">
			{#each [1, 2, 3] as n}
				<span class="pip" class:on={n <= badge.tier}></span>
			{/each}
		</span>
	{/if}
</span>

<style>
	/* `--badge-size` lets a page scale the medallion, as `--medal-size` does for MedalRank. */
	.badge {
		--size: var(--badge-size, 56px);
		display: inline-flex;
		flex-direction: column;
		align-items: center;
		gap: calc(var(--size) * 0.08);
	}

	.gold {
		--metal: var(--gold);
	}

	.silver {
		--metal: var(--silver);
	}

	.bronze {
		--metal: var(--bronze);
	}

	.plain {
		--metal: var(--accent);
	}

	.medal {
		position: relative;
		display: grid;
		place-items: center;
		width: var(--size);
		height: var(--size);
		border: max(2px, calc(var(--size) * 0.04)) solid var(--metal);
		border-radius: 50%;
	}

	/* The hairline inner ring, like a medal's rim. */
	.medal::after {
		content: '';
		position: absolute;
		inset: calc(var(--size) * 0.055);
		border: 1px solid var(--metal);
		border-radius: 50%;
		opacity: 0.35;
	}

	img {
		width: 60%;
		height: 60%;
	}

	.pips {
		display: flex;
		gap: calc(var(--size) * 0.06);
	}

	.pip {
		width: max(5px, calc(var(--size) * 0.07));
		aspect-ratio: 1;
		border-radius: 50%;
		background: var(--line);
	}

	.pip.on {
		background: var(--metal);
	}
</style>
