<script>
    export let form;
    import { fly } from "svelte/transition";
    import {slide} from "svelte/transition";
    import {cubicOut, quintOut} from "svelte/easing";
    import { useT } from '$lib/i18n';

    const t = useT();
</script>

<!-- A plain POST: the redirect reloads the page so the organiser context is set from the new cookie. -->
<form method="POST" action="?/login"
      in:fly={{ delay: 200, x: -200, duration: 300, easing: cubicOut }}>

    <!-- The action's message is English by construction (API and server code); the visitor gets the dictionary line. -->
    {#if form?.error }<p class="error" transition:slide={{ duration: 800, easing: quintOut }}>
        {t(form.throttled ? 'login.throttled' : 'login.failed')}
    </p>{/if}

    {#if form?.missing && form?.missing.username}<p class="error" id="username-error" transition:slide={{ duration: 800, easing: quintOut }}>
        {t('login.missing')}
    </p>{/if}
    <input name="username" placeholder={t('login.username')} value={form?.username ?? ''}
           class:missing={form?.missing?.username}
           aria-invalid={form?.missing?.username ? 'true' : undefined}
           aria-describedby={form?.missing?.username ? 'username-error' : undefined} autofocus>

    {#if form?.missing && form?.missing.password}<p class="error" id="password-error" transition:slide={{ duration: 800, easing: quintOut }}>
        {t('login.missing')}
    </p>{/if}
    <input type="password" name="password" placeholder={t('login.password')}
           class:missing={form?.missing?.password}
           aria-invalid={form?.missing?.password ? 'true' : undefined}
           aria-describedby={form?.missing?.password ? 'password-error' : undefined}>

    <button>{t('login.submit')}</button>
</form>

<style>
    .error {
        color: var(--loss);
        font-size: 1rem;
        font-weight: 600;
        margin: 0;
    }

    form {
        width: min(30rem, 80vw);
        display: flex;
        flex-direction: column;
        align-items: center;
        margin: 5rem auto;
        gap: 2rem;
        transition: .5s;
    }

    input {
        background: transparent;
        color: var(--text);
        border: 0;
        border-bottom: 2px solid var(--line);
        width: 100%;
        padding: .5rem 1rem;
        font-family: inherit;
        font-size: 1.25rem;
        font-weight: 600;
        transition: .5s;
    }

    input:focus-visible {
        outline: none;
        border-bottom-color: var(--accent);
    }

    input.missing,
    input.missing:focus-visible {
        border-bottom-color: var(--loss);
    }

    button {
        background: var(--accent);
        color: var(--bg);
        font-family: var(--font-display);
        letter-spacing: .15em;
        padding: .7rem 3rem;
        border: none;
        border-radius: var(--radius);
        font-size: 1.2rem;
        cursor: pointer;
        transition: .3s;
    }

    button:hover,
    button:focus-visible {
        opacity: .8;
    }

    button:focus-visible {
        outline: 2px solid var(--ink);
        outline-offset: 2px;
    }
</style>