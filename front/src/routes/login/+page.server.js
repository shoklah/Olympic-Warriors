import {fail, redirect} from "@sveltejs/kit";

export const load = async ({locals}) => {
    const user = locals.user;

};

export const actions = {
    login: async ({cookies, request}) => {
        const formData = Object.fromEntries(await request.formData());
        const {email, password} = formData;

        if (!email) {
            return fail(400, { email, missing : {email: true }});
        }
        if (!password) {
            return fail(400, { email, missing: {password: true }});
        }

        // const {error, token} = await loginUser(email, password);
        // if (error) {
        //     return fail(400, { email, error });
        // }

        // setAuthToken({cookies, token});
        // throw redirect(302, "/")
    },

    register:  async ({cookies, request}) => {
        const formData = Object.fromEntries(await request.formData());
        const {email, password, first_name, last_name, password_conf} = formData;

        if (!first_name) {
            return fail(400, { email, missing: {first_name: true }});
        }
        if (!last_name) {
            return fail(400, { email, missing: {last_name: true }});
        }
        if (!email) {
            return fail(400, { email, missing : {email: true }});
        }
        if (!password) {
            return fail(400, { email, missing: {password: true }});
        }
        if (!password_conf) {
            return fail(400, { email, missing: {password_conf: true }});
        }
        if (password !== password_conf) {
            return fail(400, { email, error: "Passwords do not match" });
        }

        // const {error, token} = await createUser(email, password, city);

        // if (error) {
        //     console.log({error});
        //     return fail(500, {error});
        // }

        // setAuthToken({cookies, token});

        // throw  redirect(302, "/");
    }
}