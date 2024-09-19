import {requestAPI} from "$lib/utils.js";
import {API_URL} from "$env/static/private";

export const load = async ({locals}) => {
    const teams = await requestAPI(`${API_URL}/teams`, "GET", null, null);
    return {teams};
};