
<footer>
    <div id="flex-div">
        <p>© 2024 - </p>
        <div id="flex-icons">

        </div>
    </div>
</footer>

<style>
    footer {
        display: flex;
        justify-content: flex-start;
        align-items: flex-start;
        background-color: #2e2e2e;
        color: var(--color-bg-0);
    }

    #flex-div {
        width: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }

    footer p {
        margin-bottom: 10px;
        padding: 0 1rem;
    }

    footer #flex-icons {
        display: flex;
        justify-content: center;
        align-items: center;
        flex-direction: row;
        gap: 20px;
    }

    a {
        transition: transform .3s;
    }

    a:hover {
        transform: scale(1.2);
    }
</style>