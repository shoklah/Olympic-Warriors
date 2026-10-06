<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';

	/** The undo and redo icon buttons of the builder's toolbars (spec 2026-10-06-builder-undo-redo). */
	export let canUndo = false;
	export let canRedo = false;

	const t = useT();
	const dispatch = createEventDispatcher();
</script>

<button type="button" disabled={!canUndo} aria-label={t('builder.undo')} title={t('builder.undo.hint')} on:click={() => dispatch('undo')}>
	<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 14 4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" /></svg>
</button>
<button type="button" disabled={!canRedo} aria-label={t('builder.redo')} title={t('builder.redo.hint')} on:click={() => dispatch('redo')}>
	<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 14 5-5-5-5" /><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13" /></svg>
</button>

<style>
	button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		padding: 0;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		cursor: pointer;
	}
	button:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
</style>
