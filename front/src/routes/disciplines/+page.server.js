import { request } from "$lib/utils.js";
import { API_URL } from "$env/static/private";

export async function load({ fetch }) {
    const disciplines = await request(`${API_URL}/disciplines`, "GET", null, null);
    return { disciplines };
}