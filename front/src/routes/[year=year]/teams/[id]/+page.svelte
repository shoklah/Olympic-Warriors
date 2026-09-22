<script>
	export let data;

	const ordinal = (n) => {
		const mod100 = n % 100;
		if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
		const mod10 = n % 10;
		if (mod10 === 1) return `${n}st`;
		if (mod10 === 2) return `${n}nd`;
		if (mod10 === 3) return `${n}rd`;
		return `${n}th`;
	};
</script>

<h1>{data.team.name}</h1>
<p class="standing">{ordinal(data.team.ranking)} · {data.team.total_points} pts</p>

<div class="players">
	{#each data.team.players as player}
		<div class="player-card">
			<p>{player.first_name} {player.last_name}</p>
		</div>
	{/each}
</div>

<table>
	<thead>
		<tr>
			<th scope="col">Discipline</th>
			<th scope="col">Rank</th>
			<th scope="col">Result</th>
		</tr>
	</thead>
	<tbody>
		{#each data.results as row}
			<tr data-testid="discipline-row">
				<td>{row.disciplineName}</td>
				{#if row.revealed}
					<td>{row.ranking}</td>
					<td>{row.result_type === 'TIM' ? row.time : `${row.points} pts`}</td>
				{:else}
					<td>—</td>
					<td>—</td>
				{/if}
			</tr>
		{/each}
	</tbody>
</table>

{#if data.games.length > 0}
	<section class="games">
		<h2>Games</h2>
		{#each data.games as discipline}
			<h3>{discipline.disciplineName}</h3>
			<ul>
				{#each discipline.games as game}
					<li data-testid="game-row">
						{#if game.role === 'referee'}
							Round {game.round + 1} · referee · {game.team1Name} vs {game.team2Name}
						{:else if !game.isPlayed}
							Round {game.round + 1} · vs {game.opponentName} · to play
						{:else if game.result === null}
							Round {game.round + 1} · vs {game.opponentName} · played
						{:else}
							Round {game.round + 1} · vs {game.opponentName} · {game.ownScore} – {game.theirScore} · {game.result === 'win' ? 'won' : game.result === 'loss' ? 'lost' : 'draw'}
						{/if}
					</li>
				{/each}
			</ul>
		{/each}
	</section>
{/if}

<style>
	.standing {
		text-align: center;
		font-weight: 600;
		margin: 0;
	}

	.players {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 20px;
		margin: 20px 1rem;
	}

	.player-card {
		background: var(--color-theme-2);
		color: black;
		padding: 20px 40px;
		border-radius: 10px;
		width: 200px;
		text-align: center;
		box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
		transition: transform 0.3s;
	}

	.player-card p {
		font-size: 1.2rem;
		font-weight: 600;
		margin: 0;
	}

	.player-card:hover {
		transform: scale(1.05);
	}

	table {
		width: min(98%, 600px);
		margin: 2rem auto;
		border-collapse: collapse;
	}

	th,
	td {
		padding: 0.6rem 1rem;
		text-align: left;
		border-bottom: 1px solid #ccc;
	}

	th {
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		font-size: 0.8rem;
	}

	.games {
		width: min(98%, 600px);
		margin: 2rem auto;
	}

	.games h2 {
		font-size: 1.3rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}

	.games h3 {
		font-size: 1rem;
		font-weight: 700;
		margin: 1.5rem 0 0.5rem;
	}

	.games ul {
		margin: 0;
	}

	.games li {
		padding: 0.5rem 0;
		border-bottom: 1px solid #ccc;
		font-variant-numeric: tabular-nums;
	}
</style>
