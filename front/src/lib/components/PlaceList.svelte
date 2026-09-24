<script>
	import { spokenPlaces } from '$lib/players';
	import { useLocale } from '$lib/i18n';

	/** Places best first, each {year, rank}: a coloured rank and its year, as the profile's
	    « Par épreuve » rows and the discipline all-time rows show them. */
	export let places;

	const locale = useLocale();
</script>

<!-- The figures are hidden from screen readers, which read the sentence instead. Both
     spans sit directly in the row's grid; the hidden one is taken out of the flow. -->
<span class="places" aria-hidden="true">
	{#each places as place}
		<span class="place"
			><span
				class="num place-rank"
				class:gold={place.rank === 1}
				class:silver={place.rank === 2}
				class:bronze={place.rank === 3}>{place.rank}</span
			>
			<span class="place-year">{place.year}</span></span
		>{' '}
	{/each}
</span>
<span class="visually-hidden">{spokenPlaces(places, locale)}</span>

<style>
	.places {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: flex-end;
		gap: 4px 10px;
		justify-self: end;
	}

	.place {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
	}

	.place-rank {
		font-size: 1.15rem;
		line-height: 1.1;
		letter-spacing: 0.04em;
		color: var(--muted);
	}

	.place-rank.gold {
		color: var(--gold);
	}

	.place-rank.silver {
		color: var(--silver);
	}

	.place-rank.bronze {
		color: var(--bronze);
	}

	.place-year {
		font-size: 0.75rem;
		color: var(--muted);
	}
</style>
