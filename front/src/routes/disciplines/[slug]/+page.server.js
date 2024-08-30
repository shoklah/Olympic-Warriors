import {request} from "$lib/utils.js";
import {API_URL} from "$env/static/private";

export async function load({ params }) {
    return request(`${API_URL}/discipline/` + params.slug, "GET", null, null);
}