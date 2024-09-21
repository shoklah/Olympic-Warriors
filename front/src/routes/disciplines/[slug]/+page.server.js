import {requestAPI} from "$lib/utils.js";
import {API_URL} from "$env/static/private";

export async function load({ cookies, params }) {

    const authCookie = cookies.get('Authorization');
    let action = null;
    const discipline = await requestAPI(`${API_URL}/discipline/` + params.slug, "GET", null, null);

    if (authCookie) {
        const token = authCookie.split(' ')[1];

        if (discipline.name === "Blindtest") {
            action = "blindtest";
        }

    }

    return { discipline, action };
}