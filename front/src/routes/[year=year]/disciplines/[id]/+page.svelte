<script>
	import { formatDifference } from '$lib/edition';

	export let data;

	$: year = data.summary.edition.year;
</script>

<h1>{data.discipline.name}</h1>

{#if data.results === null}
	<p class="hidden">Results not revealed yet</p>
{:else}
	<div id="results">
		{#each data.results as result}
			<div class="team-card" data-testid="result-row">
				<p>{result.ranking === null ? '—' : `${result.ranking}.`} <a href="/{year}/teams/{result.team}">{result.teamName}</a></p>
				{#if result.ranking === null}
					<p>—</p>
				{:else if result.result_type === 'TIM'}
					<p>{result.time}</p>
				{:else}
					<p>{result.points} pts ({formatDifference(result.points_difference)})</p>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.hidden {
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
		padding: 0 10px;
		box-shadow: 0 2px 4px #00000030;
		transition: 0.3s;
		display: flex;
		justify-content: space-between;
	}

	.team-card a {
		color: inherit;
	}

	#results .team-card:nth-of-type(1) {
		background: linear-gradient(45deg, #e6b800, #f2d06b, #e6b800, #e6ac00);
	}

	#results .team-card:nth-of-type(2) {
		background: linear-gradient(45deg, #e0e0e0, #cfcfcf, #b0b0b0, #d1d1d1, #f7f7f7);
	}

	#results .team-card:nth-of-type(3) {
		background: linear-gradient(45deg, #cd7f32, #b87333, #8c5311);
	}

	.team-card:hover {
		transform: translate(0, -4px);
	}

	.team-card p {
		font-size: 1rem;
		font-weight: 600;
	}
</style>
