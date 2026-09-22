<script>
	import { iconFor } from '$lib/icons';

	export let data;

	$: year = data.summary.edition.year;
</script>

<h1>Disciplines</h1>
<div class="grid-container">
	{#each data.summary.disciplines as discipline}
		<a href="/{year}/disciplines/{discipline.id}">
			<div class="card">
				<img src={iconFor(discipline.name)} alt="" />
				<h2>{discipline.name}</h2>
			</div>
		</a>
	{/each}
</div>

<style>
	h1 {
		visibility: hidden;
	}

	img {
		position: absolute;
		height: 90%;
		width: 50%;
		right: 0;
	}

	.grid-container {
		display: grid;
		width: min(90%, 1400px);
		grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
		gap: 16px;
		padding: 16px;
		margin: 0 auto;
	}

	.card {
		position: relative;
		height: 160px;
		background-color: var(--color-theme-1);
		border-radius: 8px;
		border: 2px solid #999999;
		padding: 16px;
		transition: 0.2s;
	}

	.card:hover {
		transform: translate(0, -4px);
	}

	h2 {
		color: var(--color-theme-2);
		font-size: 1.5rem;
		font-weight: 600;
	}

	a:hover {
		text-decoration: none;
	}

	@media (max-width: 1000px) {
		h1 {
			display: none;
		}
	}

	@media (max-width: 580px) {
		.grid-container {
			grid-template-columns: 1fr;
		}

		.card {
			height: 100px;
		}
	}
</style>
