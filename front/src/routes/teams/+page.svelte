<script>
  export let data;
</script>

<h1>Teams</h1>
<div class="grid-container">
    {#each data.teams as team}
        <a href="/teams/{team.id}">
            <div class="card">
                <h2>{team.name}</h2>
                <div class="players">
                    {#each team.players as player}
                        <p>{player.first_name} {player.last_name}</p>
                    {/each}
                </div>
            </div>
        </a>
    {/each}
</div>

<style>
    h1 {
        visibility: hidden;
    }

    a:hover {
        text-decoration: none;
    }

    .players {
        display: flex;
        justify-content: space-around;
    }

    .grid-container {
        display: grid;
        width: min(calc(100vw - 32px), 1000px);
        grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
        gap: 16px;
        padding: 16px;
        margin: 0 auto;
    }

    .card {
        background-color: var(--color-bg-0);
        border: 1px solid #ccc;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 2px 4px #00000030;
        transition: .2s;
    }

    .card:hover {
        transform: translate(0, -4px);
    }

    h2 {
        font-size: 1.2rem;
        font-weight: 600;
    }

    p {
        margin: 5px;
    }

    @media (max-width: 479px) {
        h2 {
            margin: 0;
        }
    }

    @media (max-width: 700px) {
        .grid-container {
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        }

        .players {
            flex-direction: column;
            align-items: center;
            margin: 0;
        }
    }

    @media (max-width: 1000px) {
        h1 {
            display: none;
        }
    }
</style>
