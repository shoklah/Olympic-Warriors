import { requestAPI } from "$lib/utils.js";
import { API_URL } from "$env/static/private";
import {redirect} from "@sveltejs/kit";

export const load = async ({ cookies }) => {
    const authCookie = cookies.get('Authorization');

    if (authCookie) {
        const token = authCookie.split(' ')[1];

        const disciplines = await requestAPI(`${API_URL}/disciplines`, "GET", token, null);
        const teams = await requestAPI(`${API_URL}/teams`, "GET", token, null);

        disciplines.sort((a, b) => { return a.id - b.id; });
        teams.sort((a, b) => { return b.global_points - a.global_points; });

        console.log(teams);

        return {disciplines, teams};

    } else {
        redirect(302, "/login");
    }
};
