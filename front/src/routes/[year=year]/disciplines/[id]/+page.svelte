<script>
	import { enhance } from '$app/forms';
	import { entryTime, formatDifference, formatTime, roundCount } from '$lib/edition';
	import { iconFor } from '$lib/icons';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import DisciplineRail from '$lib/components/DisciplineRail.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import GameRow from '$lib/components/GameRow.svelte';
	import ScoreSheet from '$lib/components/ScoreSheet.svelte';
	import StaffBar from '$lib/components/StaffBar.svelte';

	export let data;
	/** The last action's result: {ok, action, id} or {action, id, error} (a fail). */
	export let form = null;

	const locale = useLocale();
	const t = useT();

	$: year = data.summary.edition.year;
	$: name = disciplineName(locale, data.discipline.name);
	$: rounds = (data.schedule ?? []).filter((round) => round.games.length > 0);
	// The difference is summed from game scores, so a discipline without rounds
	// has nothing but zeroes to show.
	$: showDifference = data.schedule !== null;

	// Organiser view: only on the latest edition, for a staff user (data.editable).
	$: editable = Boolean(data.editable);
	$: hasRounds = data.schedule !== null;
	$: isSwiss = data.discipline.pairing_system === 'SW';
	$: unplayed = (data.schedule ?? []).reduce((n, round) => n + roundCount(round).left, 0);
	$: withoutResult = data.entries.filter((e) => e.points === null && e.time === null).length;
	// Worded only while hidden: once public, what is missing shows as dashes in the list.
	$: missing = data.discipline.reveal_score
		? null
		: hasRounds
			? unplayed > 0
				? t('discipline.toPlay', { n: unplayed })
				: null
			: withoutResult > 0
				? t('orga.missingResults', { n: withoutResult })
				: null;
	// Reactive on purpose: a failed action updates `form` without reloading `data`.
	$: errorFor = (action, id) =>
		form && form.action === action && form.id === id && form.error ? form.error : null;

	/** The game whose sheet is open, or null; the row's button gets focus back on close. */
	let editing = null;
	let editingRound = 0;
	let opener = null;
	/** The `form` value dismissed by closing the sheet, so reopening the same game does not
	    show the previous failure again. */
	let dismissedForm = null;
	const openSheet = (game, roundOrder, event) => {
		opener = event?.currentTarget ?? null;
		editing = game;
		editingRound = roundOrder + 1;
		dismissedForm = form;
	};
	const closeSheet = () => {
		editing = null;
		opener?.focus();
	};
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

	{#if editable}
		<StaffBar
			disciplineId={data.discipline.id}
			revealed={data.discipline.reveal_score}
			{missing}
			error={errorFor('reveal', data.discipline.id)}
		/>
	{/if}

	<div class="rail">
		<DisciplineRail {year} disciplines={data.summary.disciplines} currentId={data.discipline.id} />
	</div>

	{#if editable && !hasRounds}
		<!-- The organiser's entry form replaces the list: one line per team, one form each. -->
		<div id="entries">
			{#each data.entries as entry}
				<form method="POST" action="?/result" class="result-line" data-testid="result-line" use:enhance>
					<input type="hidden" name="result" value={entry.id} />
					<input type="hidden" name="kind" value={data.discipline.result_type} />
					<MedalRank rank={entry.ranking} />
					<label class="name" for="entry-{entry.id}">{entry.teamName ?? t('team.unknown')}</label>
					{#if data.discipline.result_type === 'TIM'}
						<!-- A text keyboard: the numeric keypad has no colon. The pattern is a JS string
						     because Svelte would read `{1,3}` in a plain attribute as an expression. -->
						<input
							id="entry-{entry.id}"
							name="value"
							type="text"
							placeholder={t('orga.timeHint')}
							pattern={'[0-9]{1,3}:[0-5][0-9]'}
							value={entryTime(entry.time) ?? ''}
						/>
					{:else}
						<input
							id="entry-{entry.id}"
							name="value"
							type="number"
							inputmode="numeric"
							min="0"
							value={entry.points ?? ''}
						/>
					{/if}
					<button>{t('orga.save')}</button>
					{#if errorFor('result', entry.id)}
						<p class="error" role="alert">{t(errorFor('result', entry.id))}</p>
					{/if}
				</form>
			{/each}
		</div>
	{:else if data.results === null}
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
							{formatTime(result.time)}
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
				{@const closable = editable && isSwiss && !round.isOver && count.left === 0}
				<div class="round-header">
					<h3>{t('discipline.round', { n: round.order + 1 })}</h3>
					{#if editable && round.isOver}
						<span class="label done">{t('orga.roundClosed')}</span>
					{:else if closable}
						<form method="POST" action="?/close" use:enhance>
							<input type="hidden" name="round" value={round.id} />
							<button class="close">{t('orga.closeRound')}</button>
						</form>
					{:else}
						<span class="label" class:todo={count.left > 0}>
							{count.left > 0
								? t('discipline.toPlay', { n: count.left })
								: t('discipline.games', { n: count.total })}
						</span>
					{/if}
				</div>
				{#if errorFor('close', round.id)}
					<p class="error" role="alert">{t(errorFor('close', round.id))}</p>
				{/if}
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
						onEdit={editable ? (event) => openSheet(game, round.order, event) : null}
					/>
				{/each}
			{/each}
		</section>
	{/if}
</div>

{#if editable && editing}
	<ScoreSheet
		game={editing}
		roundNumber={editingRound}
		open={true}
		error={form === dismissedForm ? null : errorFor('score', editing.id)}
		on:close={closeSheet}
	/>
{/if}

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

	#entries {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.result-line {
		display: grid;
		grid-template-columns: 44px minmax(0, 1fr) 6rem auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.9rem;
		margin: 0;
		padding: 10px 12px;
		background: var(--bg-raised);
		border-radius: var(--radius);
		border-left: 4px solid var(--line-strong);
	}

	.result-line input {
		min-height: 44px;
		width: 100%;
		background: var(--bg-sunken);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		color: var(--ink);
		font-family: var(--font-display);
		font-size: 1.3rem;
		text-align: right;
		padding: 0 0.6rem;
	}

	.result-line button,
	.close {
		min-height: 44px;
		padding: 0 1rem;
		border-radius: var(--radius);
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		font-family: var(--font-display);
		font-size: 1rem;
		letter-spacing: 0.1em;
		cursor: pointer;
	}

	.result-line .error {
		grid-column: 1 / -1;
	}

	.error {
		margin: 0.2rem 0 0;
		color: var(--loss);
		font-size: 0.85rem;
	}

	.round-header form {
		margin: 0;
	}

	.round-header .done {
		color: var(--win);
	}

	button:focus-visible,
	.result-line input:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
</style>
