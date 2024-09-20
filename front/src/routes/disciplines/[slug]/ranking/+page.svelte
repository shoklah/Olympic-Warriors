<script>
    export let data;
    let results = data.results;
    let discipline = data.discipline;
</script>


<h1>{discipline.name}</h1>

<div id="teams">
    {#each results as result}
        <a href="/teams/{result.team}">
            <div class="team-card">
                <p>{result.ranking}. {result.teamName}</p>
                {#if result.result_type == 'TIM'}
                    <p>{result.time}</p>
                {:else}
                    <p>{result.points} pts</p>
                {/if}
            </div>
        </a>
    {/each}
</div>


<style>
    #teams {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin: 0 1vw;
    }

    .team-card {
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

    #teams .team-card:nth-of-type(1) {
        background: linear-gradient(45deg, #e6b800, #f2d06b, #e6b800, #e6ac00);
    }

    #teams .team-card:nth-of-type(2) {
        background: linear-gradient(45deg, #e0e0e0, #cfcfcf, #b0b0b0, #d1d1d1, #f7f7f7);
    }

    #teams .team-card:nth-of-type(3) {
        background: linear-gradient(45deg, #cd7f32, #b87333, #8c5311);
    }

    .team-card:hover {
        transform: translate(0, -4px);
    }

    .team-card p {
        font-size: 1rem;
        font-weight: 600;
    }

    @media (min-width: 1000px) {
        #teams {
            order: 1;
            width: min(65%, 800px);
        }
    }
</style>