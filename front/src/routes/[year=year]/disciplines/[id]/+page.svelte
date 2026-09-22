<script>
	import { formatDifference, roundCount } from '$lib/edition';
	import { iconFor } from '$lib/icons';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import DisciplineRail from '$lib/components/DisciplineRail.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import GameRow from '$lib/components/GameRow.svelte';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: year = data.summary.edition.year;
	$: name = disciplineName(locale, data.discipline.name);
	$: rounds = (data.schedule ?? []).filter((round) => round.games.length > 0);
	// The difference is summed from game scores, so a discipline without rounds
	// has nothing but zeroes to show.
	$: showDifference = data.schedule !== null;
</script>

<div class="page">
	<Breadcrumb
		items={[
			{ label: String(year), href: `/${year}` },
			{ label: t('nav.disciplines'), href: `/${year}/disciplines` },
			{ label: name }
		]}
	/>

	<h1>
		<img src={iconFor(data.discipline.name)} alt="" />
		{name}
	</h1>

	<div class="rail">
		<DisciplineRail {year} disciplines={data.summary.disciplines} currentId={data.discipline.id} />
	</div>

	{#if data.results === null}
		<p class="not-revealed">{t('discipline.notRevealed')}</p>
	{:else}
		<div id="results">
			{#each data.results as result}
				{@const difference =
					showDifference && result.result_type === 'PTS' && result.points_difference !== null
						? formatDifference(result.points_difference)
						: null}
				<a
					class="result-row"
					class:no-diff={difference === null}
					class:gold={result.ranking === 1}
					class:silver={result.ranking === 2}
					class:bronze={result.ranking === 3}
					data-testid="result-row"
					href="/{year}/teams/{result.team}"
				>
					<MedalRank rank={result.ranking} />
					<span class="name">{result.teamName ?? t('team.unknown')}</span>
					{#if difference !== null}
						<span class="diff">{difference}</span>
					{/if}
					<span class="num value">
						{#if result.ranking === null}
							—
						{:else if result.result_type === 'TIM'}
							{result.time}
						{:else}
							{result.points} {t('team.pts')}
						{/if}
					</span>
				</a>
			{/each}
		</div>
	{/if}

	{#if rounds.length > 0}
		<section class="schedule">
			<h2>{t('discipline.schedule')}</h2>
			{#each rounds as round}
				{@const count = roundCount(round)}
				<div class="round-header">
					<h3>{t('discipline.round', { n: round.order + 1 })}</h3>
					<span class="label" class:todo={count.left > 0}>
						{count.left > 0
							? t('discipline.toPlay', { n: count.left })
							: t('discipline.games', { n: count.total })}
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

	.rail {
		margin-bottom: 14px;
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
		grid-template-columns: 44px minmax(0, 1fr) auto auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.9rem;
		padding: 10px 12px;
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

	/* A timed result, or a discipline without games, has no difference to show. */
	.result-row.no-diff {
		grid-template-columns: 44px minmax(0, 1fr) auto;
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
		font-size: 1rem;
		overflow-wrap: anywhere;
	}

	.diff {
		font-size: 0.75rem;
		font-variant-numeric: tabular-nums;
		text-align: right;
		color: var(--muted);
	}

	.value {
		font-size: 1.6rem;
		line-height: 1;
		letter-spacing: 0.06em;
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
