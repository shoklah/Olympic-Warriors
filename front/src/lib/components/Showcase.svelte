<script>
	import Badge from './Badge.svelte';
	import BadgeSheet from './BadgeSheet.svelte';
	import { isKnownBadge, slotLabel } from '$lib/badges';
	import { useT } from '$lib/i18n';

	/**
	 * The showcase, `[{ code, tier, discipline }]` in display order: a /profiles/ row's
	 * `showcase`, or the `showcase.badges` of /profile/<id>/. Each medallion is drawn from its
	 * entry, which the server picks the way a collection slot picks its medal (the highest
	 * tier, else the first entry), so the metal, the pips and a specialist's discipline icon
	 * match the collection.
	 */
	export let badges = [];
	/**
	 * 'row': a leaderboard row, which is one link and cannot hold buttons, so the medallions
	 * are aria-hidden at 1.25rem and the row's hidden sentence names them (`showcaseLabel`).
	 * 'interactive': the profile header, each medallion a button opening its BadgeSheet.
	 */
	export let mode = 'row';
	/** interactive: the page's `badgeCollection(profile.badges)`, holding each medallion's slot. */
	export let collection = null;
	/** interactive: the profile's `badge_stats`, for the sheet's rarity line, or null. */
	export let badgeStats = null;
	/** interactive: the profile's `progress`, for the sheet's progress bar, [] from an older API. */
	export let progress = [];
	/** interactive: the owner looks at an automatic showcase, so a quiet line says how it is picked. */
	export let autoHint = false;
	/**
	 * row: each medallion shows its name and rule in a tooltip under a real pointer (the row
	 * is one link, so there is no per-badge focus: the row's hidden sentence names them).
	 */
	export let tips = false;
	/** row: 2.75rem medallions from 800px (below it the row stays small, on its own line). */
	export let large = false;

	const t = useT();

	$: slots = new Map((collection?.families ?? []).flatMap((family) => family.slots).map((slot) => [slot.code, slot]));
	// A code the front does not know (a newer server) is left out. So is, in the header, a
	// code without an earned slot to open: the showcase and the badges come from the same
	// rows, so only a payload at odds with itself would have one.
	$: shown = (badges ?? []).filter(
		(badge) => isKnownBadge(badge) && (mode !== 'interactive' || slots.get(badge.code)?.earned)
	);

	// The sheet opens and gives focus back the way BadgeCollection's does.
	/** The code of the medallion whose sheet is open, or null. */
	let openCode = null;
	/** The button that opened the sheet, refocused when it closes. */
	let openButton = null;

	$: activeSlot = openCode ? (slots.get(openCode) ?? null) : null;

	function openSheet(code, event) {
		openCode = code;
		openButton = event.currentTarget;
	}

	function closeSheet() {
		openCode = null;
		openButton?.focus();
		openButton = null;
	}
</script>

<!-- Nothing at all without a badge to show: no empty line under the name. -->
{#if shown.length > 0}
	{#if mode === 'interactive'}
		<ul class="showcase interactive" role="list" aria-label={t('showcase.label')} data-testid="showcase">
			{#each shown as badge}
				<li class="item">
					<button
						type="button"
						aria-label={slotLabel(slots.get(badge.code), t)}
						aria-describedby="showcase-rule-{badge.code}"
						on:click={(event) => openSheet(badge.code, event)}
					>
						<Badge {badge} />
						<!-- The rule as the description, as on the collection's slots (without their
						     hover tooltip: the sheet this opens states the rule too). -->
						<span id="showcase-rule-{badge.code}" class="visually-hidden">{t(`badge.${badge.code}.rule`)}</span>
					</button>
					<span
						class="tooltip"
						aria-hidden="true"
						data-name={t(`badge.${badge.code}.name`)}
						data-rule={t(`badge.${badge.code}.rule`)}
					></span>
				</li>
			{/each}
		</ul>
		{#if autoHint}
			<p class="hint">{t('showcase.autoHint')}</p>
		{/if}
		<BadgeSheet slot={activeSlot} open={activeSlot !== null} {badgeStats} {progress} on:close={closeSheet} />
	{:else}
		<span class="showcase row" class:large aria-hidden="true" data-testid="showcase">
			{#each shown as badge}
				{#if tips}
					<span class="item">
						<Badge {badge} />
						<!-- Drawn from the attributes by CSS so the text stays out of the row's content. -->
						<span
							class="tooltip"
							data-name={t(`badge.${badge.code}.name`)}
							data-rule={t(`badge.${badge.code}.rule`)}
						></span>
					</span>
				{:else}
					<Badge {badge} />
				{/if}
			{/each}
		</span>
	{/if}
{/if}

<style>
	.showcase {
		display: flex;
		align-items: center;
	}

	/* Badge draws a pip row under each ring: its gap (8% of the size) then its pips (7%, at
	   least 0.3125rem). A page setting `--showcase-hang: 1`, where the medallions sit inline
	   after a name, lets that row hang below the line: the rings then centre on the name and
	   a row with a showcase is no taller than one without. */
	.row {
		--badge-size: 1.25rem;
		flex: none;
		gap: 4px;
		margin-bottom: calc(
			var(--showcase-hang, 0) * -1 * (var(--badge-size) * 0.08 + max(0.3125rem, var(--badge-size) * 0.07))
		);
	}

	@media (min-width: 800px) {
		.row.large {
			--badge-size: 2.75rem;
			gap: 8px;
		}
	}

	/* Below 600px the leaderboard gives the showcase a line of its own under the name, which
	   five medallions can outgrow with a large default font size: they wrap. */
	@media (max-width: 599.98px) {
		.row {
			flex-wrap: wrap;
		}
	}

	.item {
		position: relative;
		display: block;
	}

	/* The tooltip sits under the medallion (name and rule drawn from its data attributes). The
	   first two align to the left edge and the last two to the right, so it never leaves the row. */
	.tooltip {
		position: absolute;
		top: calc(100% + 6px);
		left: 50%;
		transform: translateX(-50%);
		width: max-content;
		max-width: 16rem;
		padding: 8px 10px;
		background: var(--bg-raised);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		text-align: center;
		z-index: 5;
		display: none;
	}

	.tooltip::before {
		content: attr(data-name);
		display: block;
		margin-bottom: 2px;
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--muted);
	}

	.tooltip::after {
		content: attr(data-rule);
		display: block;
		font-size: 0.78rem;
		line-height: 1.3;
		color: var(--text);
	}

	.item:nth-child(-n + 2) .tooltip {
		left: 0;
		transform: none;
	}

	.item:nth-last-child(-n + 2) .tooltip {
		left: auto;
		right: 0;
		transform: none;
	}

	.item:nth-child(1):nth-last-child(-n + 2) .tooltip,
	.item:nth-child(2):nth-last-child(-n + 2) .tooltip {
		left: 0;
		right: auto;
	}

	@media (hover: hover) and (pointer: fine) {
		.item:hover .tooltip {
			display: block;
		}
	}

	/* The profile's medallions are buttons: keyboard focus shows it too. */
	.interactive button:focus-visible + .tooltip {
		display: block;
	}

	/* Pulled back by the buttons' padding, so the rings line up with the name above. */
	.interactive {
		flex-wrap: wrap;
		gap: 6px;
		--badge-size: 2.5rem;
		margin: 0;
		margin-inline-start: -3px;
		padding: 0;
		list-style: none;
	}

	.interactive button {
		display: grid;
		place-items: center;
		padding: 3px;
		background: none;
		border: none;
		border-radius: var(--radius);
		color: inherit;
		font: inherit;
		cursor: pointer;
		transition: transform 0.2s ease;
	}

	.interactive button:hover {
		transform: translateY(-2px);
	}

	.interactive button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.hint {
		margin: 0;
		font-size: 0.8rem;
		color: var(--muted);
	}

	@media (min-width: 600px) {
		.interactive {
			gap: 8px;
			--badge-size: 3rem;
		}
	}
</style>
