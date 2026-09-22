<script>
	import { ordinal as toOrdinal } from '$lib/edition';

	/**
	 * Rank of a team, or null when it has none yet (rendered as a dash).
	 * @type {number | null}
	 */
	export let rank = null;
	/** Render `2nd` instead of `2`. */
	export let ordinal = false;

	const MEDALS = { 1: 'gold', 2: 'silver', 3: 'bronze' };

	$: medal = MEDALS[rank] ?? 'none';
	$: text = rank === null ? '—' : ordinal ? toOrdinal(rank) : `${rank}`;
</script>

<span class="rank num {medal}">{text}</span>

<style>
	/* `--medal-size` lets a page scale the glyph without reaching into this component. */
	.rank {
		font-size: var(--medal-size, 1.3rem);
		line-height: 1;
		letter-spacing: 0.04em;
	}

	.gold {
		color: var(--gold);
	}

	.silver {
		color: var(--silver);
	}

	.bronze {
		color: var(--bronze);
	}

	.none {
		color: var(--faint);
	}
</style>
