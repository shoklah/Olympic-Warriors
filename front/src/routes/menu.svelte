<script>
	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	export let tabs;
	export let years = [];
	export let year = null;

	let menuOpen = false;
</script>

<label class="hamburger">
	<input type="checkbox" id="menu-toggle" bind:checked={menuOpen} />
	<svg viewBox="0 0 32 32">
		<path
			class="line line-top-bottom"
			d="M27 10 13 10C10.8 10 9 8.2 9 6 9 3.5 10.8 2 13 2 15.2 2 17 3.8 17 6L17 26C17 28.2 18.8 30 21 30 23.2 30 25 28.2 25 26 25 23.8 23.2 22 21 22L7 22"
		/>
		<path class="line" d="M7 16 27 16" />
	</svg>
</label>

{#if menuOpen}
	<div class="menu" transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}>
		{#each tabs as tab}
			{#if tab.external}
				<a href={tab.url} target="_blank" rel="noopener" on:click={() => (menuOpen = false)}>{tab.name}</a>
			{:else}
				<a href={tab.url} on:click={() => (menuOpen = false)}>{tab.name}</a>
			{/if}
		{/each}
		<div class="years">
			{#each years as y}
				<a href={y.url} class:current={y.year === year} on:click={() => (menuOpen = false)}>{y.year}</a>
			{/each}
		</div>
	</div>
{/if}

<style>
	@media (min-width: 1000px) {
		.hamburger {
			display: none;
		}
	}

	@media (max-width: 1000px) {
		.hamburger {
			display: block;
		}
	}

	.menu a {
		color: var(--color-theme-1);
		font-weight: 700;
		font-size: 1.5rem;
		text-transform: uppercase;
		letter-spacing: 0.2em;
		text-decoration: none;
		padding: 0.8em 1em;
		transition: 0.2s ease-in-out;
	}

	.menu {
		position: fixed;
		top: 0;
		left: 0;
		width: 100vw;
		height: 100vh;
		display: flex;
		padding-top: 6rem;
		flex-direction: column;
		-webkit-backdrop-filter: blur(8px);
		backdrop-filter: blur(8px);
	}

	.years {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding: 1.5rem 1em;
	}

	.years a {
		font-size: 1rem;
		padding: 0.4em 1em;
		border: 2px solid var(--color-theme-1);
		border-radius: 2em;
	}

	.years a.current {
		color: var(--color-bg-0);
		background-color: var(--color-theme-1);
	}

	.menu::after {
		content: '';
		position: fixed;
		top: 0;
		left: 0;
		width: 100vw;
		height: 100vh;
		background-color: var(--color-bg-0);
		opacity: 0.4;
		z-index: -11;
	}

	.hamburger {
		z-index: 11;
		cursor: pointer;
		margin-left: 1.2rem;
	}

	.hamburger input {
		display: none;
	}

	.hamburger svg {
		height: 3.2em;
		transition: transform 600ms cubic-bezier(0.4, 0, 0.2, 1);
	}

	.line {
		fill: none;
		stroke: var(--color-theme-1);
		stroke-linecap: round;
		stroke-linejoin: round;
		stroke-width: 3;
		transition:
			stroke-dasharray 600ms cubic-bezier(0.4, 0, 0.2, 1),
			stroke-dashoffset 600ms cubic-bezier(0.4, 0, 0.2, 1);
	}

	.line-top-bottom {
		stroke-dasharray: 12 63;
	}

	.hamburger input:checked + svg {
		transform: rotate(-45deg);
	}

	.hamburger input:checked + svg .line-top-bottom {
		stroke-dasharray: 20 300;
		stroke-dashoffset: -32.42;
	}
</style>
