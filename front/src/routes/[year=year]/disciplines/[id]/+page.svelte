<script>
	import { formatDifference } from '$lib/edition';

	export let data;

	$: year = data.summary.edition.year;
</script>

<h1>{data.discipline.name}</h1>

{#if data.results === null}
	<p class="not-revealed">Results not revealed yet</p>
{:else}
	<div id="results">
		{#each data.results as result}
			<a
				class="team-card"
				class:gold={result.ranking === 1}
				class:silver={result.ranking === 2}
				class:bronze={result.ranking === 3}
				data-testid="result-row"
				href="/{year}/teams/{result.team}"
			>
				<span>{result.ranking === null ? '—' : `${result.ranking}.`} {result.teamName}</span>
				{#if result.ranking === null}
					<span>—</span>
				{:else if result.result_type === 'TIM'}
					<span>{result.time}</span>
				{:else}
					<span>{result.points} pts ({formatDifference(result.points_difference)})</span>
				{/if}
			</a>
		{/each}
	</div>
{/if}

{#if data.schedule !== null}
	<section class="schedule">
		<h2>Schedule</h2>
		{#each data.schedule as round}
			<h3>Round {round.order + 1}</h3>
			{#each round.games as game}
				<div class="game" data-testid="game-row">
					<p class="teams">
						<a href="/{year}/teams/{game.team1Id}">{game.team1Name}</a>
						<span class="score">{game.isPlayed && game.score1 !== null ? `${game.score1} – ${game.score2}` : '—'}</span>
						<a href="/{year}/teams/{game.team2Id}">{game.team2Name}</a>
					</p>
					<p class="referee">ref: {game.refereeName}</p>
				</div>
			{/each}
		{/each}
	</section>
{/if}

<style>
	.not-revealed {
		text-align: center;
		font-weight: 600;
		margin: 3rem 1rem;
	}

	#results {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0 auto;
		width: min(98%, 800px);
	}

	.team-card {
		background-color: var(--color-bg-0);
		border: 1px solid #ccc;
		border-radius: 10px;
		padding: 1em 10px;
		box-shadow: 0 2px 4px #00000030;
		transition: 0.3s;
		display: flex;
		justify-content: space-between;
		align-items: center;
		color: inherit;
		text-decoration: none;
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

	.team-card span {
		font-size: 1rem;
		font-weight: 600;
		margin: 0;
	}

	.schedule {
		width: min(98%, 800px);
		margin: 2rem auto;
	}

	.schedule h2 {
		font-size: 1.3rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}

	.schedule h3 {
		font-size: 1rem;
		font-weight: 700;
		margin: 1.5rem 0 0.5rem;
	}

	.game {
		border: 1px solid #ccc;
		border-radius: 10px;
		padding: 0.6rem 10px;
		margin-bottom: 8px;
	}

	.game .teams {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		margin: 0;
		font-weight: 600;
	}

	.game .teams a {
		color: inherit;
		flex: 1;
	}

	.game .teams a:last-child {
		text-align: right;
	}

	.game .score {
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.game .referee {
		margin: 0.2rem 0 0;
		font-size: 0.85rem;
		opacity: 0.7;
	}
</style>
