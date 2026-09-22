<script>
	import { iconFor } from '$lib/icons';
	import { rankedTeams } from '$lib/edition';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';

	export let data;

	$: year = data.summary.edition.year;
	$: teams = rankedTeams(data.summary);
	$: disciplines = data.summary.disciplines;
</script>

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: 'Ranking' }]} />
	<h1>Ranking</h1>

	<div class="columns">
		<nav id="disciplines" aria-label="Disciplines">
			{#each disciplines as discipline}
				<a
					class="discipline-tile"
					class:dimmed={!discipline.reveal_score}
					href="/{year}/disciplines/{discipline.id}"
					aria-disabled={discipline.reveal_score ? undefined : 'true'}
					tabindex={discipline.reveal_score ? undefined : -1}
					aria-label={discipline.name}
				>
					<img src={iconFor(discipline.name)} alt="" />
				</a>
			{/each}
		</nav>

		<div id="teams">
			{#each teams as team}
				<a
					class="team-row"
					class:gold={team.ranking === 1}
					class:silver={team.ranking === 2}
					class:bronze={team.ranking === 3}
					data-testid="team-row"
					href="/{year}/teams/{team.id}"
				>
					<MedalRank rank={team.ranking} />
					<span class="name">{team.name}</span>
					<span class="num pts">{team.total_points} pts</span>
				</a>
			{/each}
		</div>
	</div>
</div>

<style>
	h1 {
		margin: 0 0 0.8rem;
	}

	.columns {
		display: flex;
		flex-direction: column;
		gap: 14px;
		margin-bottom: 2rem;
	}

	#disciplines {
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

	#disciplines::-webkit-scrollbar {
		display: none;
	}

	.discipline-tile {
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

	.discipline-tile:not(.dimmed) {
		border-color: var(--accent);
	}

	.discipline-tile img {
		height: 76%;
		width: 76%;
	}

	.discipline-tile:not(.dimmed):hover {
		background: var(--line-strong);
		transform: translateY(-2px);
	}

	.discipline-tile:focus-visible,
	.team-row:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	#teams {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.team-row {
		display: grid;
		grid-template-columns: 44px minmax(0, 1fr) auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.9rem;
		padding: 10px 12px;
		background: var(--bg-raised);
		border-radius: var(--radius);
		border-left: 4px solid var(--line-strong);
		color: var(--text);
		text-decoration: none;
		transition: background 0.2s ease;
	}

	.team-row:hover {
		background: var(--line);
		text-decoration: none;
	}

	.team-row.gold {
		border-left-color: var(--gold);
	}

	.team-row.silver {
		border-left-color: var(--silver);
	}

	.team-row.bronze {
		border-left-color: var(--bronze);
	}

	.name {
		font-weight: 600;
		font-size: 1rem;
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.pts {
		font-size: 1.6rem;
		line-height: 1;
		letter-spacing: 0.06em;
	}

	@media (min-width: 1000px) {
		.columns {
			flex-direction: row;
			align-items: flex-start;
			gap: 20px;
		}

		#teams {
			order: 1;
			flex: 1;
		}

		#disciplines {
			order: 2;
			flex-direction: column;
			gap: 8px;
			overflow: visible;
		}
	}
</style>
