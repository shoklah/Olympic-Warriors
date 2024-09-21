<script>
    export let data;
    const team = data.team;
</script>

<h1>{team.name}</h1>

<div class="players">
    {#each team.players.slice(0, 3) as player}
        <div class="player-card">
            <p>{player.first_name} {player.last_name}</p>
        </div>
    {/each}
</div>

<style>
    .players {
        display: flex;
        justify-content: space-around;
        margin-top: 20px;
    }

    .player-card {
        background: var(--color-theme-2);
        color: black;
        padding: 20px 40px;
        border-radius: 10px;
        width: 200px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        position: relative;
        overflow: hidden;
        transition: transform 0.3s;
    }

    .player-card p {
        font-size: 1.2rem;
        font-weight: 600;
    }

    .player-card:hover {
        transform: scale(1.05);
    }

    @media (max-width: 1000px) {
        .players {
            flex-direction: column;
            align-items: center;
            gap: 20px;
        }
    }
</style>
