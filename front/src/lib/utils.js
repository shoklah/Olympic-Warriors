export function cleanString(str) {
    const cleaned = str.replace(/[\s']/g, '').toLowerCase();
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

export async function requestAPI(url, method, token, body) {
    try {
        const options = {
            method: method,
            headers: {
                "Content-Type": "application/json",
                "authorization": `Bearer ${token}`
            }
        };

        if (method !== "GET") {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(`${url}`, options);

        if (!response.ok) {
            throw new Error(`Failed to fetch ${url}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error(error);
        throw error;
    }
}
