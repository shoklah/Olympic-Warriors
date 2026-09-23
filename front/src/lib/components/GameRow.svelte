<script>
	import { useT } from '$lib/i18n';

	/** Home team name; null when the id matched no team (the "unknown" label is shown). @type {string | null} */
	export let team1Name;
	/** Away team name, same rule. @type {string | null} */
	export let team2Name;
	/** @type {number | null} */
	export let score1 = null;
	/** @type {number | null} */
	export let score2 = null;
	export let isPlayed = false;
	/** @type {string | null} */
	export let refereeName = null;
	/** @type {string | null} */
	export let team1Href = null;
	/** @type {string | null} */
	export let team2Href = null;
	/** Short round label ("R1") rendered in a narrow column before the pairing, or null. */
	export let roundLabel = null;
	/** Ids of the two teams, needed only with `highlightId`. */
	export let team1Id = null;
	export let team2Id = null;
	/** The team whose page this row is on: accent colour, plain text instead of a link. */
	export let highlightId = null;
	/** When set, the pairing is a button calling it (the organiser's score sheet). */
	export let onEdit = null;

	const t = useT();

	$: hasScore = isPlayed && score1 !== null && score2 !== null;
	$: team1Class = !hasScore || score1 === score2 ? '' : score1 > score2 ? 'winner' : 'loser';
	$: team2Class = !hasScore || score1 === score2 ? '' : score2 > score1 ? 'winner' : 'loser';
	$: own1 = highlightId !== null && team1Id === highlightId;
	$: own2 = highlightId !== null && team2Id === highlightId;
	$: name1 = team1Name ?? t('team.unknown');
	$: name2 = team2Name ?? t('team.unknown');
</script>

<div class="game-row" data-testid="game-row">
	{#if onEdit}
		<!-- The organiser taps the pairing to open the score sheet: no links inside a button. -->
		<button type="button" class="teams edit" on:click={onEdit} title={t('orga.edit')}>
			{#if roundLabel}
				<span class="round label">{roundLabel}</span>
			{/if}
			<span class="team {team1Class}">{name1}</span>
			<!-- Same score block as the public branch: Svelte 4 has no local snippets. -->
			{#if hasScore}
				<span class="score num">{score1} : {score2}</span>
			{:else if !isPlayed}
				<span class="score num unplayed">— : —</span>
			{:else}
				<span class="score pending">{t('game.played')}</span>
			{/if}
			<span class="team right {team2Class}">{name2}</span>
		</button>
	{:else}
		<p class="teams">
			{#if roundLabel}
				<span class="round label">{roundLabel}</span>
			{/if}

			{#if team1Href && !own1}
				<a class="team {team1Class}" href={team1Href}>{name1}</a>
			{:else}
				<span class="team {team1Class}" class:own={own1}>{name1}</span>
			{/if}

			{#if hasScore}
				<span class="score num">{score1} : {score2}</span>
			{:else if !isPlayed}
				<span class="score num unplayed">— : —</span>
			{:else}
				<span class="score pending">{t('game.played')}</span>
			{/if}

			{#if team2Href && !own2}
				<a class="team right {team2Class}" href={team2Href}>{name2}</a>
			{:else}
				<span class="team right {team2Class}" class:own={own2}>{name2}</span>
			{/if}
		</p>
	{/if}
	{#if refereeName}
		<p class="referee">{t('game.referee', { name: refereeName })}</p>
	{/if}
</div>

<style>
	.game-row {
		background: var(--bg-sunken);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		padding: 0.55rem 0.8rem;
		margin-bottom: 6px;
	}

	.teams {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.8rem;
		margin: 0;
	}

	.team {
		flex: 1;
		min-width: 0;
		overflow-wrap: anywhere;
		color: var(--text);
		text-decoration: none;
	}

	.team.right {
		text-align: right;
	}

	.round {
		flex: none;
		min-width: 2.4rem;
		color: var(--muted);
	}

	/* The own team is in accent: bold when it won, faded and thin when it lost, so the
	   outcome reads from its name alone, not only from the opponent's contrast. */
	.team.own {
		color: var(--accent);
	}

	.team.own.loser {
		opacity: 0.55;
		font-weight: 400;
	}

	.team:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	.winner {
		color: var(--ink);
		font-weight: 600;
	}

	.loser {
		color: var(--muted);
	}

	.score {
		font-size: 1.2rem;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
		color: var(--ink);
	}

	.score.unplayed {
		color: var(--muted);
	}

	.score.pending {
		font-family: var(--font-body);
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--muted);
	}

	.referee {
		margin: 0.25rem 0 0;
		font-size: 0.8rem;
		color: var(--muted);
	}

	.teams.edit {
		width: 100%;
		min-height: 44px;
		background: transparent;
		border: 0;
		padding: 0;
		font: inherit;
		color: inherit;
		text-align: inherit;
		cursor: pointer;
	}

	.teams.edit .team {
		text-align: left;
	}

	.teams.edit .team.right {
		text-align: right;
	}

	/* A small chevron after the away team: the only visual hint the pairing is tappable. */
	.teams.edit::after {
		content: '';
		width: 6px;
		height: 6px;
		border-right: 2px solid var(--muted);
		border-bottom: 2px solid var(--muted);
		transform: rotate(-45deg);
		flex: none;
		margin-left: 4px;
	}

	.teams.edit:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 4px;
		border-radius: 2px;
	}
</style>
