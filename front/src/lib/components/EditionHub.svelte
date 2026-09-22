<script>
	import { onMount } from 'svelte';
	import eclipse from '$lib/img/eclipse.png';
	import title from '$lib/img/title.svg';
	import { iconFor } from '$lib/icons';
	import { countdownParts, editionPhase } from '$lib/edition';

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

	/** Noon anchoring keeps the calendar day whatever the renderer's timezone. */
	const parseDay = (iso) => new Date(`${iso}T12:00:00`);
	const dayMonth = (date) =>
		date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long' });

	/** "19 - 20 September 2026", or "30 September - 1 October 2026" across months. */
	const formatRange = (start, end) => {
		const from = parseDay(start);
		const to = parseDay(end);
		const sameMonth = from.getFullYear() === to.getFullYear() && from.getMonth() === to.getMonth();
		const left = sameMonth ? from.toLocaleDateString('en-GB', { day: 'numeric' }) : dayMonth(from);
		return `${left} – ${dayMonth(to)} ${to.getFullYear()}`;
	};
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

<p class="where">{edition.host} · {formatRange(edition.start_date, edition.end_date)}</p>

{#if phase === 'upcoming'}
	<div id="countdown">
		<div><span>{parts.days}</span>Days</div>
		<div><span>{parts.hours}</span>Hours</div>
		<div><span>{parts.minutes}</span>Minutes</div>
		<div><span>{parts.seconds}</span>Seconds</div>
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
		color: var(--color-theme-1);
		font-weight: 600;
		letter-spacing: 0.1em;
		margin: 0 1rem 1rem;
	}

	#countdown,
	#ranking {
		display: flex;
		justify-content: center;
		gap: 2rem;
		font-size: 1rem;
		margin: 1rem 0;
		color: var(--color-theme-1);
	}

	#ranking a {
		color: var(--color-bg-0);
		background-color: var(--color-theme-1);
		padding: 0.6rem 4rem;
		border-radius: 2em;
		font-weight: 700;
		font-size: 2rem;
		transition: 0.3s;
		text-decoration: none;
	}

	#ranking a:hover {
		opacity: 0.8;
	}

	#countdown div {
		display: flex;
		flex-direction: column;
		align-items: center;
		width: 75px;
	}

	#countdown span {
		font-size: 2.5rem;
		font-weight: 600;
		margin-bottom: 1rem;
	}

	.editions {
		display: flex;
		justify-content: center;
		gap: 1rem;
		margin: 2rem 1rem;
	}

	.editions a {
		color: var(--color-theme-1);
		border: 2px solid var(--color-theme-1);
		border-radius: 2em;
		padding: 0.4rem 1.2rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-decoration: none;
		transition: 0.2s;
	}

	.editions a:hover {
		color: var(--color-bg-0);
		background-color: var(--color-theme-1);
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
		height: 65vh;
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
	}

	@media (max-width: 1000px) {
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
	}
</style>
