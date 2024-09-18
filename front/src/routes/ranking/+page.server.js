import { requestAPI } from "$lib/utils.js";
import { API_URL } from "$env/static/private";
import {redirect} from "@sveltejs/kit";

export const load = async ({ cookies }) => {
    const authCookie = cookies.get('Authorization');

    if (authCookie) {
        const token = authCookie.split(' ')[1];

        const disciplines = await requestAPI(`${API_URL}/disciplines`, "GET", token, null);
        const ranking = await requestAPI(`${API_URL}/results/`, "GET", token, null);

        disciplines.sort((a, b) => { return a.id - b.id; });
        ranking.sort((a, b) => { return b.ranking - a.ranking; });

        console.log(ranking);

        return {disciplines, ranking};

    } else {
        redirect(302, "/login");
    }
};
