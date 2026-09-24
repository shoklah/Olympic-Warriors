<script>
	import { page } from '$app/stores';
	import Avatar from '$lib/components/Avatar.svelte';
	import BadgeCollection from '$lib/components/BadgeCollection.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import PhotoEditor from '$lib/components/PhotoEditor.svelte';
	import Showcase from '$lib/components/Showcase.svelte';
	import { badgeCollection } from '$lib/badges';
	import { iconFor } from '$lib/icons';
	import { bestDisciplines, byDisplayedName, editionStatus, formatAverage, fullName, spokenPlaces } from '$lib/players';
	import { disciplineName, useLocale, useT } from '$lib/i18n';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: profile = data.profile;
	$: name = fullName(profile);
	// Defensive: a front deployed ahead of a server that doesn't carry `disciplines` yet.
	// Ties (equal position) are re-sorted by the name as displayed in this locale, so the
	// server's English database-name order doesn't leak into the French page.
	$: disciplines = byDisplayedName(profile.disciplines ?? [], locale);
	$: best = bestDisciplines(disciplines);
	$: collection = badgeCollection(profile.badges ?? []);
	$: tab = $page.url.searchParams.get('tab') === 'badges' ? 'badges' : 'profile';

	// Whether this is the viewer's own profile, from `data` (the root layout's `me` is merged
	// into it) rather than the ME context: this component stays mounted from one profile to
	// the next, and `me` follows invalidateAll() after a new photo.
	$: owner = Boolean(data.me) && data.me.id === profile.id;
	/** The photo editor is open; it closes itself when the page stops being the owner's. */
	let editing = false;
	$: if (!owner) editing = false;
	/** The camera button, given focus back when the editor closes. */
	let camera = null;
</script>

<div class="page">
	<Breadcrumb items={[{ label: t('players.title'), href: '/players' }, { label: name }]} />
	<!-- The avatar beside the name, the all-time position and the showcase, on every tab.
	     `photo` and `showcase` are optional: an older API sends neither. -->
	<div class="identity">
		<span class="portrait" data-testid="portrait">
			<Avatar photo={profile.photo?.large ?? null} name={profile} />
			{#if owner}
				<button
					type="button"
					class="camera"
					aria-label={t('photo.change')}
					aria-haspopup="dialog"
					bind:this={camera}
					on:click={() => (editing = true)}
				>
					<svg viewBox="0 0 24 24" aria-hidden="true">
						<path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2.3l1.4-2h5.6l1.4 2h2.3A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z" />
						<circle cx="12" cy="12.5" r="3.2" />
					</svg>
				</button>
			{/if}
		</span>
		<div class="who">
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

			<Showcase
				mode="interactive"
				badges={profile.showcase?.badges ?? []}
				{collection}
				badgeStats={profile.badge_stats ?? null}
			/>
		</div>
	</div>

	<nav class="tabs" aria-label={t('profile.tabs')}>
		<a
			class="tab"
			href="?"
			data-sveltekit-noscroll
			data-sveltekit-keepfocus
			aria-current={tab === 'profile' ? 'page' : undefined}>{t('profile.tab.profile')}</a
		>
		<a
			class="tab"
			href="?tab=badges"
			data-sveltekit-noscroll
			data-sveltekit-keepfocus
			aria-current={tab === 'badges' ? 'page' : undefined}>{t('profile.tab.badges')}</a
		>
	</nav>

	{#if owner}
		<PhotoEditor
			open={editing}
			photo={profile.photo ?? null}
			locked={Boolean(data.me.photo_locked)}
			name={profile}
			opener={camera}
			on:close={() => (editing = false)}
		/>
	{/if}

	{#if tab === 'badges'}
		<BadgeCollection {collection} badgeStats={profile.badge_stats ?? null} />
	{:else}
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
			<a class="figure count-card" href="?tab=badges" data-sveltekit-noscroll data-testid="badge-count">
				<span class="label">{t('profile.badges')}</span>
				<span class="value"
					><span class="num">{collection.earned}</span> <span class="num total">/ {collection.total}</span></span
				>
				<span class="bar" aria-hidden="true"
					><span style="width: {(100 * collection.earned) / collection.total}%"></span></span
				>
				<span class="visually-hidden">{t('profile.seeCollection')}</span>
			</a>
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
					<a class="year num quiet-link" href="/{edition.year}">{edition.year}</a>
					{#if edition.team}
						<a class="team quiet-link" href="/{edition.year}/teams/{edition.team.id}">{edition.team.name}</a>
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
	{/if}
</div>

<style>
	/* The avatar is 96px on phones and 128px from 600px (`--avatar-size`, read by Avatar),
	   centred on the name, the position and the showcase stacked beside it. */
	.identity {
		display: flex;
		align-items: center;
		gap: 16px;
		--avatar-size: 96px;
		margin: 0.2rem 0 1.2rem;
	}

	.portrait {
		position: relative;
		display: flex;
		flex: none;
	}

	/* On the avatar's lower right, ringed in the page colour so it reads over any photo. */
	.camera {
		position: absolute;
		right: -4px;
		bottom: -4px;
		display: grid;
		place-items: center;
		width: 40px;
		height: 40px;
		padding: 0;
		border: 3px solid var(--bg);
		border-radius: 50%;
		background: var(--accent);
		color: var(--bg);
		cursor: pointer;
	}

	.camera svg {
		width: 20px;
		height: 20px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.camera:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.who {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.5rem;
		min-width: 0;
	}

	@media (min-width: 600px) {
		.identity {
			gap: 24px;
			--avatar-size: 128px;
		}
	}

	/* `anywhere` is the last resort for a single word wider than the line. */
	h1 {
		margin: 0;
		line-height: 1;
		overflow-wrap: anywhere;
	}

	/* Beside the 96px avatar the name has 231px at 375px and 176px at 320px: the heading
	   scales with the viewport so a long name part (« Rochefoucauld- ») still fits whole on
	   a line. No `hyphens: auto`: a dictionary would cut people's names at syllables. */
	@media (max-width: 599.98px) {
		h1 {
			font-size: clamp(1.6rem, 8vw, 2.75rem);
		}
	}

	h2 {
		margin: 1.6rem 0 0.6rem;
	}

	.position {
		display: inline-flex;
		align-items: baseline;
		gap: 8px;
		--medal-size: 1.6rem;
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

	.tabs {
		display: flex;
		gap: 1.4rem;
		margin: 0 0 1.4rem;
		border-bottom: 1px solid var(--line);
	}

	.tab {
		padding: 0.3em 0.1em 0.6em;
		border-bottom: 2px solid transparent;
		color: var(--muted);
		font-family: var(--font-display);
		font-size: 1.1rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		text-decoration: none;
	}

	.tab:hover {
		color: var(--accent);
	}

	.tab[aria-current='page'] {
		color: var(--accent);
		border-bottom-color: var(--accent);
	}

	.tab:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	.figures {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 14rem));
		gap: 8px;
		margin-bottom: 0.6rem;
	}

	/* Two 14rem cards and the badge-count card don't fit below 600px: two columns instead,
	   with the signature-event card (variable height) spanning the second row alone. */
	@media (max-width: 599.98px) {
		.figures {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.figure[data-testid='best-discipline'] {
			grid-column: 1 / -1;
			order: 3;
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

	.count-card {
		color: inherit;
		text-decoration: none;
	}

	.count-card:hover {
		border-color: var(--accent);
	}

	.count-card:hover .label {
		color: var(--accent);
	}

	.count-card:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.value {
		margin-top: auto;
		font-size: 2.1rem;
		line-height: 1;
		letter-spacing: 0.04em;
		color: var(--ink);
	}

	.value .total {
		color: var(--muted);
	}

	.count-card .bar {
		height: 4px;
		border-radius: var(--radius-pill);
		background: var(--line);
		overflow: hidden;
	}

	.count-card .bar span {
		display: block;
		height: 100%;
		background: var(--accent);
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
		filter: var(--icon-filter);
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

	.name {
		color: var(--ink);
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
		filter: var(--icon-filter);
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
