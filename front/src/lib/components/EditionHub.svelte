<script>
	import { onMount } from 'svelte';
	import eclipse from '$lib/img/eclipse.png';
	import title from '$lib/img/title.svg';
	import { iconFor } from '$lib/icons';
	import { countdownParts, editionPhase, formatDateRange } from '$lib/edition';
	import { disciplineName, useLocale, useT } from '$lib/i18n';

	export let summary;
	export let editions;

	const locale = useLocale();
	const t = useT();

	$: edition = summary.edition;
	$: half = Math.ceil(summary.disciplines.length / 2);
	$: columns = [summary.disciplines.slice(0, half), summary.disciplines.slice(half)];

	let now = new Date();
	$: phase = editionPhase(edition, now);
	$: parts = countdownParts(edition, now);

	onMount(() => {
		const interval = setInterval(() => (now = new Date()), 1000);
		return () => clearInterval(interval);
	});
</script>

<div class="fullscreen">
	<!-- The title is anchored to the moon, not to the hero box: `.moon` is the rendered
	     image (its aspect ratio, contained in the hero), and the disc sits at 49.3% / 53% of it. -->
	<div class="moon">
		<img id="eclipse" src={eclipse} alt="" />
		<img id="title" src={title} alt="OLYMPIC WARRIORS" />
	</div>

	{#each columns.filter((c) => c.length > 0) as column, i}
		<!-- Explicit sides: the .moon div would otherwise be the columns' "first of type". -->
		<div class="sportcolumn" class:left={i === 0} class:right={i === 1}>
			{#each column as discipline}
				<img src={iconFor(discipline.name)} alt={disciplineName(locale, discipline.name)} />
			{/each}
		</div>
	{/each}
</div>

<p class="where">{edition.host} · {formatDateRange(edition.start_date, edition.end_date, locale)}</p>

{#if phase === 'upcoming'}
	<div id="countdown">
		<div class="label"><span class="num">{parts.days}</span>{t('hub.days')}</div>
		<div class="label"><span class="num">{parts.hours}</span>{t('hub.hours')}</div>
		<div class="label"><span class="num">{parts.minutes}</span>{t('hub.minutes')}</div>
		<div class="label"><span class="num">{parts.seconds}</span>{t('hub.seconds')}</div>
	</div>
{:else}
	<div id="ranking">
		<a href="/{edition.year}/ranking">{t('hub.ranking')}</a>
	</div>
{/if}

{#if editions.length > 1}
	<!-- Same rule as the discipline rail: every edition listed, the current one highlighted. -->
	<nav class="editions" aria-label={t('hub.editions')}>
		{#each editions as other}
			<a
				href="/{other.year}"
				class:current={other.year === edition.year}
				aria-current={other.year === edition.year ? 'page' : undefined}
			>
				{other.year}
			</a>
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
		/* Even icons zig-zag out by 80px, less on phones: never more than the columns'
		   inset minus the 1rem page gutter, so they never widen the page. */
		--inset: 20vw;
		--zigzag: min(80px, var(--inset) - 1rem);
	}

	.sportcolumn.left {
		left: var(--inset);
	}

	.sportcolumn.left :nth-child(even) {
		transform: translate(calc(-1 * var(--zigzag)), 0);
	}

	.sportcolumn.right {
		right: var(--inset);
	}

	.sportcolumn.right :nth-child(even) {
		transform: translate(var(--zigzag), 0);
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
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.8rem 1rem;
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

	.editions a.current {
		color: var(--bg);
		background-color: var(--accent);
		border-color: var(--accent);
	}

	/* The eclipse image is 1664 x 1108: as tall as the hero, or as wide as the viewport. */
	.moon {
		position: relative;
		width: calc(65vh * 1664 / 1108);
		max-width: 100%;
		aspect-ratio: 1664 / 1108;
	}

	#eclipse {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		z-index: -1;
	}

	/* Everything after the hero paints above it, whatever the hero overflows. */
	.where,
	#countdown,
	#ranking,
	.editions {
		position: relative;
		z-index: 1;
	}

	/* Centred on the dark disc (31% of the image wide), well inside it. */
	#title {
		position: absolute;
		left: 49.3%;
		top: 53%;
		width: 24%;
		transform: translate(-50%, -50%);
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

		.fullscreen {
			height: 60vh;
		}

		.moon {
			width: calc(60vh * 1664 / 1108);
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
