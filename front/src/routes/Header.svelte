<script>
	import { page } from '$app/stores';
	import logo from '$lib/img/logo.svg';
	import Menu from "./menu.svelte";

	let tabs = [
		{ name: 'Home', url: '/' },
		{ name: 'Teams', url: '/teams' },
		{ name: 'Disciplines', url: '/disciplines' },
		{ name: 'Photos', url: '/photos' },
		{ name: 'Login', url: '/login' }
	];
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
		margin-left: 3vw;
		height: 2.2em;
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

	nav a {
		display: flex;
		height: 100%;
		align-items: center;
		padding: 0 2em;
		color: var(--color-theme-1);
		font-weight: 700;
		font-size: 1rem;
		text-transform: uppercase;
		letter-spacing: .2em;
		text-decoration: none;
	}

	a:hover {
		color: var(--color-theme-1);
	}

	/* Media queries for larger screens */
	@media (min-width: 769px) {
		ul {
			display: flex;
		}
	}

	@media (max-width: 768px) {
		ul {
			display: none;
		}
	}
</style>
