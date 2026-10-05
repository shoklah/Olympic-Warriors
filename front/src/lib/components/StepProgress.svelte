<script>
	import { createEventDispatcher } from 'svelte';

	/** The steps, in order: `[{ n, label }]`. */
	export let steps;
	/** The step on screen (its `n`). */
	export let step;
	/** The nav's and the bar's accessible name. */
	export let label;
	/** « Step N of total »: a ready string, or a function of the step and the total. */
	export let ofText;
	/** Whether a step's button may be used. */
	export let canGo = () => true;
	/** Hides the whole block (the registration's no-JS render). */
	export let hidden = false;

	const dispatch = createEventDispatcher();

	$: total = steps.length;
	$: text = typeof ofText === 'function' ? ofText(step, total) : ofText;
</script>

<nav class="progress" {hidden} aria-label={label}>
	<p class="progress-text num">{text}</p>
	<div
		class="bar"
		role="progressbar"
		aria-label={label}
		aria-valuemin="1"
		aria-valuemax={total}
		aria-valuenow={step}
		aria-valuetext={text}
	>
		<div class="fill" style="width: {(step / total) * 100}%"></div>
	</div>
	<ol>
		{#each steps as s}
			<li>
				<button
					type="button"
					class="step-name"
					aria-current={s.n === step ? 'step' : undefined}
					disabled={!canGo(s.n)}
					on:click={() => dispatch('go', s.n)}
				>
					<span class="num" aria-hidden="true">{s.n}</span>
					{s.label}
				</button>
			</li>
		{/each}
	</ol>
</nav>

<style>
	.progress[hidden] {
		display: none;
	}
	.progress {
		margin: 0 0 1.25rem;
	}
	.progress-text {
		margin: 0 0 0.5rem;
		color: var(--muted);
	}
	.bar {
		height: 0.375rem;
		border-radius: 999px;
		background: var(--bg-sunken);
		border: 1px solid var(--line);
		overflow: hidden;
	}
	.fill {
		height: 100%;
		background: var(--accent);
	}
	.progress ol {
		display: flex;
		gap: 0.5rem;
		list-style: none;
		margin: 0.75rem 0 0;
		padding: 0;
	}
	.progress li {
		flex: 1;
		display: flex;
	}
	.step-name {
		width: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.125rem;
		text-align: center;
		padding: 0.5rem;
		background: transparent;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--muted);
		font: inherit;
		cursor: pointer;
	}
	@media (min-width: 600px) {
		.step-name {
			flex-direction: row;
			gap: 0.5rem;
		}
	}
	.step-name[aria-current='step'] {
		color: var(--ink);
		border-color: var(--accent);
	}
	.step-name:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
