<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';

	export let teamCount;
	export let placedCount;
	export let unplacedCount;
	export let registrationOpen;
	export let unmet = [];
	export let nameOf;
	export let busy = false;
	export let error = '';
	export let done = null;
	export let saveBlocked = false;

	const t = useT();
	const dispatch = createEventDispatcher();
	let confirmedOpen = false;
	$: blocked = busy || saveBlocked || done !== null || teamCount === 0 || unplacedCount > 0 || (registrationOpen && !confirmedOpen);
</script>

{#if done}
	<p class="saved" role="status">{t('builder.apply.done')}</p>
	{#if done.unscheduled.length > 0}
		<p>{t('builder.apply.unscheduled')}</p>
		<ul>{#each done.unscheduled as discipline}<li>{discipline.name}</li>{/each}</ul>
	{/if}
{:else}
	<p class="num">{t('builder.apply.summary', { teams: teamCount, n: placedCount })}</p>
	{#if unplacedCount > 0}<p class="error">{t('builder.apply.unplaced', { n: unplacedCount })}</p>{/if}
	{#if unmet.length > 0}
		<ul>
			{#each unmet as u}
				<li>{t(`builder.unmet.${u.kind}`, { player: nameOf(u.player), target: nameOf(u.target) })}{u.mutual ? t('builder.unmet.mutual') : ''}</li>
			{/each}
		</ul>
	{/if}
	<p class="notice">{t('builder.apply.public')}</p>
	{#if registrationOpen}
		<p class="notice">{t('builder.apply.open')}</p>
		<label class="check"><input type="checkbox" bind:checked={confirmedOpen} /> {t('builder.apply.confirmOpen')}</label>
	{/if}
	{#if error}<p class="error" role="alert">{t(error)}</p>{/if}
	<button type="button" class="submit" disabled={blocked} on:click={() => dispatch('apply')}>{t('builder.apply.button')}</button>
{/if}

<style>
	.check {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		margin: 0.75rem 0;
	}
	.notice {
		margin: 0 0 1rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		background: var(--bg-raised);
	}
	.error,
	.saved {
		margin: 0 0 1rem;
		padding: 0.5rem 0.75rem;
		border-radius: var(--radius);
	}
	.error {
		color: var(--loss);
		border: 1px solid var(--loss);
	}
	.saved {
		color: var(--win);
		border: 1px solid var(--win);
	}
	.submit {
		padding: 0.625rem 1.25rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: var(--accent);
		color: var(--bg);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.submit:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
