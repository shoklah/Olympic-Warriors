<script>
    export let data;

    const discipline = data.discipline;
</script>

<h1>{discipline.name}</h1>

<!--{#if data.action !== null}-->
<!--    <button on:click={data.action}>{data.action}</button>-->
<!--{/if}-->

<style>
    button {
        background-color: var(--color-bg-0);
        border: 1px solid #ccc;
        border-radius: 10px;
        padding: 0 10px;
        box-shadow: 0 2px 4px #00000030;
        transition: .3s;
        display: flex;
        text-decoration: none;
        justify-content: space-between;
    }
</style>
