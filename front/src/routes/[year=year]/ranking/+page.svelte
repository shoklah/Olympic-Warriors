<script>
	import { iconFor } from '$lib/icons';
	import { rankedTeams } from '$lib/edition';

	export let data;

	$: year = data.summary.edition.year;
	$: teams = rankedTeams(data.summary);
	$: disciplines = data.summary.disciplines;
</script>

<div class="flex-box">
	<div id="disciplines">
		{#each disciplines as discipline}
			<a
				class="discipline-card"
				class:dimmed={!discipline.reveal_score}
				href="/{year}/disciplines/{discipline.id}"
				aria-disabled={discipline.reveal_score ? undefined : 'true'}
				tabindex={discipline.reveal_score ? undefined : -1}
				aria-label={discipline.name}
			>
				<img src={iconFor(discipline.name)} alt="" />
			</a>
		{/each}
	</div>

	<div id="teams">
		{#each teams as team}
			<a
				class="team-card"
				class:gold={team.ranking === 1}
				class:silver={team.ranking === 2}
				class:bronze={team.ranking === 3}
				data-testid="team-row"
				href="/{year}/teams/{team.id}"
			>
				<span>{team.ranking}. {team.name}</span>
				<p>{team.total_points} pts</p>
			</a>
		{/each}
	</div>
</div>

<style>
	.flex-box {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	#disciplines {
		display: flex;
		gap: clamp(5px, 3vw, 40px);
		margin: 0 clamp(10px, 4vw, 40px);
		overflow-x: auto;
		overflow-y: hidden;
		flex-wrap: nowrap;
		-ms-overflow-style: none;
		scrollbar-width: none;
	}

	#disciplines::-webkit-scrollbar {
		display: none;
	}

	.discipline-card {
		height: clamp(70px, 12vw, 100px);
		width: clamp(70px, 12vw, 100px);
		flex: none;
		border-radius: 50%;
		background-color: var(--color-theme-1);
		display: flex;
		justify-content: center;
		align-items: center;
		transition: 0.3s;
	}

	.discipline-card.dimmed {
		opacity: 0.2;
		pointer-events: none;
	}

	.discipline-card img {
		height: 80%;
		width: 80%;
	}

	.discipline-card:hover {
		transform: translate(0, -4px);
	}

	#teams {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0 1vw;
	}

	.team-card {
		background-color: var(--color-bg-0);
		border: 1px solid #ccc;
		border-radius: 10px;
		padding: 0 10px;
		box-shadow: 0 2px 4px #00000030;
		transition: 0.3s;
		display: flex;
		justify-content: space-between;
		align-items: center;
		text-decoration: none;
	}

	.team-card span,
	.team-card p {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-theme-1);
		margin: 1em 0;
	}

	.team-card.gold {
		background: linear-gradient(45deg, #e6b800, #f2d06b, #e6b800, #e6ac00);
	}

	.team-card.silver {
		background: linear-gradient(45deg, #e0e0e0, #cfcfcf, #b0b0b0, #d1d1d1, #f7f7f7);
	}

	.team-card.bronze {
		background: linear-gradient(45deg, #cd7f32, #b87333, #8c5311);
	}

	.team-card:hover {
		transform: translate(0, -4px);
	}

	@media (min-width: 1000px) {
		.flex-box {
			flex-direction: row;
			justify-content: center;
			gap: 20px;
			margin: 80px 0;
		}

		#teams {
			order: 1;
			width: min(65%, 800px);
		}

		#disciplines {
			order: 2;
			flex-direction: column;
			gap: 15px;
			overflow: visible;
		}

		.discipline-card {
			border-radius: 10px;
			height: 100px;
			width: 100px;
		}
	}
</style>
