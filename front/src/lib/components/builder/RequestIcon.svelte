<script>
	/** The state a request line or chip is in: 'question' (to confirm), 'check' (confirmed) or 'minus' (nothing to confirm). */
	export let name;
</script>

<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
	<circle cx="12" cy="12" r="9" />
	{#if name === 'check'}
		<path d="M8 12.5l3 3 5-6" />
	{:else if name === 'minus'}
		<path d="M8 12h8" />
	{:else}
		<path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7" />
		<path d="M12 17h.01" />
	{/if}
</svg>

<style>
	svg {
		flex: none;
		width: 1em;
		height: 1em;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
