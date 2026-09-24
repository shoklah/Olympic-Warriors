<script>
	import { badgeGlyph, badgeMetal, badgeTier, isTiered } from '$lib/badges';

	/** A badge of the profile payload: { code, tier, years, discipline, partner }. */
	export let badge;
	/** A locked slot: dashed ring, dimmed glyph, no metal and no lit pip. */
	export let locked = false;

	$: metal = badgeMetal(badge);
	$: tiered = isTiered(badge.code);
	$: tier = badgeTier(badge);
</script>

<!-- Purely visual: the tile around it writes the name and, for a tiered badge, the tier. -->
<span class="badge {metal}" class:locked data-metal={metal} aria-hidden="true">
	<span class="medal"><img src={badgeGlyph(badge)} alt="" /></span>
	<!-- The pip row keeps its height on an untiered badge too, so that in a grid of tiles
	     every medallion takes the same room and the names below line up. -->
	<span class="pips">
		{#if tiered}
			{#each [1, 2, 3] as n}
				<span class="pip" class:on={!locked && n <= tier}></span>
			{/each}
		{/if}
	</span>
</span>

<style>
	/* `--badge-size` lets a page scale the medallion, as `--medal-size` does for MedalRank. */
	.badge {
		--size: var(--badge-size, 56px);
		--pip: max(5px, calc(var(--size) * 0.07));
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
		height: var(--pip);
	}

	.pip {
		width: var(--pip);
		aspect-ratio: 1;
		border-radius: 50%;
		background: var(--line);
	}

	.pip.on {
		background: var(--metal);
	}

	.locked .medal {
		border-style: dashed;
		border-color: var(--ghost);
	}

	.locked .medal::after {
		display: none;
	}

	.locked img {
		opacity: 0.35;
	}
</style>
