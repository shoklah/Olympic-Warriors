<script>
	import MedalRank from '$lib/components/MedalRank.svelte';
	import { formatAverage, formatShare } from '$lib/players';
	import { useLocale, useT } from '$lib/i18n';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: ranked = data.players.filter((player) => player.position !== null);
	$: waiting = data.players.filter((player) => player.position === null);
</script>

<div class="page">
	<h1>{t('players.title')}</h1>
	<p class="subtitle label">{t('players.subtitle')}</p>

	<ol class="list">
		{#each ranked as player}
			<li>
				<a
					class="row"
					class:gold={player.position === 1}
					class:silver={player.position === 2}
					class:bronze={player.position === 3}
					href="/players/{player.id}"
					data-testid="player-row"
				>
					<MedalRank rank={player.position} />
					<span class="name">{player.first_name} {player.last_name}</span>
					<span class="figures">
						<span class="num share">{formatShare(player.average_beaten, locale)}</span>
						<span class="detail"
							>{t('players.average', { value: formatAverage(player.average_rank, locale) })} · {t(
								'players.editions',
								{ n: player.counted }
							)}</span
						>
					</span>
				</a>
			</li>
		{/each}
	</ol>

	{#if waiting.length > 0}
		<h2 class="label">{t('players.notRanked')}</h2>
		<ul class="list">
			{#each waiting as player}
				<li>
					<a class="row waiting" href="/players/{player.id}" data-testid="unranked-row">
						<span class="name">{player.first_name} {player.last_name}</span>
						<span class="detail">{t('players.editions', { n: player.played })}</span>
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
		grid-template-columns: 44px minmax(0, 1fr) auto;
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
		grid-template-columns: minmax(0, 1fr) auto;
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

	.name {
		min-width: 0;
		font-weight: 600;
		overflow-wrap: anywhere;
	}

	.figures {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
	}

	.share {
		font-size: 1.6rem;
		line-height: 1;
		letter-spacing: 0.06em;
	}

	.detail {
		font-size: 0.75rem;
		color: var(--muted);
		white-space: nowrap;
	}
</style>
