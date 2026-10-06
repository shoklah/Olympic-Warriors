<script>
	import { createEventDispatcher, tick } from 'svelte';
	import { useLocale, useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { modal } from '$lib/modal';
	import { playerProfile } from '$lib/builder/profile.js';
	import { compareProfiles } from '$lib/builder/compare.js';
	import { normalise } from '$lib/builder/names.js';

	export let open = false;
	export let player = null;
	export let skills;
	/** The team's index, -1 for a player still in the tray. */
	export let teamIndex = -1;
	/** What had focus before the sheet opened: it gets it back on close. */
	export let opener = null;
	/** Every other player, for the compare picker: `{ id, name, teamIndex, rating }`. */
	export let candidates = [];
	/** The player compared with, and their team's index (-1 for the tray). */
	export let other = null;
	export let otherTeamIndex = -1;
	/** Why the swap is unavailable (`locked`, `sameTeam`, `bothTray`, `blocked`), null when it is. */
	export let swapReason = null;
	/** What the swap would change (`swapPreview`), null when it is unavailable. */
	export let swapView = null;

	const t = useT();
	const locale = useLocale();
	const dispatch = createEventDispatcher();

	let sheetEl = null;
	$: if (open && sheetEl) tick().then(() => sheetEl?.focus());

	let picking = false;
	let query = '';
	// A sheet opened on another player starts on their own profile.
	let pickedFor = null;
	$: if (!open || player?.id !== pickedFor) {
		pickedFor = player?.id ?? null;
		picking = false;
	}

	function close() {
		dispatch('close');
		opener?.focus();
	}
	// Escape closes the picker first, the sheet only when none is open.
	function escape() {
		if (picking) {
			picking = false;
			focusAction();
		} else close();
	}
	// The button that opened the picker is back after it closes: focus goes to it, not to the page.
	async function focusAction() {
		await tick();
		sheetEl?.querySelector('[data-compare-action]')?.focus();
	}
	function openPicker() {
		query = '';
		picking = true;
	}
	function choose(id) {
		picking = false;
		dispatch('compare', { id });
		focusAction();
	}
	const focusNow = (node) => node.focus();

	$: shownCandidates = candidates.filter((c) => normalise(c.name).includes(normalise(query.trim())));
	$: comparing = other && !picking;
	$: table = comparing ? compareProfiles(player, other, skills, locale) : null;
	$: otherName = other ? fullName(other) : '';
	const where = (index) => (index >= 0 ? t('builder.team', { n: index + 1 }) : t('builder.preview.tray'));
	const direction = (before, after) => Math.sign(Math.round(after * 10) - Math.round(before * 10));
	const shownRating = (value) => value.toFixed(1);
	const sportLine = (sport) =>
		[sport.sport, sport.level && t(`register.level.${sport.level}`)].filter(Boolean).join(' · ');

	$: profile = player ? playerProfile(player, skills, locale) : null;
	$: name = player ? fullName(player) : '';
	const shown = (value) => Math.round(value * 10) / 10;
</script>

{#if open && player}
	<div class="backdrop" data-testid="backdrop" on:click={close} aria-hidden="true"></div>
	<div
		class="sheet"
		role="dialog"
		aria-modal="true"
		aria-labelledby="player-sheet-title"
		class:wide={comparing}
		tabindex="-1"
		bind:this={sheetEl}
		use:modal={{ onClose: escape }}
	>
		<h2 id="player-sheet-title">{name}</h2>
{#if picking}
		<h3>{t('builder.compare.pick', { name })}</h3>
		<input
			class="search"
			type="search"
			aria-label={t('builder.compare.search')}
			placeholder={t('builder.compare.search')}
			bind:value={query}
			use:focusNow
		/>
		{#if shownCandidates.length === 0}
			<p class="none">{t('builder.compare.noResults')}</p>
		{:else}
			<ul class="candidates">
				{#each shownCandidates as c (c.id)}
					<li>
						<button type="button" on:click={() => choose(c.id)}>
							<span>{c.name}</span>
							<span class="muted">{where(c.teamIndex)} · <span class="num">{c.rating}</span></span>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
{:else if comparing}
		<table class="compare">
			<thead>
				<tr>
					<th scope="col" class="a">
						{name}
						<span class="where">{where(teamIndex)}</span>
						{#if table.a.incomplete}<span class="incomplete">{t('builder.incomplete')}</span>{/if}
					</th>
					<td></td>
					<th scope="col" class="b">
						{otherName}
						<span class="where">{where(otherTeamIndex)}</span>
						{#if table.b.incomplete}<span class="incomplete">{t('builder.incomplete')}</span>{/if}
					</th>
				</tr>
			</thead>
			<tbody>
				<tr>
					<td class="a num">{table.a.rating}</td>
					<th scope="row">{t('builder.compare.rating')}</th>
					<td class="b num">{table.b.rating}</td>
				</tr>
				<tr>
					<td class="a num">{table.a.globalLevel ?? '—'}</td>
					<th scope="row">{t('builder.preview.globalLevel')}</th>
					<td class="b num">{table.b.globalLevel ?? '—'}</td>
				</tr>
				<tr>
					<td class="a">{table.a.frequency ? t(`register.frequency.${table.a.frequency}`) : '—'}</td>
					<th scope="row">{t('builder.preview.frequency')}</th>
					<td class="b">{table.b.frequency ? t(`register.frequency.${table.b.frequency}`) : '—'}</td>
				</tr>
				{#each table.rows as row (row.identifier)}
					<tr>
						<td class="a" class:estimated={row.aEstimated}>
							<div class="cell">
								{#if row.lead === 'a'}<span class="lead">{t('builder.compare.lead', { n: row.delta })}</span>{/if}
								<span class="value num">{shown(row.a)}</span>
								<span class="track" aria-hidden="true"><span class="fill" style="width: {row.a * 10}%"></span></span>
							</div>
							{#if row.aEstimated}<span class="note">{t('builder.preview.estimated')}</span>{/if}
						</td>
						<th scope="row">{row.name}</th>
						<td class="b" class:estimated={row.bEstimated}>
							<div class="cell">
								<span class="track" aria-hidden="true"><span class="fill" style="width: {row.b * 10}%"></span></span>
								<span class="value num">{shown(row.b)}</span>
								{#if row.lead === 'b'}<span class="lead">{t('builder.compare.lead', { n: row.delta })}</span>{/if}
							</div>
							{#if row.bEstimated}<span class="note">{t('builder.preview.estimated')}</span>{/if}
						</td>
					</tr>
				{/each}
				<tr>
					<td class="a sports">
						{#each table.a.sports as sport}<span>{sportLine(sport)}</span>{:else}<span class="muted">{t('builder.preview.noSports')}</span>{/each}
					</td>
					<th scope="row">{t('builder.preview.sports')}</th>
					<td class="b sports">
						{#each table.b.sports as sport}<span>{sportLine(sport)}</span>{:else}<span class="muted">{t('builder.preview.noSports')}</span>{/each}
					</td>
				</tr>
			</tbody>
		</table>

		<div class="swap">
			<button
				type="button"
				class="primary"
				disabled={swapReason !== null}
				aria-describedby={swapReason ? 'swap-reason' : undefined}
				on:click={() => dispatch('swap', { a: player.id, b: other.id })}
			>{t('builder.compare.swap')}</button>
			{#if swapReason}<p id="swap-reason" class="reason">{t(`builder.compare.${swapReason}`)}</p>{/if}
		</div>
		<div class="effect" aria-live="polite">
			{#if swapView}
				<h3>{t('builder.compare.preview')}</h3>
				<ul>
					{#each swapView.teams as row (row.index)}
						{@const d = direction(row.before, row.after)}
						<li>
							{t('builder.compare.average', { team: t('builder.team', { n: row.index + 1 }), before: shownRating(row.before), after: shownRating(row.after) })}
							({d > 0 ? t('builder.compare.up') : d < 0 ? t('builder.compare.down') : t('builder.compare.same')})
						</li>
					{/each}
					{#if true}
						{@const u = swapView.unmet.after - swapView.unmet.before}
						<li class:good={u < 0} class:bad={u > 0}>
							{t('builder.compare.unmet', { before: swapView.unmet.before, after: swapView.unmet.after })}
							({u < 0 ? t('builder.compare.better') : u > 0 ? t('builder.compare.worse') : t('builder.compare.same')})
						</li>
					{/if}
				</ul>
			{/if}
		</div>
{:else}
		<p class="where">{teamIndex >= 0 ? t('builder.team', { n: teamIndex + 1 }) : t('builder.preview.tray')}</p>
		<dl class="summary">
			<div>
				<dt>{t('builder.preview.rating')}</dt>
				<dd class="num">{profile.rating}</dd>
			</div>
			{#if profile.globalLevel !== null}
				<div>
					<dt>{t('builder.preview.globalLevel')}</dt>
					<dd class="num">{profile.globalLevel}</dd>
				</div>
			{/if}
			<div>
				<dt>{t('builder.preview.frequency')}</dt>
				<dd>{profile.frequency ? t(`register.frequency.${profile.frequency}`) : '—'}</dd>
			</div>
		</dl>

		<h3>{t('builder.preview.skills')}</h3>
		<ul class="bars">
			{#each profile.bars as bar (bar.identifier)}
				<li class:estimated={bar.estimated}>
					<span class="skill">{bar.name}</span>
					<span class="track" aria-hidden="true"><span class="fill" style="width: {bar.value * 10}%"></span></span>
					<span class="value num">{shown(bar.value)}</span>
					{#if bar.estimated}<span class="note">{t('builder.preview.estimated')}</span>{/if}
				</li>
			{/each}
		</ul>
		{#if profile.incomplete}<p class="incomplete">{t('builder.incomplete')}</p>{/if}

		<h3>{t('builder.preview.sports')}</h3>
		{#if profile.sports.length === 0}
			<p class="none">{t('builder.preview.noSports')}</p>
		{:else}
			<ul class="sports">
				{#each profile.sports as s}
					<li>
						<span>{[s.sport, s.level && t(`register.level.${s.level}`), s.practice && t(`register.practice.${s.practice}`)].filter(Boolean).join(' · ')}</span>
						{#if s.notes}<span class="notes">{s.notes}</span>{/if}
					</li>
				{/each}
			</ul>
		{/if}
{/if}

		<div class="actions">
			{#if comparing}
				<button type="button" class="ghost" data-compare-action on:click={openPicker}>{t('builder.compare.change')}</button>
				<button type="button" class="ghost" on:click={() => dispatch('uncompare')}>{t('builder.compare.close')}</button>
			{:else if !picking}
				<button type="button" class="ghost" data-compare-action on:click={openPicker}>{t('builder.compare.open')}</button>
			{/if}
			<button type="button" on:click={close}>{t('builder.preview.close')}</button>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		background: var(--scrim);
		z-index: 30;
	}
	.sheet {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 31;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg) var(--radius-lg) 0 0;
		padding: 1rem 1rem calc(1rem + env(safe-area-inset-bottom));
		max-height: 90vh;
		max-height: 90dvh;
		overflow-y: auto;
		overscroll-behavior: contain;
	}
	h2 {
		margin: 0;
		text-align: center;
	}
	h3 {
		margin: 1rem 0 0.5rem;
		font-size: 1rem;
		font-family: var(--font-body);
		text-transform: none;
		letter-spacing: 0;
	}
	.where {
		margin: 0.2rem 0 1rem;
		text-align: center;
		color: var(--muted);
	}
	.summary {
		display: grid;
		gap: 0.5rem;
		margin: 0;
	}
	.summary div {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
		text-align: right;
		color: var(--ink);
	}
	.bars,
	.sports {
		display: grid;
		gap: 0.375rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	/* The name on its own line, whole (skill names run long), then the bar and its value. */
	.bars li {
		display: grid;
		grid-template-columns: 1fr 2rem;
		gap: 0.125rem 0.5rem;
		align-items: center;
	}
	.skill {
		grid-column: 1 / -1;
	}
	.track {
		display: block;
		height: 0.5rem;
		background: var(--bg);
		border: 1px solid var(--line);
		border-radius: 999px;
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		background: var(--accent);
	}
	.estimated .fill {
		opacity: 0.35;
	}
	.value {
		text-align: right;
	}
	.note {
		grid-column: 1 / -1;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.incomplete {
		margin: 0.5rem 0 0;
		font-size: 0.8125rem;
		color: var(--loss);
	}
	.notes {
		display: block;
		font-size: 0.8125rem;
		color: var(--muted);
		white-space: pre-line;
		overflow-wrap: anywhere;
	}
	.none {
		margin: 0;
		color: var(--muted);
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.5rem;
		margin-top: 1rem;
	}
	.actions button.ghost {
		background: transparent;
		color: var(--accent);
	}
	.search {
		width: 100%;
		box-sizing: border-box;
		padding: 0.5rem 0.625rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	.candidates {
		display: grid;
		gap: 0.25rem;
		margin: 0.5rem 0 0;
		padding: 0;
		list-style: none;
		max-height: 50vh;
		overflow-y: auto;
	}
	.candidates button {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		width: 100%;
		min-height: 44px;
		align-items: center;
		padding: 0.25rem 0.75rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}
	.muted {
		color: var(--muted);
		font-size: 0.875rem;
	}
	.compare {
		width: 100%;
		table-layout: fixed;
		border-collapse: collapse;
	}
	.compare th[scope='col'] {
		padding-bottom: 0.5rem;
		font-weight: 600;
		color: var(--ink);
		overflow-wrap: anywhere;
	}
	.compare th[scope='col'] .where {
		display: block;
		margin: 0;
		font-weight: 400;
		font-size: 0.8125rem;
	}
	.compare th[scope='col'] .incomplete {
		display: block;
		margin: 0;
	}
	.compare thead td {
		width: 28%;
	}
	.compare tbody th {
		width: 28%;
		padding: 0.25rem 0.25rem;
		font-weight: 400;
		font-size: 0.8125rem;
		color: var(--muted);
		text-align: center;
		overflow-wrap: anywhere;
	}
	.compare tbody td {
		padding: 0.25rem 0;
		font-size: 0.875rem;
		color: var(--ink);
		vertical-align: middle;
	}
	.compare td.a,
	.compare th.a {
		text-align: right;
		padding-right: 0.25rem;
	}
	.compare td.b,
	.compare th.b {
		text-align: left;
		padding-left: 0.25rem;
	}
	.compare .cell {
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}
	.compare .a .cell {
		flex-direction: row-reverse;
	}
	.compare .cell .track {
		flex: 1;
		display: flex;
		min-width: 1.5rem;
	}
	.compare .a .track {
		justify-content: flex-end;
	}
	.compare .lead {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--accent);
	}
	.compare .note {
		display: block;
		font-size: 0.75rem;
		color: var(--muted);
	}
	.compare .sports {
		display: grid;
		gap: 0.25rem;
		font-size: 0.8125rem;
	}
	.swap {
		display: grid;
		justify-items: center;
		gap: 0.375rem;
		margin-top: 1rem;
	}
	.swap button.primary {
		min-height: 44px;
		padding: 0 1.2rem;
		border-radius: var(--radius);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		cursor: pointer;
	}
	.swap button.primary:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.reason {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--muted);
		text-align: center;
	}
	.effect ul {
		margin: 0;
		padding: 0;
		list-style: none;
		display: grid;
		gap: 0.25rem;
		font-size: 0.875rem;
	}
	.effect li.good {
		color: var(--win);
	}
	.effect li.bad {
		color: var(--loss);
	}
	.actions button {
		min-height: 44px;
		padding: 0 1.2rem;
		border-radius: var(--radius);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		cursor: pointer;
	}
	.actions button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	@media (min-width: 1000px) {
		.sheet.wide {
			width: 560px;
		}
		.sheet {
			left: 50%;
			right: auto;
			bottom: auto;
			top: 50%;
			width: 420px;
			transform: translate(-50%, -50%);
			border-radius: var(--radius-lg);
		}
	}
</style>
