

export const handle = async ({event, resolve}) => {
    const authCookie = event.cookies.get('Authorization');

    if (authCookie) {
        const token = authCookie.split(' ')[1];
        try {
            // verify the token

            // find the user in the database

            const user = {
                op: true,
            }
            event.locals.user = user;

        } catch (error) {
            console.log(error);
        }
    }
    return await resolve(event);
};
