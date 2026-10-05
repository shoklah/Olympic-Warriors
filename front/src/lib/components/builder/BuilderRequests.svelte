<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { matchNames } from '$lib/builder/names.js';

	export let players;
	export let links;

	const t = useT();
	const dispatch = createEventDispatcher();
	const KINDS = [['team_with', 'with'], ['team_avoid', 'avoid']];

	$: byId = new Map(players.map((p) => [p.id, p]));
	// The matches depend on the roster only, so confirming a link never recomputes them.
	$: rows = players.flatMap((player) =>
		KINDS.flatMap(([field, kind]) =>
			player[field]?.trim() ? [{ player, kind, matches: matchNames(player[field], players, player.id) }] : []
		)
	);
	$: confirmed = new Set(links.map((l) => `${l.player}:${l.kind}:${l.target}`));
	$: isOn = (player, kind, target) => confirmed.has(`${player.id}:${kind}:${target}`);
	const toggle = (player, kind, target) => dispatch('toggle', { player: player.id, kind, target });

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
{:else}
	<ul class="rows">
		{#each rows as row (`${row.player.id}-${row.kind}`)}
			<li class="row">
				<p class="who"><strong>{fullName(row.player)}</strong> {t(`builder.requests.${row.kind}`)}</p>
				<ul>
					{#each row.matches as match}
						<li class="match">
							<span class="text">« {match.text} »</span>
							{#each match.candidates as candidate}
								<button
									type="button"
									class="chip"
									aria-pressed={isOn(row.player, row.kind, candidate.id)}
									aria-label={t('builder.requests.confirm', { name: fullName(byId.get(candidate.id)) })}
									on:click={() => toggle(row.player, row.kind, candidate.id)}
								>
									{fullName(byId.get(candidate.id))}
								</button>
							{/each}
							{#if match.candidates.length === 0}<span class="hint">{t('builder.requests.noMatch')}</span>{/if}
						</li>
					{/each}
					{#each extras(row) as link}
						<li class="match">
							<button type="button" class="chip" aria-pressed="true" aria-label={t('builder.requests.confirm', { name: fullName(byId.get(link.target)) })} on:click={() => toggle(row.player, row.kind, link.target)}>
								{fullName(byId.get(link.target))}
							</button>
						</li>
					{/each}
				</ul>
				<select aria-label="{t('builder.requests.other')} ({fullName(row.player)})" on:change={(e) => other(e, row.player, row.kind)}>
					<option value="">{t('builder.requests.other')}</option>
					{#each players.filter((p) => p.id !== row.player.id) as p}<option value={p.id}>{fullName(p)}</option>{/each}
				</select>
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
	.rows {
		display: grid;
		gap: 1rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.row {
		display: grid;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.who {
		margin: 0;
	}
	.row ul {
		display: grid;
		gap: 0.375rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.match {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}
	.match .hint {
		margin: 0;
	}
	.text {
		color: var(--muted);
	}
	.chip {
		padding: 0.375rem 0.875rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.chip[aria-pressed='true'] {
		background: var(--accent);
		color: var(--bg);
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
</style>
