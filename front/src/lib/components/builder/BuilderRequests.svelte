<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { clearLinks, lineState, reasonKey, requestRows, summarise } from '$lib/builder/requests.js';
	import RequestIcon from './RequestIcon.svelte';
	import HistoryButtons from './HistoryButtons.svelte';
	import ToolSwitch from './ToolSwitch.svelte';

	export let players;
	export let links;
	export let canUndo = false;
	export let canRedo = false;

	const t = useT();
	const dispatch = createEventDispatcher();
	const STATE_ICON = { confirmed: 'check', clear: 'question', choose: 'question', check: 'question', none: 'minus' };

	$: byId = new Map(players.map((p) => [p.id, p]));
	// The matches depend on the roster only, so confirming a link never recomputes them.
	$: rows = requestRows(players);
	// One card per player, holding the « avec » and the « à éviter » requests they wrote.
	$: cards = players
		.map((player) => ({ player, rows: rows.filter((row) => row.player.id === player.id) }))
		.filter((card) => card.rows.length > 0);
	$: confirmed = new Set(links.map((l) => `${l.player}:${l.kind}:${l.target}`));
	$: isOn = (player, kind, target) => confirmed.has(`${player.id}:${kind}:${target}`);
	$: stateOf = (row, match) => lineState(match, links, row.player, row.kind);
	$: summary = summarise(rows, links);
	// « À examiner seulement »: the lines already confirmed leave the cards (the ones with no match stay: they need a hand).
	let reviewOnly = false;
	$: shown = reviewOnly
		? cards
				.map((card) => ({
					player: card.player,
					rows: card.rows
						.map((row) => ({ ...row, matches: row.matches.filter((m) => stateOf(row, m) !== 'confirmed') }))
						.filter((row) => row.matches.length > 0)
				}))
				.filter((card) => card.rows.length > 0)
		: cards;
	const toggle = (player, kind, target) => dispatch('toggle', { player: player.id, kind, target });
	const confirmClear = () => dispatch('confirmClear', clearLinks(rows, links));
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
{#if cards.length === 0}
	<p>{t('builder.requests.none')}</p>
{:else}
	<div class="toolbar">
		<div class="actions">
			<HistoryButtons {canUndo} {canRedo} on:undo on:redo />
			{#if summary.clear > 0}
				<button type="button" class="submit" on:click={confirmClear}>{t('builder.requests.confirmClear', { n: summary.clear })}</button>
			{/if}
		</div>
		<span class="sep" aria-hidden="true"></span>
		<ToolSwitch checked={reviewOnly} on:change={(e) => (reviewOnly = e.detail)}>{t('builder.requests.reviewOnly')}</ToolSwitch>
	</div>
	<div class="tally" aria-live="polite">
		<span class="tally-total">{t('builder.requests.count.total', { n: summary.total })}</span>
		<span class="tag good">
			<RequestIcon name="check" />{t('builder.requests.count.confirmed', { n: summary.confirmed })}
		</span>
		<span class="tag warn">
			<RequestIcon name="question" />{t('builder.requests.count.review', { n: summary.review })}
		</span>
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
					<section class="kind" aria-label="{fullName(card.player)}: {t(`builder.requests.${row.kind}`)}">
						<p class="label">{t(`builder.requests.${row.kind}`)}</p>
						<ul class="matches">
							{#each row.matches as match}
								{@const state = stateOf(row, match)}
								<li class="match">
									<span class="line">
										<span class="text">« {match.text} »</span>
										<span class="status {state}"><RequestIcon name={STATE_ICON[state]} />{t(`builder.requests.state.${state}`)}</span>
									</span>
									{#if match.candidates.length > 0}
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
									<span class="why">{why(match)}</span>
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
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.who {
		margin: 0;
		font-size: 1.125rem;
	}
	.kind {
		display: grid;
		gap: 0.5rem;
	}
	.label {
		margin: 0;
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--muted);
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
	.status.none {
		color: var(--muted);
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
</style>
