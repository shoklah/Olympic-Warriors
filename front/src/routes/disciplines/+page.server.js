import { requestAPI } from "$lib/utils.js";
import { API_URL } from "$env/static/private";

export async function load({ fetch, locals }) {
    const disciplines = await requestAPI(`${API_URL}/disciplines`, "GET", null, null);
    return { disciplines };
}
