<script>
	import { formatTime } from '$lib/edition';
	import { iconFor } from '$lib/icons';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import Avatar from '$lib/components/Avatar.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import GameRow from '$lib/components/GameRow.svelte';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: year = data.summary.edition.year;
</script>

<div class="page">
	<Breadcrumb
		items={[
			{ label: String(year), href: `/${year}` },
			{ label: t('nav.ranking'), href: `/${year}/ranking` },
			{ label: data.team.name }
		]}
	/>

	<h1>{data.team.name}</h1>

	<p class="standing" data-testid="standing">
		<MedalRank rank={data.team.ranking} ordinal />
		<span class="label">{t('team.overall')}</span>
		{#if data.team.total_points !== null}
			<span class="num points">{data.team.total_points}</span>
			<span class="label">{t('team.pts')}</span>
		{/if}
	</p>

	<div class="roster">
		{#each data.team.players as player}
			<a class="chip" href="/players/{player.user}"
				><Avatar photo={player.photo ?? null} name={player} size={24} /><span class="player">{fullName(player)}</span></a
			>
		{/each}
	</div>

	<h2>{t('team.results')}</h2>
	<div class="tiles">
		{#each data.results as row}
			<div
				class="tile"
				class:gold={row.ranking === 1}
				class:silver={row.ranking === 2}
				class:bronze={row.ranking === 3}
				data-testid="discipline-row"
			>
				<span class="discipline">
					<img src={iconFor(row.disciplineName)} alt="" />
					<span class="label name">{disciplineName(locale, row.disciplineName)}</span>
				</span>
				<MedalRank rank={row.ranking} ordinal />
				<!-- `.num` on the revealed value only: the status is words, not a number. -->
				<span class="value" class:num={row.revealed} class:muted={!row.revealed}>
					{#if !row.revealed}
						{t('team.notRevealed')}
					{:else if row.result_type === 'TIM'}
						{formatTime(row.time)}
					{:else}
						{row.points} {t('team.pts')}
					{/if}
				</span>
			</div>
		{/each}
	</div>

	{#if data.games.length > 0}
		<section class="games">
			<h2>{t('team.games')}</h2>
			{#each data.games as discipline}
				<h3 class="label">{disciplineName(locale, discipline.disciplineName)}</h3>
				{#each discipline.games as game}
					<GameRow
						roundLabel={game.round === null ? null : t('discipline.roundShort', { n: game.round + 1 })}
						highlightId={data.team.id}
						team1Id={game.team1Id}
						team2Id={game.team2Id}
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
		margin: 0 0 0.4rem;
		overflow-wrap: anywhere;
	}

	h2 {
		margin: 1.6rem 0 0.6rem;
	}

	.standing {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 10px;
		--medal-size: 2.1rem;
		margin: 0 0 0.9rem;
	}

	.points {
		font-size: 2.1rem;
		line-height: 1;
		letter-spacing: 0.04em;
		color: var(--ink);
	}

	.roster {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	/* The avatar tucked into the pill's rounded end, like the header's account pill. */
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 3px 12px 3px 3px;
		border-radius: var(--radius-pill);
		background: var(--bg-raised);
		border: 1px solid var(--line-strong);
		font-size: 0.8rem;
		min-width: 0;
		overflow-wrap: anywhere;
		color: var(--text);
		text-decoration: none;
		transition: border-color 0.2s ease;
	}

	.player {
		min-width: 0;
	}

	.chip:hover {
		border-color: var(--accent);
		text-decoration: none;
	}

	.chip:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.tiles {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 8px;
	}

	.tile {
		min-width: 0;
		--medal-size: 1.9rem;
		padding: 10px 12px;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-top: 3px solid var(--line-strong);
		border-radius: var(--radius);
	}

	.tile.gold {
		border-top-color: var(--gold);
	}

	.tile.silver {
		border-top-color: var(--silver);
	}

	.tile.bronze {
		border-top-color: var(--bronze);
	}

	.discipline {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}

	.discipline img {
		flex: none;
		height: 16px;
		width: 16px;
		filter: var(--icon-filter);
	}

	.name {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.value {
		display: block;
		margin-top: 2px;
		font-size: 0.85rem;
	}

	/* The display face wants the tracking; the "not revealed" words do not. */
	.value.num {
		letter-spacing: 0.04em;
	}

	.value.muted {
		color: var(--muted);
	}

	.games {
		margin-bottom: 2rem;
	}

	.games h3 {
		margin: 1.2rem 0 0.3rem;
	}

	@media (max-width: 580px) {
		.tiles {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
