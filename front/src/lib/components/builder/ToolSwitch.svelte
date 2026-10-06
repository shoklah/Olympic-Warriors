<script>
	import { createEventDispatcher } from 'svelte';

	/** A labelled on/off switch for the builder's toolbars: a real checkbox, restyled. */
	export let checked = false;

	const dispatch = createEventDispatcher();
</script>

<label>
	<input type="checkbox" {checked} on:change={(e) => dispatch('change', e.currentTarget.checked)} />
	<span class="knob" aria-hidden="true"></span>
	<slot />
</label>

<style>
	label {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		border-radius: var(--radius);
	}
	label:focus-within {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	input {
		position: absolute;
		opacity: 0;
		width: 1px;
		height: 1px;
	}
	.knob {
		position: relative;
		flex: none;
		width: 2rem;
		height: 1.125rem;
		border-radius: 999px;
		background: var(--line-strong);
		transition: background 0.15s;
	}
	.knob::after {
		content: '';
		position: absolute;
		top: 0.125rem;
		left: 0.125rem;
		width: 0.875rem;
		height: 0.875rem;
		border-radius: 50%;
		background: var(--bg);
		transition: transform 0.15s;
	}
	input:checked + .knob {
		background: var(--accent);
	}
	input:checked + .knob::after {
		transform: translateX(0.875rem);
	}
</style>
