<script>
  export let data;
  import {cleanString} from "$lib/utils.js";

  import Orienteering from "$lib/img/icons/orienteering.svg";
  import Dodgeball from "$lib/img/icons/dodgeball.svg";
  import Blindtest from "$lib/img/icons/blindtest.svg";
  import Hideandseek from "$lib/img/icons/hideandseek.svg";
  import Crossfit from "$lib/img/icons/crossfit.svg";
  import Rugby from "$lib/img/icons/rugby.svg";
  const disciplineIcons = {Orienteering, Dodgeball, Blindtest, Hideandseek, Crossfit, Rugby};

  const teams = data.ranking
</script>

<div class="flex-box">
    <div id="disciplines">
        {#each data.disciplines as discipline}
            <a class="discipline-card" href="/disciplines/{discipline.id}/ranking"
            style="{discipline.reveal_score ? 'opacity: 1;' : 'opacity: .2;'}">
                <img src="{disciplineIcons[cleanString(discipline.name)]}" alt="{discipline.name}">
            </a>
        {/each}
    </div>

    <div id="teams">
        {#each teams as team}
            <a href="/teams/{team.id}/ranking">
                <div class="team-card">
                    <p>{team.ranking}. {team.name}</p>
                    <p>{team.points} pts</p>
                </div>
            </a>
        {/each}
        <a href="/teams/1/ranking" class="team-card">
            <p>1. Nom d'équipe</p>
            <p>36 pts</p>
        </a>
        <a href="/teams/1/ranking" class="team-card">
            <p>1. Nom d'équipe</p>
            <p>36 pts</p>
        </a>
        <a href="/teams/1/ranking" class="team-card">
            <p>1. Nom d'équipe</p>
            <p>36 pts</p>
        </a>
        <a href="/teams/1/ranking" class="team-card">
            <p>1. Nom d'équipe</p>
            <p>36 pts</p>
        </a>
        <a href="/teams/1/ranking" class="team-card">
            <p>1. Nom d'équipe</p>
            <p>36 pts</p>
        </a>
        <a href="/teams/1/ranking" class="team-card">
            <p>1. Nom d'équipe</p>
            <p>36 pts</p>
        </a>
        <a href="/teams/1/ranking" class="team-card">
            <p>1. Nom d'équipe</p>
            <p>36 pts</p>
        </a>
    </div>

</div>


<style>
    .flex-box {
        display: flex;
        flex-direction: column;
        gap: 20px;
    }

    #disciplines {
        display: flex;
        gap: clamp(5px, 3vw, 40px);
        margin: 0 clamp(10px, 4vw, 40px);
        overflow-x: auto;
        overflow-y: hidden;
        flex-wrap: nowrap;
        -ms-overflow-style: none;
        scrollbar-width: none;
    }

    #disciplines::-webkit-scrollbar {
        display: none;
    }

    .discipline-card {
        height: clamp(70px, 12vw, 100px);
        width: clamp(70px, 12vw, 100px);
        border-radius: 50%;
        background-color: var(--color-theme-1);
        display: flex;
        justify-content: center;
        align-items: center;
        transition: .3s;
    }

    .discipline-card img {
        height: 80%;
        width: 80%;
    }

    .discipline-card:hover {
        transform: translate(0, -4px);
    }

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
        .flex-box {
            display: flex;
            flex-direction: row;
            justify-content: center;
            gap: 20px;
            margin: 80px 0;
        }

        #teams {
            order: 1;
            width: min(65%, 800px);
        }

        #disciplines {
            order: 2;
            flex-direction: column;
            gap: 15px;
            overflow: visible;
        }

        .discipline-card {
            border-radius: 10px;
            height: 100px;
            width: 100px;
        }
    }
</style>
