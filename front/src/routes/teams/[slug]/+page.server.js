import {requestAPI} from "$lib/utils.js";
import {API_URL} from "$env/static/private";

export const load = async ({locals, params}) => {
    const team = await requestAPI(`${API_URL}/team/` + params.slug, "GET", null, null);
    return {team};
};