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

</script>

<h1>disciplines</h1>
<div class="grid-container">
    {#each data.disciplines as discipline}
        <a href="/disciplines/{discipline.id}">
            <div class="card">
                <img src="{disciplineIcons[cleanString(discipline.name)]}" alt="{discipline.name}">
                <h2>{discipline.name}</h2>
            </div>
        </a>
    {/each}
</div>

<style>
    img {
        position: absolute;
        height: 90%;
        width: 50%;
        right: 0;
        opacity: .3;
    }

    .grid-container {
        display: grid;
        width: min(90%, 1400px);
        grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
        gap: 16px;
        padding: 16px;
        margin: 0 auto;
    }

    .card {
        position: relative;
        height: 200px;
        background-color: var(--color-theme-1);
        border-radius: 8px;
        padding: 16px;
        transition: .2s;
    }

    .card:hover {
        transform: translate(0, -4px);
    }

    h2 {
        color: var(--color-bg-0);
        font-size: 1.5rem;
        font-weight: 600;
    }

    a:hover {
        text-decoration: none;
    }

    @media (max-width: 580px) {
        h1 {
            margin-top: 0;
        }

        .grid-container {
            grid-template-columns: 1fr;
        }
    }
</style>
