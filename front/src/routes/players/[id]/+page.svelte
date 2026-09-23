<script>
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import { editionStatus, formatAverage, formatShare } from '$lib/players';
	import { useLocale, useT } from '$lib/i18n';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: profile = data.profile;
	$: name = `${profile.first_name} ${profile.last_name}`;
</script>

<div class="page">
	<Breadcrumb items={[{ label: t('players.title'), href: '/players' }, { label: name }]} />
	<h1>{name}</h1>

	{#if profile.position !== null}
		<!-- A plain number: a French ordinal would have to guess the player's gender. -->
		<a class="position" href="/players" data-testid="position">
			<MedalRank rank={profile.position} />
			<span class="label">{t('profile.allTime')}</span>
		</a>
	{/if}

	<!-- Two figures at the same size: neither is the headline. -->
	<div class="figures">
		<div class="figure" data-testid="average-rank">
			<span class="label">{t('profile.averageRank')}</span>
			<span class="num value">{formatAverage(profile.average_rank, locale)}</span>
		</div>
		<div class="figure" data-testid="beaten">
			<span class="label">{t('profile.beaten')}</span>
			<span class="num value">{formatShare(profile.average_beaten, locale)}</span>
		</div>
	</div>

	<p class="counts">
		{t('players.editions', { n: profile.editions.length })} · {t('profile.counted', {
			n: profile.counted
		})}
	</p>
	{#if profile.counted === 0}
		<p class="counts">{t('profile.noRankedEdition')}</p>
	{/if}

	<h2>{t('profile.editions')}</h2>
	<ul class="editions" role="list">
		{#each profile.editions as edition}
			{@const status = editionStatus(edition)}
			<li class="edition" data-testid="edition-row">
				<a class="year num" href="/{edition.year}">{edition.year}</a>
				{#if edition.team}
					<a class="team" href="/{edition.year}/teams/{edition.team.id}">{edition.team.name}</a>
				{:else}
					<span class="team muted">{t('profile.noTeam')}</span>
				{/if}
				{#if status === 'ranked'}
					<span class="rank">
						<MedalRank rank={edition.rank} />
						<span class="num of">/ {edition.teams}</span>
					</span>
				{:else if status === 'inProgress'}
					<span class="tag label">{t('profile.inProgress')}</span>
				{:else}
					<span class="rank muted">—</span>
				{/if}
			</li>
		{/each}
	</ul>
</div>

<style>
	h1 {
		margin: 0 0 0.6rem;
		overflow-wrap: anywhere;
	}

	h2 {
		margin: 1.6rem 0 0.6rem;
	}

	.position {
		display: inline-flex;
		align-items: baseline;
		gap: 8px;
		--medal-size: 1.6rem;
		margin-bottom: 0.9rem;
		color: var(--text);
		text-decoration: none;
	}

	.position:hover .label {
		color: var(--accent);
	}

	.position:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	.figures {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
		margin-bottom: 0.6rem;
	}

	.figure {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
		padding: 10px 12px;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.value {
		font-size: 2.1rem;
		line-height: 1;
		letter-spacing: 0.04em;
		color: var(--ink);
	}

	.counts {
		margin: 0 0 0.4rem;
		font-size: 0.85rem;
		color: var(--muted);
	}

	.editions {
		margin: 0 0 2rem;
		padding: 0;
		list-style: none;
	}

	.edition {
		display: grid;
		grid-template-columns: 3.2rem minmax(0, 1fr) auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.5rem;
		padding: 10px 0;
		border-top: 1px solid var(--line);
	}

	.year {
		font-size: 1.3rem;
		letter-spacing: 0.06em;
		color: var(--accent);
		text-decoration: none;
	}

	.team {
		min-width: 0;
		overflow-wrap: anywhere;
		color: var(--text);
	}

	.muted {
		color: var(--muted);
	}

	.rank {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
	}

	.of {
		font-size: 1rem;
		color: var(--muted);
	}

	.tag {
		padding: 3px 10px;
		border: 1px solid var(--accent);
		border-radius: var(--radius-pill);
		color: var(--accent);
		white-space: nowrap;
	}
</style>
