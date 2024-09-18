import {redirect} from "@sveltejs/kit";

export const load = async ({ cookies }) => {
    const authCookie = cookies.get('Authorization');

    if (authCookie) {
        const token = authCookie.split(' ')[1];



    } else {
        redirect(302, "/login");
    }
};