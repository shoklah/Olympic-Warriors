<script>
    import { onMount } from 'svelte';

    import eclipse from "$lib/img/eclipse.png";
    import title from "$lib/img/title.svg";

    import blindtest from "$lib/img/icons/blindtest.svg";
    import cachecache from "$lib/img/icons/cachecache.svg";
    import crossfit from "$lib/img/icons/crossfit.svg";
    import co from "$lib/img/icons/co.svg";
    import dodgeball from "$lib/img/icons/dodgeball.svg";
    import rugby from "$lib/img/icons/rugby.svg";

    let countdownDate = new Date('September 21, 2024 09:00:00').getTime();
    let days, hours, minutes, seconds;

    const updateCountdown = () => {
        const now = new Date().getTime();
        const distance = countdownDate - now;

        days = Math.floor(distance / (1000 * 60 * 60 * 24));
        hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        seconds = Math.floor((distance % (1000 * 60)) / 1000);

        if (distance < 0) {
            clearInterval(interval);
            days = hours = minutes = seconds = 0;
        }
    };

    let interval;
    onMount(() => {
        interval = setInterval(updateCountdown, 1000);
        updateCountdown();
        return () => clearInterval(interval);
    });
</script>

<div class="fullscreen">
    <img id="eclipse" src={eclipse} alt="eclipse" />
    <img id="title" src={title} alt="OLYMPIC WARRIORS">

    <div class="sportcolumn">
        <img src={rugby} alt="rugby">

        <img src={cachecache} alt="cache cache">
        <img src={crossfit} alt="crossfit">
    </div>
    <div class="sportcolumn">
        <img src={co} alt="course d'orientation">
        <img src={dodgeball} alt="dodgeball">
        <img src={blindtest} alt="blindtest">
    </div>
</div>

<div id="countdown">
    <div><span>{days}</span>Jours</div>
    <div><span>{hours}</span>Heures</div>
    <div><span>{minutes}</span>Minutes</div>
    <div><span>{seconds}</span>Secondes</div>
</div>

<style>
    .sportcolumn {
        position: absolute;
        display: flex;
        flex-direction: column;
        opacity: .3;
        gap: 180px;
    }

    .sportcolumn:first-of-type{
        left: 20vw;
    }

    .sportcolumn:first-of-type :nth-child(2) {
        transform: translate(-80px, 0);
    }

    .sportcolumn:last-of-type {
        right: 20vw;
    }

    .sportcolumn:last-of-type :nth-child(2) {
        transform: translate(80px, 0);
    }

    .sportcolumn img {
        width: min(100px, 10vw);
    }

    #countdown {
        display: flex;
        justify-content: center;
        gap: 2rem;
        font-size: 1rem;
        margin: 1rem 0;
        color: var(--color-theme-1);
    }

    #countdown div {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 75px;
    }

    #countdown span {
        font-size: 2.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }

    #eclipse {
        width: min(100%, 1200px);
        margin: 0 auto;
        transform: translate(1%, 0); /* to correct img default */
        z-index: -10;
    }

    #title {
        width: min(25%, 300px);
        position: absolute;
    }

    .fullscreen {
        position: relative;
        height: 65vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }

</style>