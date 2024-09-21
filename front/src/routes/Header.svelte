<script>
	import { page } from '$app/stores';
	import logo from '$lib/img/logo.svg';
	import Menu from "./menu.svelte";

	$: tabs = $page.data.sections;
</script>

<header>
	<div class="logo">
		<a href="/">
			<img src="{logo}" alt="OW" />
		</a>
	</div>

	<nav>
		<ul>
			{#each tabs as tab}
				<li aria-current={$page.url.pathname === tab.url ? 'page' : undefined}>
					<a href="{tab.url}">{tab.name}</a>
				</li>
			{/each}
		</ul>
	</nav>
	<Menu {tabs}/>
</header>

<style>
	li:last-of-type a {
		color: var(--color-bg-0);
		background-color: var(--color-theme-1);
		border-radius: 2em;
		margin: 0 0 0 2em;
		text-decoration: none;
	}

	nav a {
		display: flex;
		height: 90%;
		align-items: center;
		padding: 0 2em;
		color: var(--color-theme-1);
		font-weight: 700;
		font-size: 1rem;
		text-transform: uppercase;
		letter-spacing: .2em;
		text-decoration: none;
	}

	header {
		display: flex;
		z-index: 10;
		padding: 2em clamp(0em, 2vw, 5em);
		justify-content: space-between;
	}

	.logo a {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
	}

	.logo img {
		margin-left: 2vw;
		height: 3em;
		object-fit: contain;
	}

	nav {
		display: flex;
		justify-content: center;
		view-transition-name: navbar;
	}

	ul {
		display: flex;
		justify-content: center;
		align-items: center;
		padding: 0;
		margin: 0;
		height: 3em;
	}

	li {
		position: relative;
		height: 100%;
	}

	li[aria-current='page']::before {
		content: '';
		width: 30px;
		height: 3px;
		position: absolute;
		top: 0;
		left: calc(50% - 15px);
		background-color: var(--color-theme-1);
		view-transition-name: indicator;
	}

	a:hover {
		color: var(--color-theme-1);
	}

	/* Media queries for larger screens */
	@media (min-width: 1000px) {
		ul {
			display: flex;
		}
	}

	@media (max-width: 1000px) {
		ul {
			display: none;
		}
	}
</style>
