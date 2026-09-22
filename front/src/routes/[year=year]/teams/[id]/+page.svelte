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
</style>
