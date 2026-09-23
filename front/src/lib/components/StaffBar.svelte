<script>
	import { enhance } from '$app/forms';
	import { useT } from '$lib/i18n';

	export let disciplineId;
	export let revealed = false;
	/** Worded count of what is still missing, or null when nothing is. */
	export let missing = null;
	/** A dictionary key for the line under the bar, or null. */
	export let error = null;

	const t = useT();
</script>

<div class="bar" class:revealed>
	<div class="text">
		<span class="status">{revealed ? t('orga.public') : t('orga.hidden')}</span>
		{#if missing}
			<span class="missing">{missing}</span>
		{/if}
	</div>
	<form method="POST" action="?/reveal" use:enhance>
		<input type="hidden" name="discipline" value={disciplineId} />
		<input type="hidden" name="reveal_score" value={revealed ? 'false' : 'true'} />
		<button>{revealed ? t('orga.hide') : t('orga.reveal')}</button>
	</form>
	{#if error}
		<p class="error" role="alert">{t(error)}</p>
	{/if}
</div>

<style>
	.bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.6rem 1rem;
		margin: 0 0 14px;
		padding: 0.7rem 0.9rem;
		border: 1px dashed var(--todo);
		border-radius: var(--radius);
	}

	.bar.revealed {
		border-color: var(--win);
	}

	.text {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.status {
		font-weight: 600;
	}

	.missing {
		font-size: 0.85rem;
		color: var(--muted);
	}

	form {
		margin: 0;
	}

	button {
		min-height: 44px;
		padding: 0 1.2rem;
		border-radius: var(--radius);
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		cursor: pointer;
	}

	button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.error {
		flex-basis: 100%;
		margin: 0;
		color: var(--loss);
		font-size: 0.85rem;
	}
</style>
