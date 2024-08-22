<script>
    import { slide } from "svelte/transition";
    import {quintOut} from "svelte/easing";
    import { onMount } from "svelte";

    let checkbox;
    let menuOpen = false;
    let menu;
    let links;

    onMount(() => {
        const handleClickOutside = (event) => {
            if (menuOpen && !checkbox.contains(event.target) && !menu.contains(event.target) || links.contains(event.target)) {
                menuOpen = false;
            }
        };

        document.body.addEventListener('click', handleClickOutside);

        return () => {
            document.body.removeEventListener('click', handleClickOutside);
        };
    });
</script>

<label class="hamburger" bind:this={checkbox}>
    <input type="checkbox" id="menu-toggle" bind:checked={menuOpen} >
    <svg viewBox="0 0 32 32">
        <path class="line line-top-bottom" d="M27 10 13 10C10.8 10 9 8.2 9 6 9 3.5 10.8 2 13 2 15.2 2 17 3.8 17 6L17 26C17 28.2 18.8 30 21 30 23.2 30 25 28.2 25 26 25 23.8 23.2 22 21 22L7 22"></path>
        <path class="line" d="M7 16 27 16"></path>
    </svg>
</label>

{#if menuOpen}
    <div class="menu" bind:this={menu} transition:slide={{ delay: 50, duration: 300, easing: quintOut, axis: 'x' }}>
        <a href="/" bind:this={links}>Acceuil</a>
        <a href="/create" bind:this={links}>Créer</a>
        <a href="https://github.com/RodolpheANDRIEUX/B2Dev">A propos</a>
        <a href="https://github.com/RodolpheANDRIEUX">Contact</a>
    </div>
{/if}

<style>
    .menu a {
        font-size: 3em;
        color: var(--color-theme-1);
        text-decoration: none;
        padding: .4em 1em;
        transition: .2s ease-in-out;
    }

    .menu a:hover {
        transform: translate(.5em, 0);
    }

    .menu {
        position: fixed;
        top: 60px;
        left: 0;
        width: min(90vw, 600px);
        height: 100vh;
        background-color: var(--color-theme-2);
        display: flex;
        padding-top: 2rem;
        flex-direction: column;
        backdrop-filter: blur(10px);
        overflow: hidden;
    }

    .hamburger {
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
        transition: stroke-dasharray 600ms cubic-bezier(0.4, 0, 0.2, 1),
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