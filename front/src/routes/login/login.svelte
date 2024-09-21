<script>
    export let form;
    import { enhance } from '$app/forms';
    import { fly } from "svelte/transition";
    import {slide} from "svelte/transition";
    import {cubicOut, quintOut} from "svelte/easing";
</script>

<form class="form-login" method="POST" action="?/login" use:enhance
      in:fly={{ delay: 200, x: -200, duration: 300, easing: cubicOut }}
      out:fly={{ x: -200, duration: 200, easing: cubicOut }}>

    {#if form?.error }<p class="error" transition:slide={{ duration: 800, easing: quintOut }}>
        {form.error}
    </p>{/if}

    {#if form?.missing && form?.missing.username}<p class="error" transition:slide={{ duration: 800, easing: quintOut }}>
        The email field is required
    </p>{/if}
    <input name="username" placeholder="Username" value={form?.email ?? ''}
           style="border-bottom: {(form?.missing && form?.missing.email) ? '#ff0000' : 'var(--color-theme-1)'} 2px solid;" autofocus>

    {#if form?.missing && form?.missing.password}<p class="error" transition:slide={{ duration: 800, easing: quintOut }}>
        You forgot the password...
    </p>{/if}
    <input type="password" name="password" placeholder="Password"
           style="border-bottom: {(form?.missing && form?.missing.password) ? '#ff0000' : 'var(--color-theme-1)'} 2px solid;">

    <button>Log In</button>
</form>

<style>
    .error {
        color: red;
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
        background-color: var(--color-bg-0);
        color: var(--color-text);
        border: none;
        border-bottom: var(--color-theme-1) 2px solid;
        width: 100%;
        padding: .5rem 1rem;
        font-size: 1.5rem;
        font-weight: 600;
        transition: .5s;
    }

    button {
        background-color: var(--color-theme-1);
        color: var(--color-bg-0);
        margin-left: .5rem;
        padding: .9rem;
        border: none;
        border-radius: 5px;
        font-size: 1.2rem;
        font-weight: 600;
        cursor: pointer;
        transform: translate(0, -1px);
        transition: .2s;
    }

    button:hover {
        opacity: .6;
    }

    button:active {
        transform: translate(0, 3px);
    }
</style>