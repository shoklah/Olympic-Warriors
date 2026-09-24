<script>
	import Badge from './Badge.svelte';
	import BadgeSheet from './BadgeSheet.svelte';
	import { useT } from '$lib/i18n';

	/** badgeCollection(profile.badges ?? []); the page computes it once and passes it down. */
	export let collection;
	/** profile.badge_stats ({ players, holders, tiers }), or null (an older API). */
	export let badgeStats = null;

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

	// --- Hover/focus tooltip (desktop only: gated by @media (hover: hover) and (pointer:
	// fine) in CSS). The rule itself reaches every device through aria-describedby, on a
	// visually hidden span that's always in the DOM, regardless of pointer type.

	/** Roughly half the tooltip's 16rem max width, to keep it inside the viewport. */
	const TOOLTIP_HALF_WIDTH = 130;

	/** 'left' | 'right' | 'center': edge slots align a side instead of centring, so the
	    tooltip never overflows the viewport. */
	function edgeAlign(rect) {
		if (typeof window === 'undefined') return 'center';
		const mid = rect.left + rect.width / 2;
		if (mid - TOOLTIP_HALF_WIDTH < 0) return 'left';
		if (mid + TOOLTIP_HALF_WIDTH > window.innerWidth) return 'right';
		return 'center';
	}

	/** The slot currently hovered or keyboard-focused, or null. */
	let tooltipCode = null;
	let tooltipAlign = 'center';
	/** Escape hid the tooltip; cleared once the pointer leaves or focus moves, so it shows
	    again next time (WCAG 1.4.13: dismissible without losing the hover/focus target). */
	let tooltipDismissed = false;

	function showTooltip(slot, event) {
		tooltipCode = slot.code;
		tooltipDismissed = false;
		tooltipAlign = edgeAlign(event.currentTarget.getBoundingClientRect());
	}

	function hideTooltip(slot) {
		if (tooltipCode === slot.code) {
			tooltipCode = null;
			tooltipDismissed = false;
		}
	}

	function onSlotKey(event, slot) {
		if (event.key === 'Escape' && tooltipCode === slot.code) tooltipDismissed = true;
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
				<button
					type="button"
					class="slot"
					class:tooltip-dismissed={tooltipDismissed && tooltipCode === slot.code}
					class:align-left={tooltipCode === slot.code && tooltipAlign === 'left'}
					class:align-right={tooltipCode === slot.code && tooltipAlign === 'right'}
					on:click={(event) => openSheet(slot, event)}
					on:mouseenter={(event) => showTooltip(slot, event)}
					on:mouseleave={() => hideTooltip(slot)}
					on:focus={(event) => showTooltip(slot, event)}
					on:blur={() => hideTooltip(slot)}
					on:keydown={(event) => onSlotKey(event, slot)}
					aria-label={slotLabel(slot)}
					aria-describedby="rule-{slot.code}"
				>
					<span class="medallion">
						<Badge badge={slot.medal} locked={!slot.earned} />
						{#if slot.earned && slot.count > 1}
							<span class="chip num" aria-hidden="true">{t('badge.times', { n: slot.count })}</span>
						{/if}
					</span>
					<span class="name" class:muted={!slot.earned} aria-hidden="true">{t(`badge.${slot.code}.name`)}</span>
					<!-- Always in the DOM (just visually hidden), so every device's screen
					     reader gets the rule as the button's description, not only a mouse. -->
					<span id="rule-{slot.code}" class="visually-hidden">{t(`badge.${slot.code}.rule`)}</span>
					<!-- Purely visual, desktop-only companion of the line above: a hover/focus
					     tooltip, hidden from assistive tech so the rule isn't announced twice. -->
					<span class="tooltip" aria-hidden="true">
						<span class="tooltip-box">
							<span class="tooltip-name label">{t(`badge.${slot.code}.name`)}</span>
							<span class="tooltip-rule">{t(`badge.${slot.code}.rule`)}</span>
						</span>
					</span>
				</button>
			{/each}
		</div>
	</section>
{/each}

<BadgeSheet slot={activeSlot} open={activeSlot !== null} {badgeStats} on:close={closeSheet} />

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
		position: relative;
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

	.tooltip {
		position: absolute;
		left: 50%;
		bottom: 100%;
		transform: translateX(-50%);
		/* The gap to the slot lives inside this padding, not as a margin, so the pointer
		   never crosses a dead zone between the slot and the tooltip (WCAG 1.4.13: the
		   tooltip must stay up while the pointer moves onto it). */
		padding-bottom: 8px;
		width: max-content;
		max-width: 16rem;
		z-index: 5;
		/* display: none, not opacity/visibility: a hidden tooltip still occupies its full
		   (up to 16rem) box otherwise, which was widening the page's scrollable area for
		   every slot near an edge even though nothing was shown. */
		display: none;
	}

	.tooltip-box {
		display: block;
		padding: 8px 10px;
		background: var(--bg-raised);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		text-align: center;
	}

	.tooltip-name {
		display: block;
		margin-bottom: 2px;
	}

	.tooltip-rule {
		display: block;
		font-size: 0.78rem;
		line-height: 1.3;
		color: var(--text);
	}

	.slot.align-left .tooltip {
		left: 0;
		transform: none;
	}

	.slot.align-right .tooltip {
		left: auto;
		right: 0;
		transform: none;
	}

	/* Only a real pointer gets the hover tooltip: a touch tap opens the sheet directly. */
	@media (hover: hover) and (pointer: fine) {
		.slot:hover .tooltip,
		.slot:focus-visible .tooltip {
			display: block;
		}
	}

	/* Escape hid it: this must win over the :hover/:focus-visible rule above regardless of
	   which fires last, hence the equal-specificity + later-source-order pairing. */
	.slot.tooltip-dismissed .tooltip {
		display: none;
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
