<script>
    import Login from './login.svelte';
    import Register from './register.svelte';
    export let form;

    let login = true;
</script>

<div class="login">
    <label id="toggle" for="toggle-login">
        <input type="checkbox" id="toggle-login" bind:checked={login}>
        <span id="toggle-moving" style="transform: translate({login ? '0' : '120px'}, 0);">{login ? 'Log in' : 'Sign in'}</span>
        <span>Log in</span>
        <span>Sign in</span>
    </label>

    {#if login}
        <Login {form}/>
    {:else}
        <Register {form}/>
    {/if}
</div>


<style>
    .login {
        position: relative;
    }

    #toggle {
        position: absolute;
        top: 0;
        right: 50%;
        transform: translate(50%, 0);
        cursor: pointer;
        transition: .3s;
        width: 250px;
        height: 42px;
        background: var(--color-bg-3);
        border-radius: 21px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    #toggle span {
        font-size: 1rem;
        font-weight: 600;
        margin: 0 4px;
        height: 34px;
        width: 120px;
        border-radius: 17px;
        display: flex;
        justify-content: center;
        align-items: center;
        transition: .3s;
    }

    #toggle-moving {
        position: absolute;
        background: var(--color-bg-0);
        box-shadow: var(--color-theme-3) 0 0 5px;
        color: var(--color-theme-1);
    }

    #toggle-login {
        display: none;
    }

    @media (max-width: 1100px) {
        .login {
            margin-top: 2rem;
        }
    }

    .form-select img {
        position: absolute;
        Z-index: 1;
        top: 25px;
        left: 10px;
        transform: translate(0, -50%);
        height: 2rem;
        width: 2rem;
    }
</style>