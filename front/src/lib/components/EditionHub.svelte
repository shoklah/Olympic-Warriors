<script>
	import { onMount } from 'svelte';
	import eclipse from '$lib/img/eclipse.png';
	import title from '$lib/img/title.svg';
	import { iconFor } from '$lib/icons';
	import { countdownParts, editionPhase, formatDateRange } from '$lib/edition';

	export let summary;
	export let editions;

	$: edition = summary.edition;
	$: half = Math.ceil(summary.disciplines.length / 2);
	$: columns = [summary.disciplines.slice(0, half), summary.disciplines.slice(half)];
	$: others = editions.filter((e) => e.year !== edition.year);

	let now = new Date();
	$: phase = editionPhase(edition, now);
	$: parts = countdownParts(edition, now);

	onMount(() => {
		const interval = setInterval(() => (now = new Date()), 1000);
		return () => clearInterval(interval);
	});
</script>

<div class="fullscreen">
	<img id="eclipse" src={eclipse} alt="" />
	<img id="title" src={title} alt="OLYMPIC WARRIORS" />

	{#each columns.filter((c) => c.length > 0) as column}
		<div class="sportcolumn">
			{#each column as discipline}
				<img src={iconFor(discipline.name)} alt={discipline.name} />
			{/each}
		</div>
	{/each}
</div>

<p class="where">{edition.host} · {formatDateRange(edition.start_date, edition.end_date)}</p>

{#if phase === 'upcoming'}
	<div id="countdown">
		<div class="label"><span class="num">{parts.days}</span>Days</div>
		<div class="label"><span class="num">{parts.hours}</span>Hours</div>
		<div class="label"><span class="num">{parts.minutes}</span>Minutes</div>
		<div class="label"><span class="num">{parts.seconds}</span>Seconds</div>
	</div>
{:else}
	<div id="ranking">
		<a href="/{edition.year}/ranking">Ranking</a>
	</div>
{/if}

{#if others.length > 0}
	<nav class="editions" aria-label="Other editions">
		{#each others as other}
			<a href="/{other.year}">{other.year}</a>
		{/each}
	</nav>
{/if}

<style>
	.sportcolumn {
		position: absolute;
		top: 0;
		bottom: 0;
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		opacity: 0.3;
	}

	.sportcolumn:first-of-type {
		left: 20vw;
	}

	.sportcolumn:first-of-type :nth-child(even) {
		transform: translate(-80px, 0);
	}

	.sportcolumn:last-of-type {
		right: 20vw;
	}

	.sportcolumn:last-of-type :nth-child(even) {
		transform: translate(80px, 0);
	}

	.sportcolumn img {
		width: min(100px, 10vw);
	}

	.where {
		text-align: center;
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		color: var(--accent);
		margin: 0 1rem 1rem;
	}

	#countdown,
	#ranking {
		display: flex;
		justify-content: center;
		gap: 2rem;
		margin: 1rem 0;
	}

	#ranking a {
		background: var(--accent);
		color: var(--bg);
		font-family: var(--font-display);
		font-size: 1.6rem;
		letter-spacing: 0.15em;
		padding: 0.7rem 3rem;
		border-radius: var(--radius);
		transition: 0.3s;
		text-decoration: none;
	}

	#ranking a:hover,
	#ranking a:focus-visible {
		opacity: 0.8;
	}

	#countdown .label {
		display: flex;
		flex-direction: column;
		align-items: center;
		width: 75px;
	}

	#countdown .num {
		font-size: 3rem;
		margin-bottom: 0.25rem;
		color: var(--ink);
		font-weight: 400;
		letter-spacing: 0.02em;
	}

	.editions {
		display: flex;
		justify-content: center;
		gap: 1rem;
		margin: 2rem 1rem;
	}

	.editions a {
		font-family: var(--font-display);
		letter-spacing: 0.1em;
		color: var(--accent);
		border: 2px solid var(--faint);
		border-radius: var(--radius-pill);
		padding: 0.4rem 1.2rem;
		text-decoration: none;
		transition: 0.2s;
	}

	.editions a:hover,
	.editions a:focus-visible {
		color: var(--bg);
		background-color: var(--accent);
	}

	#eclipse {
		width: min(98%, 1200px);
		margin: 0 auto;
		transform: translate(1%, 0);
		z-index: -10;
	}

	#title {
		width: min(25%, 300px);
		position: absolute;
	}

	.fullscreen {
		position: relative;
		isolation: isolate;
		height: 65vh;
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
	}

	@media (max-width: 999.98px) {
		.sportcolumn img {
			width: min(100px, 20vw);
		}

		#eclipse {
			width: min(98%, 800px);
		}

		#title {
			width: min(25%, 200px);
		}

		.fullscreen {
			height: 60vh;
		}

		#ranking a {
			padding: 0.6rem 2rem;
			font-size: 1.2rem;
		}

		#countdown {
			gap: 1rem;
			padding: 0 1rem;
		}
	}
</style>
