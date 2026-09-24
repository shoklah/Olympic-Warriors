<script>
	import Badge from './Badge.svelte';
	import BadgeSheet from './BadgeSheet.svelte';
	import { useT } from '$lib/i18n';

	/** badgeCollection(profile.badges ?? []); the page computes it once and passes it down. */
	export let collection;

	const t = useT();

	$: pct = collection.total ? Math.round((100 * collection.earned) / collection.total) : 0;

	/** The code of the slot whose sheet is open, or null. */
	let openCode = null;
	/** The button that opened the sheet, refocused when it closes. */
	let openButton = null;

	$: activeSlot = openCode
		? collection.families.flatMap((f) => f.slots).find((s) => s.code === openCode)
		: null;

	function openSheet(slot, event) {
		openCode = slot.code;
		openButton = event.currentTarget;
	}

	function closeSheet() {
		openCode = null;
		openButton?.focus();
		openButton = null;
	}

	/**
	 * The button's accessible name: "<name>, <earned|locked>" or, above ×1,
	 * "<name>, badge earned N times" (a plural key, so a screen reader never hears "×2").
	 */
	function slotLabel(slot) {
		const name = t(`badge.${slot.code}.name`);
		if (!slot.earned) return `${name}, ${t('badge.locked')}`;
		if (slot.count > 1) return `${name}, ${t('badge.earnedTimes', { n: slot.count })}`;
		return `${name}, ${t('badge.earned')}`;
	}
</script>

<h2 class="visually-hidden">{t('profile.badges')}</h2>

<div class="progress">
	<p>{t('badge.progress', { n: collection.earned, total: collection.total })}</p>
	<div class="bar" aria-hidden="true"><div class="fill" style="width: {pct}%"></div></div>
	<span class="pct num" aria-hidden="true">{pct}%</span>
</div>

{#each collection.families as family (family.key)}
	<section class="family">
		<h3 class="label">
			{t(`badge.family.${family.key}`)}
			<!-- "3/5" reads as a fraction or a date to a screen reader: hide it and say the
			     count in words instead. -->
			<span aria-hidden="true">{family.earned}/{family.total}</span>
			<span class="visually-hidden"
				>{t('badge.familyProgress', { earned: family.earned, total: family.total })}</span
			>
		</h3>
		<div class="slots">
			{#each family.slots as slot (slot.code)}
				<button type="button" class="slot" on:click={(event) => openSheet(slot, event)} aria-label={slotLabel(slot)}>
					<span class="medallion">
						<Badge badge={slot.medal} locked={!slot.earned} />
						{#if slot.earned && slot.count > 1}
							<span class="chip num" aria-hidden="true">{t('badge.times', { n: slot.count })}</span>
						{/if}
					</span>
					<span class="name" class:muted={!slot.earned} aria-hidden="true">{t(`badge.${slot.code}.name`)}</span>
				</button>
			{/each}
		</div>
	</section>
{/each}

<BadgeSheet slot={activeSlot} open={activeSlot !== null} on:close={closeSheet} />

<style>
	.progress {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		margin-bottom: 1.4rem;
	}

	.progress p {
		margin: 0;
		flex: 1 1 auto;
		min-width: 12rem;
	}

	.bar {
		flex: 1 1 10rem;
		height: 6px;
		border-radius: var(--radius-pill);
		background: var(--line);
		overflow: hidden;
	}

	.fill {
		height: 100%;
		background: var(--accent);
	}

	.pct {
		color: var(--muted);
		font-size: 0.95rem;
	}

	.family {
		margin-bottom: 1.6rem;
	}

	.family h3 {
		margin: 0 0 0.6rem;
	}

	.slots {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(4.75rem, 1fr));
		gap: 14px 8px;
		--badge-size: 48px;
	}

	.slot {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding: 4px;
		background: none;
		border: none;
		border-radius: var(--radius);
		cursor: pointer;
		font: inherit;
		color: inherit;
	}

	.slot:hover .name {
		color: var(--accent);
	}

	.slot:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.medallion {
		position: relative;
	}

	.chip {
		position: absolute;
		right: -6px;
		bottom: -2px;
		padding: 1px 5px;
		border-radius: var(--radius-pill);
		background: var(--accent);
		color: var(--bg);
		font-size: 0.7rem;
		line-height: 1.4;
	}

	.name {
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		overflow: hidden;
		max-width: 100%;
		font-size: 0.78rem;
		line-height: 1.25;
		text-align: center;
		overflow-wrap: anywhere;
		color: var(--ink);
	}

	.name.muted {
		color: var(--muted);
	}
</style>
