<script>
	/** Round index, 0-based as `teamGames` returns it. */
	export let round = 0;
	/** @type {'play' | 'referee'} */
	export let role = 'play';
	/** @type {string | null} */
	export let opponentName = null;
	/** Home team name, shown when the team referees. */
	export let team1Name = '';
	/** Away team name, shown when the team referees. */
	export let team2Name = '';
	export let isPlayed = false;
	/** @type {number | null} */
	export let ownScore = null;
	/** @type {number | null} */
	export let theirScore = null;
	/** @type {'win' | 'loss' | 'draw' | null} */
	export let result = null;

	const OUTCOME = { win: 'won', loss: 'lost', draw: 'draw' };
</script>

<div class="game-row" data-testid="game-row">
	<span class="label">Round {round + 1}</span>
	<span class="separator" aria-hidden="true">{' · '}</span>
	{#if role === 'referee'}
		<span class="referee">referee</span>
		<span class="separator" aria-hidden="true">{' · '}</span>
		<span class="teams">{team1Name} vs {team2Name}</span>
	{:else}
		<span class="opponent">vs {opponentName}</span>
		<span class="separator" aria-hidden="true">{' · '}</span>
		{#if !isPlayed}
			<span class="to-play">to play</span>
		{:else if result === null}
			<span class="pending">played</span>
		{:else}
			<span class="score num">{ownScore} : {theirScore}</span>
			<span class="separator" aria-hidden="true">{' · '}</span>
			<span class={OUTCOME[result]}>{OUTCOME[result]}</span>
		{/if}
	{/if}
</div>

<style>
	.game-row {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.4rem;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--line);
	}

	.separator {
		color: var(--ghost);
	}

	.opponent,
	.teams {
		color: var(--text);
	}

	.score {
		font-size: 1.1rem;
		color: var(--ink);
		font-variant-numeric: tabular-nums;
	}

	.won {
		color: var(--win);
	}

	.lost {
		color: var(--loss);
	}

	.draw {
		color: var(--text);
	}

	.to-play {
		color: var(--todo);
	}

	.pending,
	.referee {
		color: var(--muted);
	}
</style>
