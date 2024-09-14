export function cleanString(str) {
    const cleaned = str.replace(/[\s']/g, '').toLowerCase();
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

export const setAuthToken = ({cookies, token}) => {
    cookies.set('Authorization', `Bearer ${token}`, {
        httpOnly: true,
        secure: true,
        sameSite: 'strict',
        maxAge: 60 * 60 * 24,
        path: '/'
    });
};

export async function requestAPI(url, method, token, body) {
    try {
        const headers = {};

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const options = {
            method,
            headers,
        };

        if (body) {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);

        const contentType = response.headers.get('content-type');

        let data;
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else {
            data = await response.text();
        }

        if (!response.ok) {
            return {
                error: data,
                status: response.status,
                statusText: response.statusText,
            };
        }

        return data;
    } catch (error) {
        return { error: error.message };
    }
}
