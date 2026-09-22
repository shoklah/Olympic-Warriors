<script>
	import { iconFor } from '$lib/icons';
	import { disciplineSubtitle } from '$lib/edition';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: year = data.summary.edition.year;
	$: disciplines = data.summary.disciplines;

	/** "2 rounds · 3 games", or "points" / "time" / nothing for a discipline without rounds. */
	const subtitle = (sub) => {
		if ('rounds' in sub) {
			return `${t('discipline.rounds', { n: sub.rounds })} · ${t('discipline.games', { n: sub.games })}`;
		}
		if (sub.resultType === 'PTS') return t('discipline.points');
		if (sub.resultType === 'TIM') return t('discipline.time');
		return '';
	};
</script>

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: t('nav.disciplines') }]} />
	<h1>{t('disciplines.title')}</h1>

	<div class="grid">
		{#each disciplines as discipline}
			{@const name = disciplineName(locale, discipline.name)}
			<!-- The whole card is the link, so its name is pinned to the bare discipline name.
			     An unrevealed discipline stays reachable: its page still shows the pairings. -->
			<a
				class="card"
				class:unrevealed={!discipline.reveal_score}
				href="/{year}/disciplines/{discipline.id}"
				aria-label={name}
			>
				<span class="icon">
					<img src={iconFor(discipline.name)} alt="" />
				</span>
				<span class="text">
					<span class="name">{name}</span>
					<span class="label subtitle">{subtitle(disciplineSubtitle(data.summary, discipline))}</span>
				</span>
			</a>
		{/each}
	</div>
</div>

<style>
	h1 {
		margin: 0 0 0.8rem;
	}

	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
		margin-bottom: 2rem;
	}

	.card {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--text);
		text-decoration: none;
		transition:
			transform 0.2s ease,
			background 0.2s ease;
	}

	.card:hover {
		background: var(--line);
		transform: translateY(-2px);
		text-decoration: none;
	}

	.card:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	.icon {
		flex: none;
		display: flex;
		align-items: center;
		justify-content: center;
		height: 44px;
		width: 44px;
		border-radius: var(--radius);
		background: var(--bg-sunken);
		border: 1px solid var(--line);
	}

	.icon img {
		height: 76%;
		width: 76%;
	}

	/* Only the tile dims: the name and the subtitle stay readable. */
	.unrevealed .icon {
		opacity: 0.35;
	}

	.text {
		min-width: 0;
	}

	.name {
		display: block;
		font-family: var(--font-display);
		font-size: 1.4rem;
		letter-spacing: 0.06em;
		line-height: 1;
		color: var(--ink);
		overflow-wrap: anywhere;
	}

	.subtitle {
		display: block;
		margin-top: 4px;
	}

	@media (max-width: 580px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
