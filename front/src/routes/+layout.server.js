export const load = async ({cookies}) => {
    const auth = cookies.get('Authorization');

    if (auth) {
        const sections = [
            { name: 'Home', url: '/' },
            { name: 'Teams', url: '/teams' },
            { name: 'Disciplines', url: '/disciplines' },
            { name: 'Photos', url: '/photos' },
            { name: 'Profile', url: '/profile' }
        ];
        return {sections};
    }

    const sections = [
        { name: 'Home', url: '/' },
        { name: 'Disciplines', url: '/disciplines' },
        { name: 'Login', url: '/login' }
    ];
    return {sections};
};