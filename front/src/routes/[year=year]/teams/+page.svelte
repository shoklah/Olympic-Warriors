<script>
	import { rankedTeams } from '$lib/edition';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import MedalRank from '$lib/components/MedalRank.svelte';
	import { useT } from '$lib/i18n';

	export let data;

	const t = useT();

	$: year = data.summary.edition.year;
	$: teams = rankedTeams(data.summary);
</script>

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: t('nav.teams') }]} />
	<h1>{t('teams.title')}</h1>

	<div class="list">
		{#each teams as team}
			<a
				class="team-card"
				class:gold={team.ranking === 1}
				class:silver={team.ranking === 2}
				class:bronze={team.ranking === 3}
				data-testid="team-card"
				href="/{year}/teams/{team.id}"
			>
				<MedalRank rank={team.ranking} />
				<span class="text">
					<span class="name">{team.name}</span>
					<!-- One span per player so each name stays a single text node, with real
					     separator spans so copied text keeps the dots. -->
					<span class="roster">
						{#each team.players as player, i}
							{#if i > 0}<span class="sep" aria-hidden="true">{' · '}</span>{/if}<span
								>{player.first_name} {player.last_name}</span
							>
						{/each}
					</span>
				</span>
				<span class="num pts">{team.total_points} {t('team.pts')}</span>
			</a>
		{/each}
	</div>
</div>

<style>
	h1 {
		margin: 0 0 0.8rem;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin-bottom: 2rem;
	}

	.team-card {
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

	.team-card:hover {
		background: var(--line);
		transform: translateY(-2px);
		text-decoration: none;
	}

	.team-card:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	.team-card.gold {
		border-left-color: var(--gold);
	}

	.team-card.silver {
		border-left-color: var(--silver);
	}

	.team-card.bronze {
		border-left-color: var(--bronze);
	}

	.text {
		min-width: 0;
	}

	.name {
		display: block;
		font-weight: 600;
		overflow-wrap: anywhere;
	}

	.roster {
		display: block;
		margin-top: 2px;
		font-size: 0.75rem;
		color: var(--muted);
		overflow-wrap: anywhere;
	}

	.sep {
		color: var(--ghost);
	}

	.pts {
		font-size: 1.6rem;
		line-height: 1;
		letter-spacing: 0.06em;
	}
</style>
