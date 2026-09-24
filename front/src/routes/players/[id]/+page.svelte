<script>
	import Badge from '$lib/components/Badge.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import { badgeDetail, isKnownBadge } from '$lib/badges';
	import { iconFor } from '$lib/icons';
	import { bestDisciplines, byDisplayedName, editionStatus, formatAverage, fullName, spokenPlaces } from '$lib/players';
	import { disciplineName, useLocale, useT } from '$lib/i18n';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: profile = data.profile;
	$: name = fullName(profile);
	$: badges = (profile.badges ?? []).filter(isKnownBadge);
	// Defensive: a front deployed ahead of a server that doesn't carry `disciplines` yet.
	// Ties (equal position) are re-sorted by the name as displayed in this locale, so the
	// server's English database-name order doesn't leak into the French page.
	$: disciplines = byDisplayedName(profile.disciplines ?? [], locale);
	$: best = bestDisciplines(disciplines);
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
		<div class="figure" data-testid="best-discipline">
			<span class="label">{t('profile.bestDiscipline', { n: Math.max(best.count, 1) })}</span>
			{#if best.count > 0}
				<ul class="best-list" role="list">
					{#each best.shown as d}
						<li class="best"><img src={iconFor(d.name)} alt="" />{disciplineName(locale, d.name)}</li>
					{/each}
				</ul>
				{#if best.more > 0}
					<span class="num more" aria-hidden="true">{t('players.more', { n: best.more })}</span>
					<span class="visually-hidden">{t('profile.moreDisciplines', { n: best.more })}</span>
				{/if}
			{:else}
				<span class="num value">—</span>
			{/if}
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

	{#if disciplines.length > 0}
		<h2>{t('profile.byDiscipline')}</h2>
		<ul class="disciplines" role="list">
			{#each disciplines as d}
				<li class="discipline" data-testid="discipline-row">
					<img src={iconFor(d.name)} alt="" />
					<span class="name">{disciplineName(locale, d.name)}</span>
					<span class="places" aria-hidden="true">
						{#each d.places as p}
							<span class="discipline-place"
								><span
									class="num place-rank"
									class:gold={p.rank === 1}
									class:silver={p.rank === 2}
									class:bronze={p.rank === 3}>{p.rank}</span
								>
								<span class="place-year">{p.year}</span></span
							>{' '}
						{/each}
					</span>
					<span class="visually-hidden">{spokenPlaces(d.places, locale)}</span>
				</li>
			{/each}
		</ul>
	{/if}
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
		grid-template-columns: repeat(2, minmax(0, 14rem));
		gap: 8px;
		margin-bottom: 0.6rem;
	}

	/* Two 14rem cards don't fit below 360px: stack them instead of squeezing. */
	@media (max-width: 359.98px) {
		.figures {
			grid-template-columns: minmax(0, 14rem);
		}
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

	.best-list {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: auto 0 0;
		padding: 0;
		list-style: none;
	}

	.best {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 0.95rem;
		overflow-wrap: break-word;
		hyphens: auto;
		color: var(--ink);
	}

	.best img {
		width: 20px;
		height: 20px;
		flex-shrink: 0;
	}

	.more {
		font-size: 0.95rem;
		line-height: 1.3;
		color: var(--muted);
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

	.disciplines {
		margin: 0 0 2rem;
		padding: 0;
		border-bottom: 1px solid var(--line);
		list-style: none;
	}

	.discipline {
		display: grid;
		grid-template-columns: 20px minmax(7rem, 1fr) auto;
		align-items: center;
		gap: 12px;
		padding: 10px 0;
		border-top: 1px solid var(--line);
	}

	.discipline img {
		width: 20px;
		height: 20px;
	}

	.discipline .name {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.places {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: flex-end;
		gap: 4px 10px;
		justify-self: end;
	}

	.discipline-place {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
	}

	.place-rank {
		font-size: 1.15rem;
		line-height: 1.1;
		letter-spacing: 0.04em;
		color: var(--muted);
	}

	.place-rank.gold {
		color: var(--gold);
	}

	.place-rank.silver {
		color: var(--silver);
	}

	.place-rank.bronze {
		color: var(--bronze);
	}

	.place-year {
		font-size: 0.75rem;
		color: var(--muted);
	}
</style>
