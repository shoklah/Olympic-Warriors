<script>
	import Avatar from '$lib/components/Avatar.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import Showcase from '$lib/components/Showcase.svelte';
	import { formatAverage, fullName, showcaseLabel, shownPlaces, spokenPlaces } from '$lib/players';
	import { useLocale, useT } from '$lib/i18n';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: ranked = data.players.filter((player) => player.position !== null);
	$: waiting = data.players.filter((player) => player.position === null);

	// The row is one link: the showcase's medallions are aria-hidden, so their names join
	// this sentence (nothing for a player without a badge).
	const spoken = (player) => {
		const average = t('players.averageSpoken', { value: formatAverage(player.average_rank, locale) });
		return [spokenPlaces(player.places, locale), average, showcaseLabel(player.showcase, locale)]
			.filter(Boolean)
			.join(', ');
	};
</script>

<div class="page">
	<h1>{t('players.title')}</h1>
	<p class="subtitle">{t('players.subtitle')}</p>

	{#if ranked.length > 0}
		<ol class="list" role="list">
			{#each ranked as player}
				{@const { shown, more } = shownPlaces(player.places)}
				<li>
					<a
						class="row"
						class:gold={player.position === 1}
						class:silver={player.position === 2}
						class:bronze={player.position === 3}
						href="/players/{player.id}"
						data-testid="player-row"
					>
						<span class="position"><MedalRank rank={player.position} /></span>
						<Avatar photo={player.photo ?? null} name={player} size={32} lazy />
						<span class="text">
							<span class="head">
								<span class="name">{fullName(player)}</span>
								<Showcase badges={player.showcase ?? []} />
							</span>
							<span class="places" aria-hidden="true" data-testid="places">
								{#each shown as place}
									<span
										class="num place"
										class:gold={place.rank === 1}
										class:silver={place.rank === 2}
										class:bronze={place.rank === 3}>{place.rank}</span
									>{' '}
								{/each}
								{#if more > 0}
									<span class="num more">{t('players.more', { n: more })}</span>
								{/if}
							</span>
							<span class="visually-hidden">{spoken(player)}</span>
						</span>
						<span class="average" data-testid="average" aria-hidden="true">
							<span class="num value">{formatAverage(player.average_rank, locale)}</span>
							<span class="label long">{t('players.averageRank')}</span>
							<span class="label short">{t('players.averageRankShort')}</span>
						</span>
					</a>
				</li>
			{/each}
		</ol>
	{/if}

	{#if waiting.length > 0}
		<h2>{t('players.notRanked')}</h2>
		<ul class="list" role="list">
			{#each waiting as player}
				{@const showcase = showcaseLabel(player.showcase, locale)}
				<li>
					<a class="row waiting" href="/players/{player.id}" data-testid="unranked-row">
						<Avatar photo={player.photo ?? null} name={player} size={32} lazy />
						<span class="head">
							<span class="name">{fullName(player)}</span>
							<Showcase badges={player.showcase ?? []} />
						</span>
						<span class="detail"
							>{t('players.editions', { n: player.played })}{#if showcase}<span class="visually-hidden"
									>, {showcase}</span
								>{/if}</span
						>
					</a>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	h1 {
		margin: 1.4rem 0 0.2rem;
	}

	.subtitle {
		margin: 0 0 1rem;
		color: var(--muted);
	}

	h2 {
		margin: 1.6rem 0 0.6rem;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0 0 1.6rem;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		grid-template-columns: 44px auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 12px;
		--medal-size: 1.9rem;
		padding: 10px 12px;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-left: 4px solid var(--line-strong);
		border-radius: var(--radius);
		color: var(--text);
		text-decoration: none;
		transition:
			transform 0.2s ease,
			background 0.2s ease;
	}

	.row.waiting {
		grid-template-columns: auto minmax(0, 1fr) auto;
	}

	/* On a phone the position hugs the avatar: a column two digits wide (a third overflows
	   into the row's padding), the number set against its right edge. */
	@media (max-width: 599.98px) {
		.row {
			grid-template-columns: 28px auto minmax(0, 1fr) auto;
			column-gap: 10px;
		}

		.position {
			justify-self: end;
		}
	}

	.row:hover {
		background: var(--line);
		transform: translateY(-2px);
		text-decoration: none;
	}

	.row:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	.row.gold {
		border-left-color: var(--gold);
	}

	.row.silver {
		border-left-color: var(--silver);
	}

	.row.bronze {
		border-left-color: var(--bronze);
	}

	.text {
		min-width: 0;
	}

	.name {
		min-width: 0;
		font-weight: 600;
		overflow-wrap: anywhere;
	}

	/* The name, then the showcase on its own line below 600px. From 600px the showcase stays
	   inline after the name, a long name wrapping beside it, and its pip row hangs below the
	   line (`--showcase-hang`), so the rings centre on the name and the row keeps its height. */
	.head {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 3px;
		min-width: 0;
	}

	@media (min-width: 600px) {
		.head {
			flex-direction: row;
			align-items: center;
			gap: 10px;
			--showcase-hang: 1;
		}
	}

	.detail {
		font-size: 0.75rem;
		color: var(--muted);
	}

	.row.waiting .detail {
		white-space: nowrap;
	}

	.places {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 2px 8px;
		margin-top: 2px;
	}

	.place {
		font-size: 1.15rem;
		line-height: 1.1;
		letter-spacing: 0.04em;
		color: var(--muted);
	}

	.place.gold {
		color: var(--gold);
	}

	.place.silver {
		color: var(--silver);
	}

	.place.bronze {
		color: var(--bronze);
	}

	.more {
		font-size: 0.95rem;
		line-height: 1.3;
		color: var(--muted);
	}

	.average {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
	}

	.average .value {
		font-size: 1.6rem;
		line-height: 1;
		letter-spacing: 0.06em;
	}

	.average .label {
		text-align: right;
		white-space: nowrap;
	}

	.average .short {
		display: none;
	}

	@media (max-width: 479.98px) {
		.average .long {
			display: none;
		}

		.average .short {
			display: block;
		}
	}
</style>
