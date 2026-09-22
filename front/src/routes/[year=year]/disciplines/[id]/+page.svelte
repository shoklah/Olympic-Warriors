<script>
	import { formatDifference } from '$lib/edition';
	import { iconFor } from '$lib/icons';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import GameRow from '$lib/components/GameRow.svelte';

	export let data;

	$: year = data.summary.edition.year;
	$: rounds = (data.schedule ?? []).filter((round) => round.games.length > 0);
	// The difference is summed from game scores, so a discipline without rounds
	// has nothing but zeroes to show.
	$: showDifference = data.schedule !== null;

	/** "3 games" once every game is played, "1 to play" while some are not. */
	function roundCount(round) {
		const left = round.games.filter((g) => !g.isPlayed).length;
		if (left > 0) return `${left} to play`;
		return `${round.games.length} game${round.games.length === 1 ? '' : 's'}`;
	}
</script>

<div class="page">
	<Breadcrumb
		items={[
			{ label: String(year), href: `/${year}` },
			{ label: 'Disciplines', href: `/${year}/disciplines` },
			{ label: data.discipline.name }
		]}
	/>

	<h1>
		<img src={iconFor(data.discipline.name)} alt="" />
		{data.discipline.name}
	</h1>

	{#if data.results === null}
		<p class="not-revealed">Results not revealed yet</p>
	{:else}
		<div id="results">
			{#each data.results as result}
				<a
					class="result-row"
					class:gold={result.ranking === 1}
					class:silver={result.ranking === 2}
					class:bronze={result.ranking === 3}
					data-testid="result-row"
					href="/{year}/teams/{result.team}"
				>
					<MedalRank rank={result.ranking} />
					<span class="name">{result.teamName}</span>
					<span class="diff">
						{showDifference &&
						result.result_type === 'PTS' &&
						result.points_difference !== null
							? formatDifference(result.points_difference)
							: ''}
					</span>
					<span class="num value">
						{#if result.ranking === null}
							—
						{:else if result.result_type === 'TIM'}
							{result.time}
						{:else}
							{result.points} pts
						{/if}
					</span>
				</a>
			{/each}
		</div>
	{/if}

	{#if rounds.length > 0}
		<section class="schedule">
			<h2>Schedule</h2>
			{#each rounds as round}
				<div class="round-header">
					<h3>Round {round.order + 1}</h3>
					<span class="label" class:todo={round.games.some((g) => !g.isPlayed)}>
						{roundCount(round)}
					</span>
				</div>
				{#each round.games as game}
					<GameRow
						team1Name={game.team1Name}
						team2Name={game.team2Name}
						team1Href="/{year}/teams/{game.team1Id}"
						team2Href="/{year}/teams/{game.team2Id}"
						score1={game.score1}
						score2={game.score2}
						isPlayed={game.isPlayed}
						refereeName={game.refereeName}
					/>
				{/each}
			{/each}
		</section>
	{/if}
</div>

<style>
	h1 {
		display: flex;
		align-items: center;
		gap: 12px;
		margin: 0 0 0.8rem;
	}

	h1 img {
		height: 40px;
		width: 40px;
	}

	.not-revealed {
		margin: 1rem 0 2rem;
		color: var(--muted);
	}

	#results {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.result-row {
		display: grid;
		grid-template-columns: 40px minmax(0, 1fr) auto auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.9rem;
		padding: 9px 12px;
		background: var(--bg-raised);
		border-radius: var(--radius);
		border-left: 4px solid var(--line-strong);
		color: var(--text);
		text-decoration: none;
		transition: background 0.2s ease;
	}

	.result-row:hover {
		background: var(--line);
		text-decoration: none;
	}

	.result-row:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	.result-row.gold {
		border-left-color: var(--gold);
	}

	.result-row.silver {
		border-left-color: var(--silver);
	}

	.result-row.bronze {
		border-left-color: var(--bronze);
	}

	.name {
		min-width: 0;
		font-weight: 600;
		font-size: 0.95rem;
		overflow-wrap: anywhere;
	}

	.diff {
		font-size: 0.75rem;
		font-variant-numeric: tabular-nums;
		text-align: right;
		color: var(--muted);
	}

	.value {
		font-size: 1.5rem;
		line-height: 1;
		letter-spacing: 0.04em;
		color: var(--ink);
	}

	.schedule {
		margin: 1.6rem 0 2rem;
	}

	.schedule h2 {
		margin: 0 0 0.6rem;
	}

	.round-header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
		margin: 1rem 0 0.4rem;
	}

	.round-header h3 {
		margin: 0;
	}

	.round-header .todo {
		color: var(--todo);
	}
</style>
