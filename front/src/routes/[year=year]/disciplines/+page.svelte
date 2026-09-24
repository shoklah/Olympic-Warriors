<script>
	import { disciplineSubtitle } from '$lib/edition';
	import { allTimePath, byShownName, yearSpan } from '$lib/all-time';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import DisciplineCard from '$lib/components/DisciplineCard.svelte';

	export let data;

	const locale = useLocale();
	const t = useT();

	$: year = data.summary.edition.year;
	$: disciplines = data.summary.disciplines;
	// Every discipline ever held, whatever this edition holds: each leads to its all-time table,
	// the « Palmarès » tab of its page in this year when this edition held it (allTimePath).
	$: held = byShownName(data.held ?? [], locale);

	/** "2 rounds · 3 games", or "points" / "time" / nothing for a discipline without rounds. */
	const subtitle = (sub) => {
		if ('rounds' in sub) {
			return `${t('discipline.rounds', { n: sub.rounds })} · ${t('discipline.games', { n: sub.games })}`;
		}
		if (sub.resultType === 'PTS') return t('discipline.points');
		if (sub.resultType === 'TIM') return t('discipline.time');
		return '';
	};

	/** "3 editions · 2021–2026". */
	const heldSubtitle = (editions) => {
		const years = editions.map((e) => e.year);
		return `${t('disciplines.editions', { n: years.length })} · ${yearSpan(years)}`;
	};
</script>

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: t('nav.disciplines') }]} />
	<h1>{t('disciplines.title')}</h1>

	<div class="grid">
		{#each disciplines as discipline}
			<!-- An unrevealed discipline stays reachable: its page still shows the pairings. -->
			<DisciplineCard
				href="/{year}/disciplines/{discipline.id}"
				discipline={discipline.name}
				name={disciplineName(locale, discipline.name)}
				subtitle={subtitle(disciplineSubtitle(data.summary, discipline))}
				unrevealed={!discipline.reveal_score}
			/>
		{/each}
	</div>

	{#if held.length > 0}
		<section aria-labelledby="all-time">
			<h2 id="all-time">{t('disciplines.allTime')}</h2>
			<p class="intro">{t('disciplines.allTimeIntro')}</p>
			<div class="grid">
				{#each held as discipline}
					{@const name = disciplineName(locale, discipline.name)}
					<!-- Named apart from the edition's card of the same discipline above. -->
					<DisciplineCard
						href={allTimePath(discipline, year)}
						discipline={discipline.name}
						{name}
						subtitle={heldSubtitle(discipline.editions)}
						label={t('disciplines.allTimeOf', { name })}
						data-testid="all-time-card"
					/>
				{/each}
			</div>
		</section>
	{/if}
</div>

<style>
	h1 {
		margin: 0 0 0.8rem;
	}

	h2 {
		margin: 0 0 0.2rem;
	}

	.intro {
		margin: 0 0 0.8rem;
		color: var(--muted);
	}

	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
		margin-bottom: 2rem;
	}

	@media (max-width: 580px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
