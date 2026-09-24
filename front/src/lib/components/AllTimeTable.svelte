<script>
	import MedalRank from '$lib/components/MedalRank.svelte';
	import PlaceList from '$lib/components/PlaceList.svelte';
	import { fullName, listYears } from '$lib/players';
	import { useLocale, useT } from '$lib/i18n';

	/** The discipline's all-time table, as /discipline/<id>/all-time/ returns it:
	    {name, years, players: [{id, first_name, last_name, position, places}]}. */
	export let table;

	const locale = useLocale();
	const t = useT();

	$: players = table?.players ?? [];
	$: years = table?.years ?? [];
</script>

<h2 class="visually-hidden">{t('discipline.tab.allTime')}</h2>

{#if players.length === 0}
	<p class="empty">{t('discipline.allTime.empty')}</p>
{:else}
	<p class="years">{t('discipline.allTime.years', { n: years.length, years: listYears(years, locale) })}</p>
	<ol class="list" role="list">
		{#each players as player}
			<li>
				<a
					class="row"
					class:gold={player.position === 1}
					class:silver={player.position === 2}
					class:bronze={player.position === 3}
					href="/players/{player.id}"
					data-testid="all-time-row"
				>
					<MedalRank rank={player.position} />
					<span class="name">{fullName(player)}</span>
					<PlaceList places={player.places} />
				</a>
			</li>
		{/each}
	</ol>
{/if}

<style>
	.empty,
	.years {
		margin: 0 0 1rem;
		color: var(--muted);
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0 0 2rem;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		grid-template-columns: 44px minmax(0, 1fr) auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.9rem;
		padding: 10px 12px;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-left: 4px solid var(--line-strong);
		border-radius: var(--radius);
		color: var(--text);
		text-decoration: none;
		transition:
			transform 0.2s ease,
			background 0.2s ease;
	}

	.row:hover {
		background: var(--line);
		transform: translateY(-2px);
		text-decoration: none;
	}

	.row:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	.row.gold {
		border-left-color: var(--gold);
	}

	.row.silver {
		border-left-color: var(--silver);
	}

	.row.bronze {
		border-left-color: var(--bronze);
	}

	.name {
		min-width: 0;
		font-weight: 600;
		overflow-wrap: anywhere;
	}

</style>
