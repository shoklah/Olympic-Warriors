<script>
	import Badge from '$lib/components/Badge.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import { badgeDetail, isKnownBadge } from '$lib/badges';
	import { editionStatus, formatAverage, fullName } from '$lib/players';
	import { useLocale, useT } from '$lib/i18n';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: profile = data.profile;
	$: name = fullName(profile);
	$: badges = (profile.badges ?? []).filter(isKnownBadge);
</script>

<div class="page">
	<Breadcrumb items={[{ label: t('players.title'), href: '/players' }, { label: name }]} />
	<h1>{name}</h1>

	{#if profile.position !== null}
		<!-- A plain number: a French ordinal would have to guess the player's gender. -->
		<a class="position" href="/players" data-testid="position">
			<MedalRank rank={profile.position} />
			<span class="label">{t('profile.allTime')}</span>
			<!-- The accessible name must contain the visible text (WCAG 2.5.3). -->
			<span class="visually-hidden"> · {t('profile.positionHint')}</span>
		</a>
	{/if}

	<div class="figures">
		<div class="figure" data-testid="average-rank">
			<span class="label">{t('profile.averageRank')}</span>
			<span class="num value">{formatAverage(profile.average_rank, locale)}</span>
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

	{#if badges.length}
		<h2>{t('profile.badges')}</h2>
		<ul class="badges" role="list">
			{#each badges as badge}
				{@const parts = badgeDetail(badge, t, locale)}
				<li class="tile" data-testid="badge">
					<Badge {badge} />
					<span class="label name">{t(`badge.${badge.code}.name`)}</span>
					{#if badge.partner || parts.length}
						<!-- Each part is its own text, with the dots hidden from assistive tech;
						     the spaces stay outside them so spoken parts never run together. -->
						<span class="detail" data-testid="badge-detail">
							{#if badge.partner}
								{t('badge.with')}
								<a href="/players/{badge.partner.id}">{fullName(badge.partner)}</a>
							{/if}
							{#each parts as part, i}{#if i > 0 || badge.partner}{' '}<span
										class="sep"
										aria-hidden="true">·</span
									>{' '}{/if}<span>{part}</span>{/each}
						</span>
					{/if}
					<span class="rule">{t(`badge.${badge.code}.rule`)}</span>
				</li>
			{/each}
		</ul>
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
		grid-template-columns: minmax(0, 14rem);
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
		margin-top: auto;
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

	.badges {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
		gap: 22px 16px;
		--badge-size: 56px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.tile {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 6px;
		min-width: 0;
	}

	.name {
		color: var(--ink);
	}

	.detail {
		font-size: 0.85rem;
		color: var(--muted);
		overflow-wrap: anywhere;
	}

	.detail a {
		color: var(--accent);
	}

	.sep {
		color: var(--ghost);
	}

	.detail a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	.rule {
		font-size: 0.78rem;
		line-height: 1.35;
		color: var(--muted);
	}

	.editions {
		margin: 0 0 2rem;
		padding: 0;
		border-bottom: 1px solid var(--line);
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

	.year:hover {
		text-decoration: underline;
	}

	.year:focus-visible,
	.team:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		border-radius: 2px;
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
