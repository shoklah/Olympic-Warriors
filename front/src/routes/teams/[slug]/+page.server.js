import {requestAPI} from "$lib/utils.js";
import {API_URL} from "$env/static/private";
import {redirect} from "@sveltejs/kit";

export const load = async ({ cookies, params }) => {
    const authCookie = cookies.get('Authorization');

    if (authCookie) {
        const token = authCookie.split(' ')[1];

        const team = await requestAPI(`${API_URL}/team/` + params.slug, "GET", token, null);
        return {team};

    } else {
        redirect(302, "/login");
    }
};