<script>
	import { createEventDispatcher, tick } from 'svelte';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { clearLinks, lineState, reasonKey, requestRows, summarise } from '$lib/builder/requests.js';
	import RequestIcon from './RequestIcon.svelte';
	import HistoryButtons from './HistoryButtons.svelte';
	import ToolSwitch from './ToolSwitch.svelte';

	export let players;
	export let links;
	/** The lines set aside by the organisers: `{ player, kind, text }`. */
	export let ignored = [];
	export let canUndo = false;
	export let canRedo = false;

	const t = useT();
	const dispatch = createEventDispatcher();
	const STATE_ICON = { confirmed: 'check', clear: 'question', choose: 'question', check: 'question', none: 'minus', ignored: 'minus' };

	$: byId = new Map(players.map((p) => [p.id, p]));
	// The matches depend on the roster only, so confirming a link never recomputes them.
	$: rows = requestRows(players);
	// One card per player, whoever wrote something: both kinds always show, and a kind with no written request is an empty row,
	// so an organiser can still add a link by hand.
	const KINDS = ['with', 'avoid'];
	$: cards = players.map((player) => ({
		player,
		rows: KINDS.map((kind) => rows.find((r) => r.player.id === player.id && r.kind === kind) ?? { player, kind, matches: [] })
	}));
	$: confirmed = new Set(links.map((l) => `${l.player}:${l.kind}:${l.target}`));
	$: isOn = (player, kind, target) => confirmed.has(`${player.id}:${kind}:${target}`);
	$: stateOf = (row, match) => lineState(match, links, row.player, row.kind, ignored);
	$: summary = summarise(rows, links, ignored);
	// « À examiner seulement »: the lines already confirmed or ignored leave the cards (the ones with no match stay: they need a hand).
	// A line still to review when the filter turned on, or at any point since, stays until the filter is switched off and on
	// again: confirming it must not pull the button under the keyboard focus out of the page.
	let reviewOnly = false;
	let kept = new Set();
	// What is no longer to be decided on: confirmed, or set aside.
	const settled = (state) => state === 'confirmed' || state === 'ignored';
	const lineKey = (row, match) => `${row.player.id}:${row.kind}:${match.text}`;
	function setReviewOnly(on) {
		kept = new Set();
		reviewOnly = on;
	}
	$: if (reviewOnly) {
		let grew = false;
		for (const row of rows) {
			for (const match of row.matches) {
				if (!settled(stateOf(row, match)) && !kept.has(lineKey(row, match))) {
					kept.add(lineKey(row, match));
					grew = true;
				}
			}
		}
		if (grew) kept = kept;
	}
	$: shown = reviewOnly
		? cards
				.map((card) => ({
					player: card.player,
					rows: card.rows
						.map((row) => ({ ...row, matches: row.matches.filter((m) => !settled(stateOf(row, m)) || kept.has(lineKey(row, m))) }))
						.filter((row) => row.matches.length > 0)
				}))
				.filter((card) => card.rows.length > 0)
		: cards;
	// `drop`: the candidates of the line, whose confirmed links go with it when it is set aside.
	const setAside = (row, match, on) =>
		dispatch('ignore', { player: row.player.id, kind: row.kind, text: match.text, on, drop: match.candidates.map((c) => c.id) });
	const toggle = (player, kind, target) => dispatch('toggle', { player: player.id, kind, target });
	let toolbarEl;
	// The button that did it is gone once nothing is left to confirm: focus moves to the next control of the toolbar.
	async function confirmClear() {
		dispatch('confirmClear', clearLinks(rows, links, ignored));
		await tick();
		toolbarEl?.querySelector('button:not(:disabled)')?.focus();
	}
	const why = (match) => t(reasonKey(match), { n: match.candidates.length });

	/** Confirmed links of this player and kind that no name of their text suggested (added through « Autre joueur »). */
	$: extras = (row) => {
		const suggested = new Set(row.matches.flatMap((m) => m.candidates.map((c) => c.id)));
		return links.filter((l) => l.player === row.player.id && l.kind === row.kind && !suggested.has(l.target));
	};
	function other(event, player, kind) {
		const target = Number(event.currentTarget.value);
		event.currentTarget.value = '';
		if (target && !isOn(player, kind, target)) toggle(player, kind, target);
	}
</script>

<p class="hint">{t('builder.requests.intro')}</p>
{#if rows.length === 0}
	<p>{t('builder.requests.none')}</p>
{/if}
{#if cards.length > 0}
	<div class="toolbar" bind:this={toolbarEl}>
		<div class="actions">
			<HistoryButtons {canUndo} {canRedo} on:undo on:redo />
			{#if summary.clear > 0}
				<button type="button" class="submit" on:click={confirmClear}>{t('builder.requests.confirmClear', { n: summary.clear })}</button>
			{/if}
		</div>
		<span class="sep" aria-hidden="true"></span>
		<ToolSwitch checked={reviewOnly} on:change={(e) => setReviewOnly(e.detail)}>{t('builder.requests.reviewOnly')}</ToolSwitch>
	</div>
	<div class="tally" aria-live="polite">
		<span class="tally-total">{t('builder.requests.count.total', { n: summary.total })}</span>
		<span class="tag good">
			<RequestIcon name="check" />{t('builder.requests.count.confirmed', { n: summary.confirmed })}
		</span>
		<span class="tag warn">
			<RequestIcon name="question" />{t('builder.requests.count.review', { n: summary.review })}
		</span>
		{#if summary.ignored > 0}
			<span class="tag none">
				<RequestIcon name="minus" />{t('builder.requests.count.ignored', { n: summary.ignored })}
			</span>
		{/if}
		{#if summary.none > 0}
			<span class="tag none">
				<RequestIcon name="minus" />{t('builder.requests.count.none', { n: summary.none })}
			</span>
		{/if}
	</div>
	{#if shown.length === 0}
		<p class="hint">{t('builder.requests.allDone')}</p>
	{/if}
	<ul class="grid">
		{#each shown as card (card.player.id)}
			<li class="card">
				<h3 class="who">{fullName(card.player)}</h3>
				{#each card.rows as row (row.kind)}
					<section class="kind {row.kind}" aria-label="{fullName(card.player)}: {t(`builder.requests.${row.kind}`)}">
						<p class="label {row.kind}">{t(`builder.requests.${row.kind}`)}</p>
						{#if row.matches.length === 0 && extras(row).length === 0}
							<p class="empty">{t('builder.requests.empty')}</p>
						{/if}
						<ul class="matches">
							{#each row.matches as match}
								{@const state = stateOf(row, match)}
								<li class="match" class:ignored={state === 'ignored'}>
									<span class="line">
										<span class="text">« {match.text} »</span>
										<span class="status {state}"><RequestIcon name={STATE_ICON[state]} />{t(`builder.requests.state.${state}`)}</span>
									</span>
									{#if match.candidates.length > 0 && state !== 'ignored'}
										<span class="chips">
											{#each match.candidates as candidate}
												<button
													type="button"
													class="chip"
													class:clear={state === 'clear'}
													aria-pressed={isOn(row.player, row.kind, candidate.id)}
													aria-label={t('builder.requests.confirm', { name: fullName(byId.get(candidate.id)) })}
													on:click={() => toggle(row.player, row.kind, candidate.id)}
												>
													<RequestIcon name={isOn(row.player, row.kind, candidate.id) ? 'check' : 'question'} />
													{fullName(byId.get(candidate.id))}
												</button>
											{/each}
										</span>
									{/if}
									<span class="why">{state === 'ignored' ? t('builder.requests.ignoredWhy') : why(match)}</span>
									<button
										type="button"
										class="ignore"
										aria-label={t(state === 'ignored' ? 'builder.requests.unignoreLine' : 'builder.requests.ignoreLine', { text: match.text })}
										on:click={() => setAside(row, match, state !== 'ignored')}
									>{t(state === 'ignored' ? 'builder.requests.unignore' : 'builder.requests.ignore')}</button>
								</li>
							{/each}
							{#if !reviewOnly && extras(row).length > 0}
								<li class="match added">
									<span class="text">{t('builder.requests.added')}</span>
									<span class="chips">
										{#each extras(row) as link}
											<button type="button" class="chip" aria-pressed="true" aria-label={t('builder.requests.confirm', { name: fullName(byId.get(link.target)) })} on:click={() => toggle(row.player, row.kind, link.target)}>
												<RequestIcon name="check" />
												{fullName(byId.get(link.target))}
											</button>
										{/each}
									</span>
								</li>
							{/if}
						</ul>
						<select aria-label="{t('builder.requests.other')} ({fullName(row.player)}) · {t(`builder.requests.${row.kind}`)}" on:change={(e) => other(e, row.player, row.kind)}>
							<option value="">{t('builder.requests.other')}</option>
							{#each players.filter((p) => p.id !== row.player.id) as p}<option value={p.id}>{fullName(p)}</option>{/each}
						</select>
					</section>
				{/each}
			</li>
		{/each}
	</ul>
{/if}

<style>
	.hint {
		color: var(--muted);
		font-size: 0.875rem;
		margin: 0 0 1rem;
	}
	.toolbar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1.25rem;
		margin-bottom: 0.5rem;
		padding: 0.75rem 1rem;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.sep {
		align-self: stretch;
		width: 1px;
		background: var(--line);
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.tally {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 0.75rem;
		margin: 0 0 1rem;
		padding: 0.5rem 1rem;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 0.875rem;
	}
	.tally-total {
		color: var(--muted);
	}
	.tag {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		font-weight: 600;
	}
	.tag.good {
		color: var(--win);
	}
	.tag.warn {
		color: var(--todo);
	}
	.tag.none {
		color: var(--muted);
	}
	.submit {
		padding: 0.5rem 1.125rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: var(--accent);
		color: var(--bg);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(26rem, 100%), 1fr));
		gap: 1rem;
		align-items: stretch;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.card {
		display: grid;
		align-content: start;
		gap: 1rem;
		padding: 0.75rem 1rem;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.who {
		margin: 0;
		font-size: 1.125rem;
	}
	/* Each kind is an inset block with a coloured rule, so « avec » and « à éviter » never read as one list. */
	.kind {
		display: grid;
		gap: 0.5rem;
		padding: 0.625rem 0.75rem;
		background: var(--bg-sunken);
		border-left: 3px solid var(--muted);
		border-radius: 0;
	}
	.kind.with {
		border-left-color: var(--win);
	}
	.kind.avoid {
		border-left-color: var(--loss);
	}
	.label {
		margin: 0;
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.label.with {
		color: var(--win);
	}
	.label.avoid {
		color: var(--loss);
	}
	.empty {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--faint);
	}
	.kind ul {
		display: grid;
		gap: 0.375rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.match {
		display: grid;
		gap: 0.375rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--line);
	}
	.match:last-child {
		border-bottom: 0;
		padding-bottom: 0;
	}
	.match.added .text {
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.line {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.25rem 0.75rem;
	}
	.text {
		color: var(--muted);
	}
	/* The state in words and an icon as well as a colour: none of the three is the only signal. */
	.status {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		font-weight: 600;
		white-space: nowrap;
	}
	.status.confirmed {
		color: var(--win);
	}
	.status.clear {
		color: var(--accent);
	}
	.status.choose,
	.status.check {
		color: var(--todo);
	}
	.status.none,
	.status.ignored {
		color: var(--muted);
	}
	.match.ignored .text,
	.match.ignored .why {
		opacity: 0.6;
	}
	.match.ignored .text {
		text-decoration: line-through;
	}
	.ignore {
		justify-self: start;
		align-self: start;
		padding: 0.125rem 0;
		background: none;
		border: 0;
		color: var(--muted);
		font: inherit;
		font-size: 0.8125rem;
		text-decoration: underline;
		cursor: pointer;
		border-radius: var(--radius);
	}
	.ignore:hover {
		color: var(--ink);
	}
	.ignore:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.why {
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}
	/* A suggestion is dashed: a question. A clear one is solid in the accent, and a confirmed one
	   solid and tinted in the win colour. */
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.375rem 0.875rem;
		border-radius: 999px;
		border: 1.5px dashed var(--line-strong);
		background: transparent;
		color: var(--ink);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.chip.clear {
		border-style: solid;
		border-color: var(--accent);
		color: var(--accent);
	}
	.chip[aria-pressed='true'] {
		border-style: solid;
		border-color: var(--win);
		background: color-mix(in srgb, var(--win) 16%, transparent);
		color: var(--win);
	}
	select {
		width: 100%;
		max-width: 20rem;
		padding: 0.5rem 0.625rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	/* Side by side, every card the same size (the tallest row sets the height); one column on a
	   phone keeps each card as tall as its content. */
	@media (min-width: 600px) {
		.grid {
			grid-auto-rows: 1fr;
		}
	}
	/* On a phone the clusters stack, split by horizontal hairlines, and the actions fall on one grid:
	   the history icons, then the main button filling the row, then the rest each on a line of their own. */
	@media (max-width: 599px) {
		.toolbar {
			flex-direction: column;
			align-items: stretch;
		}
		.sep {
			align-self: auto;
			width: auto;
			height: 1px;
		}
		.actions {
			display: grid;
			grid-template-columns: auto auto 1fr;
			gap: 0.5rem;
		}
		.actions > .submit {
			grid-column: 3;
		}
	}
</style>
