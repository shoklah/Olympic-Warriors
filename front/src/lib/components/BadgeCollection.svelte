<script>
	import { tick } from 'svelte';
	import { enhance } from '$app/forms';
	import Badge from './Badge.svelte';
	import BadgeSheet from './BadgeSheet.svelte';
	import { slotLabel } from '$lib/badges';
	import { useT } from '$lib/i18n';

	/** badgeCollection(profile.badges ?? []); the page computes it once and passes it down. */
	export let collection;
	/** profile.badge_stats ({ players, holders, tiers }), or null (an older API). */
	export let badgeStats = null;
	/** The viewer's own profile: « Choisir ma vitrine » offers the selection mode below. */
	export let editable = false;
	/** profile.showcase ({ auto, badges }), or null (an older API): the pins a selection starts from. */
	export let showcase = null;

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
		const code = openCode;
		openCode = null;
		openButton?.focus();
		// Returning focus to the slot (below) must not pop its tooltip straight back up:
		// treat it as already dismissed, the same way Escape does.
		if (code) dismissedCode = code;
		openButton = null;
	}

	// --- Hover/focus tooltip (desktop only: gated by @media (hover: hover) and (pointer:
	// fine) in CSS). The rule itself reaches every device through aria-describedby, on a
	// visually hidden span that's always in the DOM, regardless of pointer type. Display is
	// driven entirely from the state below, not from raw :hover/:focus-visible on .tooltip:
	// those are independent per element, so two slots (one hovered, another still focused)
	// could otherwise both show at once.

	/** Half the tooltip's 16rem max width, in px, scaled to the root font size (a larger
	    user text size still needs to fit): "measure it" isn't possible while it's
	    display: none, so this is the width its max-width would give it instead. */
	function tooltipHalfWidth() {
		if (typeof document === 'undefined') return 128;
		const root = parseFloat(getComputedStyle(document.documentElement).fontSize);
		return (Number.isFinite(root) ? root : 16) * 8;
	}

	/** 'left' | 'right' | 'center': edge slots align a side instead of centring, so the
	    tooltip never overflows the viewport. clientWidth, not window.innerWidth, which
	    counts a classic scrollbar as usable width when it isn't. */
	function edgeAlign(rect) {
		if (typeof document === 'undefined') return 'center';
		const half = tooltipHalfWidth();
		const mid = rect.left + rect.width / 2;
		const viewport = document.documentElement.clientWidth;
		if (mid - half < 0) return 'left';
		if (mid + half > viewport) return 'right';
		return 'center';
	}

	/** Whichever slot the pointer is over, and whichever has keyboard focus, tracked
	    separately so only one tooltip ever shows: a hover always wins over a focus left
	    behind on another slot. */
	let hoveredCode = null;
	let focusedCode = null;
	let hoverAlign = 'center';
	let focusAlign = 'center';
	/** Escape hid this slot's tooltip (or the sheet closing returned focus to it, which
	    must not pop the tooltip back up either). Cleared once neither hover nor focus is
	    on it any more, so it shows again next time (WCAG 1.4.13: dismissible without
	    losing the hover/focus target). */
	let dismissedCode = null;

	$: tooltipCode = hoveredCode ?? focusedCode;
	$: tooltipAlign = hoveredCode !== null ? hoverAlign : focusAlign;
	$: tooltipShown = tooltipCode !== null && tooltipCode !== dismissedCode;
	$: if (dismissedCode !== null && dismissedCode !== hoveredCode && dismissedCode !== focusedCode) {
		dismissedCode = null;
	}

	function onHoverEnter(slot, event) {
		hoveredCode = slot.code;
		hoverAlign = edgeAlign(event.currentTarget.getBoundingClientRect());
	}

	function onHoverLeave(slot) {
		if (hoveredCode === slot.code) hoveredCode = null;
	}

	function onFocusIn(slot, event) {
		focusedCode = slot.code;
		focusAlign = edgeAlign(event.currentTarget.getBoundingClientRect());
	}

	function onFocusOut(slot) {
		if (focusedCode === slot.code) focusedCode = null;
	}

	/** Escape dismisses whichever tooltip is showing, wherever focus is (a hover-only
	    tooltip has no button to catch a keydown on): the sheet handles its own Escape
	    when it's open, so this steps aside then. */
	function onWindowKey(event) {
		if (event.key !== 'Escape' || openCode !== null) return;
		if (tooltipCode !== null) dismissedCode = tooltipCode;
	}

	// --- Showcase selection (the owner only). « Choisir ma vitrine » turns the earned slots
	// into toggles numbered in pick order and disables the locked ones; the bar at the bottom
	// saves or cancels, and « Revenir à l'automatique » under the intro drops the pins. The
	// forms post to the page's `showcase` action, which puts the codes to the API.

	/** A showcase holds this many badges, as the API checks. */
	const SHOWCASE_SIZE = 3;
	const FAILED = 'showcase.error.failed';

	/** The selection mode is on: a slot click toggles the slot instead of opening its sheet. */
	let selecting = false;
	/** The codes picked, in pick order: a slot's place in the showcase is its index plus one. */
	let picks = [];
	/** Fourth picks refused since the last change: the status line then states the limit.
	    A count, not a flag, so a second refusal re-renders the line and is read out again. */
	let refused = 0;
	/** A save (or the return to automatic) is on its way: every control holds until it answers. */
	let busy = false;
	/** A dictionary key for the alert line, or null. */
	let error = null;
	/** « Choisir ma vitrine », given focus back when the mode ends. */
	let chooseButton = null;
	/** The intro line, focused when the mode starts: it says what the toggles are for. */
	let introEl = null;

	// The page stops being the viewer's own (another profile, a logout), or leaves nothing to
	// choose from: the mode ends with it.
	$: if (!editable || collection.earned === 0) selecting = false;

	/** The current pins still earned, in pin order; none while the showcase is automatic. */
	function currentPins() {
		if (!showcase || showcase.auto) return [];
		const earned = new Set(
			collection.families.flatMap((f) => f.slots).filter((slot) => slot.earned).map((slot) => slot.code)
		);
		const codes = (showcase.badges ?? []).map((badge) => badge.code).filter((code) => earned.has(code));
		return [...new Set(codes)].slice(0, SHOWCASE_SIZE);
	}

	async function startSelecting() {
		picks = currentPins();
		refused = 0;
		error = null;
		selecting = true;
		await tick();
		introEl?.focus();
	}

	/** Leave the mode, the picks dropped (the next one starts from the pins again), and give
	    focus back to « Choisir ma vitrine », which comes back in place of the intro. */
	async function stopSelecting() {
		selecting = false;
		picks = [];
		refused = 0;
		error = null;
		await tick();
		chooseButton?.focus();
	}

	/** Annuler: nothing is sent, the pins stay as they were. */
	function cancel() {
		if (!busy) stopSelecting();
	}

	/** Pick or unpick an earned slot; taking one back renumbers the ones after it. */
	function toggle(slot) {
		if (busy || !slot.earned) return;
		if (picks.includes(slot.code)) {
			picks = picks.filter((code) => code !== slot.code);
		} else if (picks.length < SHOWCASE_SIZE) {
			picks = [...picks, slot.code];
		} else {
			refused += 1;
			return;
		}
		refused = 0;
	}

	/** The key of a fail() from the page's own action, or the generic one. */
	const failureKey = (data) =>
		typeof data?.error === 'string' && data.error.startsWith('showcase.error.') ? data.error : FAILED;

	/**
	 * use:enhance for Save and « Revenir à l'automatique », whose form posts no code. A success
	 * re-runs the loads (reset: false: the hidden fields are the picks, nothing to blank), so
	 * the header's showcase and `showcase` here follow, then the mode ends. A failure keeps
	 * the mode and the picks, with the alert. A thrown error is only worded, never applied:
	 * SvelteKit would swap the whole page for its error page.
	 */
	const submit = ({ cancel: drop }) => {
		if (busy) {
			drop();
			return;
		}
		busy = true;
		error = null;
		return async ({ result, update }) => {
			if (result.type === 'success') {
				try {
					await update({ reset: false });
				} catch {
					// A load failing shows its own error page: nothing to add here.
				}
				busy = false;
				await stopSelecting();
				return;
			}
			busy = false;
			error = result.type === 'failure' ? failureKey(result.data) : FAILED;
		};
	};
</script>

<svelte:window on:keydown={onWindowKey} />

<h2 class="visually-hidden">{t('profile.badges')}</h2>

<div class="progress">
	<p>{t('badge.progress', { n: collection.earned, total: collection.total })}</p>
	<div class="bar" aria-hidden="true"><div class="fill" style="width: {pct}%"></div></div>
	<span class="pct num" aria-hidden="true">{pct}%</span>
</div>

<!-- Nothing to choose from without an earned badge. -->
{#if editable && collection.earned > 0}
	{#if selecting}
		<div class="picker-intro">
			<!-- Focused when the mode starts, only to be read out: not a control. -->
			<p tabindex="-1" bind:this={introEl}>{t('showcase.intro', { max: SHOWCASE_SIZE })}</p>
			{#if showcase && !showcase.auto}
				<!-- No codes: the action puts [], back to the rarest badges. aria-disabled rather
				     than disabled while saving, so the focused button keeps focus. -->
				<form method="POST" action="?/showcase" use:enhance={submit}>
					<button type="submit" class="action" aria-disabled={busy ? 'true' : undefined}
						>{t('showcase.automatic')}</button
					>
				</form>
			{/if}
		</div>
	{:else}
		<button type="button" class="action choose" bind:this={chooseButton} on:click={startSelecting}
			>{t('showcase.choose')}</button
		>
	{/if}
{/if}

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
				<!-- The slot's place in the showcase being chosen, 1 to 3, or 0. -->
				{@const place = selecting ? picks.indexOf(slot.code) + 1 : 0}
				<!-- Outside the selection mode, aria-pressed, aria-disabled and disabled are all
				     left out: the slot is the plain button opening its sheet. -->
				<button
					type="button"
					class="slot"
					class:tooltip-shown={tooltipShown && tooltipCode === slot.code}
					class:align-left={tooltipCode === slot.code && tooltipAlign === 'left'}
					class:align-right={tooltipCode === slot.code && tooltipAlign === 'right'}
					on:click={(event) => (selecting ? toggle(slot) : openSheet(slot, event))}
					on:mouseenter={(event) => onHoverEnter(slot, event)}
					on:mouseleave={() => onHoverLeave(slot)}
					on:focus={(event) => onFocusIn(slot, event)}
					on:blur={() => onFocusOut(slot)}
					aria-label={slotLabel(slot, t)}
					aria-describedby={place > 0 ? `place-${slot.code} rule-${slot.code}` : `rule-${slot.code}`}
					aria-pressed={selecting && slot.earned ? String(place > 0) : undefined}
					aria-disabled={selecting && slot.earned && busy ? 'true' : undefined}
					disabled={selecting && !slot.earned}
				>
					<span class="medallion">
						<Badge badge={slot.medal} locked={!slot.earned} />
						{#if slot.earned && slot.count > 1}
							<span class="chip num" aria-hidden="true">{t('badge.times', { n: slot.count })}</span>
						{/if}
						{#if place > 0}
							<span class="place num" aria-hidden="true" data-testid="order">{place}</span>
						{/if}
					</span>
					<span class="name" class:muted={!slot.earned} aria-hidden="true">{t(`badge.${slot.code}.name`)}</span>
					{#if place > 0}
						<!-- The place is the description's first part: the name stays the same
						     whether the toggle is pressed or not. -->
						<span id="place-{slot.code}" class="visually-hidden">{t('showcase.place', { n: place })}</span>
					{/if}
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

{#if selecting}
	<!-- After the slots, so the keyboard reaches it last, and held at the bottom of the screen
	     while they scroll by, so Save is at hand from the first family to the last. -->
	<div class="picker" data-testid="showcase-picker">
		{#if error}
			<p class="picker-error" role="alert">{t(error)}</p>
		{/if}
		<p class="picker-status" role="status">
			{#if busy}
				{t('showcase.saving')}
			{:else if refused > 0}
				{#key refused}<span class="limit">{t('showcase.limit', { max: SHOWCASE_SIZE })}</span>{/key}
			{:else}
				<span class="label" aria-hidden="true">{t('showcase.label')}</span>
				<span class="num count" aria-hidden="true">{picks.length}/{SHOWCASE_SIZE}</span>
				<span class="visually-hidden">{t('showcase.picked', { n: picks.length, max: SHOWCASE_SIZE })}</span>
			{/if}
		</p>
		<button type="button" class="action" disabled={busy} on:click={cancel}>{t('showcase.cancel')}</button>
		<form method="POST" action="?/showcase" use:enhance={submit}>
			{#each picks as code (code)}
				<input type="hidden" name="codes" value={code} />
			{/each}
			<button type="submit" class="action primary" aria-disabled={busy ? 'true' : undefined}
				>{t('showcase.save')}</button
			>
		</form>
	</div>
{/if}

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

	/* Only a real pointer gets the hover tooltip: a touch tap opens the sheet directly.
	   Display is driven by the JS-tracked .tooltip-shown class, not raw :hover/
	   :focus-visible, so only one slot's tooltip is ever shown at a time. */
	@media (hover: hover) and (pointer: fine) {
		.slot.tooltip-shown .tooltip {
			display: block;
		}
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
		/* break-word + hyphens, not overflow-wrap: anywhere, which was splitting words
		   mid-letter ("Rassembleu/r"); html lang is set, so hyphenation picks the right
		   dictionary. */
		overflow-wrap: break-word;
		hyphens: auto;
		color: var(--ink);
	}

	.name.muted {
		color: var(--muted);
	}

	/* --- Showcase selection. */

	.action {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 44px;
		padding: 0 1rem;
		border: 1px solid var(--accent);
		border-radius: var(--radius);
		background: transparent;
		color: var(--accent);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		cursor: pointer;
	}

	.action.primary {
		background: var(--accent);
		color: var(--bg);
	}

	.action:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.action:disabled,
	.action[aria-disabled='true'] {
		opacity: 0.35;
		cursor: default;
	}

	.choose {
		margin: 0 0 1.4rem;
	}

	.picker-intro {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 8px 16px;
		margin: 0 0 1.4rem;
	}

	.picker-intro p {
		flex: 1 1 14rem;
		margin: 0;
		color: var(--text);
	}

	.picker-intro p:focus {
		outline: none;
	}

	/* A picked slot: ringed in the accent, its place on the medallion's upper left (the ×N
	   chip keeps the lower right). */
	.slot[aria-pressed='true'] {
		background: var(--bg-raised);
		box-shadow: inset 0 0 0 1px var(--accent);
	}

	.place {
		position: absolute;
		left: -6px;
		top: -4px;
		display: grid;
		place-items: center;
		min-width: 1.4rem;
		height: 1.4rem;
		padding: 0 4px;
		border-radius: var(--radius-pill);
		background: var(--accent);
		color: var(--bg);
		font-size: 0.95rem;
		line-height: 1;
	}

	/* A locked slot cannot be picked: fainter still, and no hover colour. */
	.slot:disabled {
		cursor: default;
	}

	.slot:disabled .medallion,
	.slot:disabled .name {
		opacity: 0.5;
	}

	.slot:disabled:hover .name {
		color: var(--muted);
	}

	/* Above the phones' bottom tab bar, and clear of the screen's edge everywhere. On a phone
	   the status takes a line of its own and the two buttons share the next, so a longer
	   status (« 3 badges maximum », « Enregistrement… ») never pushes a button off the row;
	   from 480px everything sits on one line. */
	.picker {
		position: sticky;
		bottom: 8px;
		z-index: 10;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		margin: 0 0 1.6rem;
		padding: 10px 12px;
		background: var(--bg-raised);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius-lg);
	}

	@media (max-width: 999.98px) {
		:global(.app.has-tabbar) .picker {
			bottom: calc(var(--tabbar) + 8px);
		}
	}

	.picker-error {
		flex: 1 1 100%;
		margin: 0;
		color: var(--loss);
		font-size: 0.85rem;
	}

	.picker-status {
		display: flex;
		align-items: baseline;
		gap: 8px;
		flex: 1 1 100%;
		min-height: 1.3rem;
		margin: 0;
		font-size: 0.85rem;
		color: var(--text);
	}

	.picker > .action,
	.picker form {
		flex: 1 1 0;
	}

	.picker form {
		display: flex;
	}

	.picker form .action {
		flex: 1;
	}

	@media (min-width: 480px) {
		.picker-status {
			flex: 1 1 auto;
		}

		.picker > .action,
		.picker form {
			flex: none;
		}
	}

	.count {
		font-size: 1.3rem;
		line-height: 1;
		color: var(--ink);
	}

	.limit {
		color: var(--accent);
		font-weight: 600;
	}
</style>
