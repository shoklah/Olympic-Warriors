<script>
	import { page } from '$app/stores';
	import logo from '$lib/img/logo.svg';
	import Menu from "./menu.svelte";
</script>

<header>
	<div class="logo">
		<a href="/">
			<img src={logo} alt="OW" />
		</a>
	</div>

	<nav>
		<ul>
			<li aria-current={$page.url.pathname === '/' ? 'page' : undefined}>
				<a href="/">Home</a>
			</li>
			<li aria-current={$page.url.pathname === '/login' ? 'page' : undefined}>
				<a href="/login">Login</a>
			</li>
		</ul>
		<Menu class="menu"/>
	</nav>
</header>

<style>
	/* Mobile-first approach */
	.menu {
		display: none;
	}

	/* Flexbox layout for header */
	header {
		display: flex;
		padding: 2em clamp(0em, 2vw, 5em);
		justify-content: space-between;
		view-transition-name: header;
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
		list-style: none;
		background: var(--background);
		background-size: contain;
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
		font-size: .8rem;
		text-transform: uppercase;
		letter-spacing: .2em;
		text-decoration: none;
		transition: color 0.2s linear;
	}

	a:hover {
		color: var(--color-theme-1);
	}

	/* Media queries for larger screens */
	@media (min-width: 769px) {
		.menu {
			display: none;
		}

		ul {
			display: flex;
		}
	}

	@media (max-width: 768px) {
		.menu {
			display: block;
		}

		ul {
			display: none;
		}
	}
</style>
