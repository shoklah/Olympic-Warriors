<script>
	import { createEventDispatcher } from 'svelte';
	import { useLocale, useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import PlayerCard from './PlayerCard.svelte';

	export let players;
	export let teams;
	export let unplaced;
	export let result;
	export let skills;
	export let perTeam;
	export let locked;
	export let incomplete;
	export let notesFor;
	export let tooFew = false;
	export let showRequests = true;

	const t = useT();
	const locale = useLocale();
	const dispatch = createEventDispatcher();
	$: byId = new Map(players.map((p) => [p.id, p]));
	$: proposed = teams.length > 0;
	$: count = proposed ? teams.length : Math.ceil(players.length / perTeam);
	$: unmet = result?.unmet ?? [];
	const skillName = (s) => (locale === 'en' ? s.name_en : s.name_fr);

	// The column a card is being dragged over: 'tray' or the team's index.
	let over = null;
	function dragOver(event, key) {
		event.preventDefault();
		over = key;
	}
	function dragLeave(event) {
		if (!event.currentTarget.contains(event.relatedTarget)) over = null;
	}
	function drop(event, to) {
		event.preventDefault();
		over = null;
		const id = Number(event.dataTransfer?.getData('text/plain'));
		if (byId.has(id)) dispatch('move', { id, to });
	}
	function setPerTeam(event) {
		const value = Number(event.currentTarget.value);
		if (Number.isInteger(value) && value >= 2 && value <= 20) dispatch('perTeam', value);
		else event.currentTarget.value = perTeam; // the field shows what the page holds
	}
	const nameOf = (id) => (byId.has(id) ? fullName(byId.get(id)) : '');
</script>

<div class="controls">
	<div class="field">
		<label for="per-team">{t('builder.perTeam')}</label>
		<input
			id="per-team"
			type="number"
			min="2"
			max="20"
			step="1"
			value={perTeam}
			disabled={proposed}
			aria-describedby={proposed ? 'per-team-hint' : undefined}
			on:change={setPerTeam}
		/>
		{#if proposed}<p class="hint" id="per-team-hint">{t('builder.perTeamLocked')}</p>{/if}
	</div>
	<p class="count num">{t('builder.counts', { n: count })}</p>
	<label class="check">
		<input type="checkbox" checked={showRequests} on:change={(e) => dispatch('showRequests', e.currentTarget.checked)} />
		{t('builder.showRequests')}
	</label>
	<div class="buttons">
		{#if !proposed}
			<button type="button" class="submit" disabled={players.length === 0} on:click={() => dispatch('propose')}>{t('builder.propose')}</button>
		{:else}
			<button type="button" class="submit" on:click={() => dispatch('reroll')}>{t('builder.reroll')}</button>
			{#if unplaced.length > 0}
				<button type="button" class="pill" on:click={() => dispatch('placeNew')}>{t('builder.placeNew')}</button>
			{/if}
			<button type="button" class="pill" on:click={() => dispatch('reset')}>{t('builder.reset')}</button>
		{/if}
	</div>
</div>
{#if tooFew}<p class="error" role="alert">{t('builder.tooFew')}</p>{/if}

{#if proposed}
	<section class="unmet" aria-labelledby="unmet-title">
		<h3 id="unmet-title">{t('builder.unmet')}</h3>
		{#if unmet.length === 0}
			<p class="hint">{t('builder.unmetNone')}</p>
		{:else}
			<ul>
				{#each unmet as u}
					<li>
						{t(`builder.unmet.${u.kind}`, { player: nameOf(u.player), target: nameOf(u.target) })}{u.mutual ? t('builder.unmet.mutual') : ''}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<div class="board">
	{#if unplaced.length > 0}
		<section
			class="column tray"
			class:over={over === 'tray'}
			aria-label={t('builder.tray')}
			on:dragover={(e) => dragOver(e, 'tray')}
			on:dragleave={dragLeave}
			on:drop={(e) => drop(e, null)}
		>
			<h3>{t('builder.tray')}</h3>
			<ul>
				{#each unplaced as id (id)}
					<PlayerCard player={byId.get(id)} teamCount={teams.length} incomplete={incomplete.has(id)} notes={showRequests ? notesFor(byId.get(id)) : []} on:move on:preview />
				{/each}
			</ul>
		</section>
	{/if}
	{#each teams as team, i}
		<section
			class="column"
			class:over={over === i}
			aria-label={t('builder.team', { n: i + 1 })}
			on:dragover={(e) => dragOver(e, i)}
			on:dragleave={dragLeave}
			on:drop={(e) => drop(e, i)}
		>
			<h3>{t('builder.team', { n: i + 1 })}</h3>
			<p class="stats">
				<span>{t('builder.size', { n: team.players.length })}</span>
				{#if result?.teams[i]}<span class="num">{t('builder.average', { rating: result.teams[i].rating.toFixed(1) })}</span>{/if}
			</p>
			{#if result?.teams[i]}
				<ul class="bars" aria-hidden="true">
					{#each skills as s}
						<li title="{skillName(s)} {result.teams[i].skills[s.identifier].toFixed(1)}">
							<span class="tag">{s.identifier}</span>
							<span class="track"><span class="fill" style="width: {result.teams[i].skills[s.identifier] * 10}%"></span></span>
						</li>
					{/each}
				</ul>
			{/if}
			<ul>
				{#each team.players as id (id)}
					<PlayerCard
						player={byId.get(id)}
						teamCount={teams.length}
						index={i}
						locked={locked.includes(id)}
						incomplete={incomplete.has(id)}
						notes={showRequests ? notesFor(byId.get(id)) : []}
						on:move
						on:lock
						on:preview
					/>
				{/each}
			</ul>
		</section>
	{/each}
</div>

<style>
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1.5rem;
		align-items: end;
		margin-bottom: 1rem;
	}
	.field {
		display: grid;
		gap: 0.25rem;
	}
	.field label {
		font-weight: 600;
	}
	input[type='number'] {
		width: 6rem;
		padding: 0.5rem 0.625rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	input:disabled {
		opacity: 0.5;
	}
	.count {
		margin: 0;
		color: var(--muted);
	}
	.check {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.submit,
	.pill {
		padding: 0.625rem 1.25rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.submit {
		background: var(--accent);
		color: var(--bg);
	}
	.submit:disabled,
	.pill:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.hint {
		color: var(--muted);
		font-size: 0.875rem;
		margin: 0;
	}
	.error {
		margin: 0;
		padding: 0.5rem 0.75rem;
		border-radius: var(--radius);
		color: var(--loss);
		border: 1px solid var(--loss);
	}
	.unmet {
		margin: 1rem 0;
	}
	.unmet h3 {
		font-size: 1rem;
		font-family: var(--font-body);
		text-transform: none;
		letter-spacing: 0;
		margin: 0 0 0.5rem;
	}
	.unmet ul {
		margin: 0;
		padding-left: 1.25rem;
	}
	.board {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
		gap: 1rem;
		align-items: stretch;
	}
	.column {
		display: grid;
		/* A stretched card keeps its rows where they are: the spare height ends up at the bottom,
		   so every card's title, stats and bars line up with its neighbours'. */
		align-content: start;
		gap: 0.5rem;
		padding: 0.75rem;
		background: var(--bg-sunken);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.column.over {
		border-color: var(--accent);
		background: var(--bg-raised);
	}
	.column h3 {
		margin: 0;
		font-size: 1.125rem;
	}
	.column ul {
		display: grid;
		gap: 0.5rem;
		margin: 0;
		padding: 0;
	}
	.tray {
		border-style: dashed;
		border-color: var(--accent);
	}
	.stats {
		display: flex;
		justify-content: space-between;
		margin: 0;
		color: var(--muted);
		font-size: 0.875rem;
	}
	.column ul.bars {
		display: grid;
		gap: 0.25rem;
	}
	.bars li {
		display: grid;
		grid-template-columns: 2.75rem 1fr;
		gap: 0.5rem;
		align-items: center;
		list-style: none;
	}
	.tag {
		font-size: 0.6875rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.track {
		display: block;
		height: 0.375rem;
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
	/* Side by side, every card the same size (the tallest row sets the height); one column on a
	   phone keeps each card as tall as its content. */
	@media (min-width: 600px) {
		.board {
			grid-auto-rows: 1fr;
		}
	}
</style>
