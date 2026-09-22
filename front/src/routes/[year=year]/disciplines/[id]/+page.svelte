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
</style>
