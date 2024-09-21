import {requestAPI} from "$lib/utils.js";
import {API_URL} from "$env/static/private";
import {redirect} from "@sveltejs/kit";

export const load = async ({ cookies }) => {
    const authCookie = cookies.get('Authorization');

    if (authCookie) {
        const token = authCookie.split(' ')[1];
        const teams = await requestAPI(`${API_URL}/teams`, "GET", token, null);
        teams.sort(() => Math.random() - 0.5);
        return {teams};
    } else {
        redirect(302, "/login");
    }
};