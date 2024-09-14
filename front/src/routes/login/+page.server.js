import {fail, redirect} from '@sveltejs/kit';
import {requestAPI, setAuthToken} from '$lib/utils';
import { API_URL } from '$env/static/private';

export const actions = {
    login: async ({cookies, request}) => {
        const formData = Object.fromEntries(await request.formData());
        const { username, password } = formData;

        console.log('login action called')

        // Validation
        const errors = {};
        if (!username) errors.username = 'username required';
        if (!password) errors.password = 'Password required';

        if (Object.keys(errors).length > 0) {
            return fail(400, { errors, username });
        }

        const {error, token} = await requestAPI(
            `${API_URL}/auth/token/`,
            'POST',
            null,
            {
                username: username,
                password: password
            }
        );

        if (error) {
            return fail(500, { error: error.message || 'Invalid username or password' });
        }

        if (!token) {
            return fail(500, { error: 'Authentication failed: token not received' });
        }

        setAuthToken({cookies, token});
        throw redirect(302, "/")
    }
};

    // register:  async ({cookies, request}) => {
    //     const formData = Object.fromEntries(await request.formData());
    //     const {email, password, first_name, last_name, password_conf} = formData;
    //
    //     if (!first_name) {
    //         return fail(400, { email, missing: {first_name: true }});
    //     }
    //     if (!last_name) {
    //         return fail(400, { email, missing: {last_name: true }});
    //     }
    //     if (!email) {
    //         return fail(400, { email, missing : {email: true }});
    //     }
    //     if (!password) {
    //         return fail(400, { email, missing: {password: true }});
    //     }
    //     if (!password_conf) {
    //         return fail(400, { email, missing: {password_conf: true }});
    //     }
    //     if (password !== password_conf) {
    //         return fail(400, { email, error: "Passwords do not match" });
    //     }
    //
    //     // const {error, token} = await createUser(email, password, city);
    //
    //     // if (error) {
    //     //     console.log({error});
    //     //     return fail(500, {error});
    //     // }
    //
    //     // setAuthToken({cookies, token});
    //
    //     // throw  redirect(302, "/");
    // }
