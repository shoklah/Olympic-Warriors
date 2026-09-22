<script>
	import { ordinal as toOrdinal } from '$lib/edition';
	import { useLocale } from '$lib/i18n';

	/**
	 * Rank of a team; null or 0 (the API's unrevealed value) renders as a dash.
	 * @type {number | null}
	 */
	export let rank = null;
	/** Render `2nd` (`2e` in French) instead of `2`. */
	export let ordinal = false;

	const locale = useLocale();
	const MEDALS = { 1: 'gold', 2: 'silver', 3: 'bronze' };

	$: unranked = rank === null || rank === 0;
	$: medal = MEDALS[rank] ?? 'none';
	$: text = unranked ? '—' : ordinal ? toOrdinal(rank, locale) : `${rank}`;
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
