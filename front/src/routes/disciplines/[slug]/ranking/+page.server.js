import { requestAPI } from "$lib/utils.js";
import { API_URL } from "$env/static/private";
import { redirect } from "@sveltejs/kit";

export const load = async ({ cookies, params }) => {
    const authCookie = cookies.get('Authorization');

    if (authCookie) {
        const token = authCookie.split(' ')[1];

        const discipline_id = params.slug;

        // Fetch the discipline data
        const disciplineUrl = `${API_URL}/discipline/${discipline_id}/`;
        const disciplineData = await requestAPI(disciplineUrl, "GET", token, null);

        // Fetch the results data
        const resultsUrl = `${API_URL}/results/discipline/${discipline_id}/`;
        const resultsData = await requestAPI(resultsUrl, "GET", token, null);

        // Extract unique team IDs from the results
        const teamIds = [...new Set(resultsData.map(result => result.team))];

        // Fetch team data for each team ID in parallel
        const teamPromises = teamIds.map(teamId =>
            requestAPI(`${API_URL}/team/${teamId}/`, "GET", token, null)
        );
        const teamsData = await Promise.all(teamPromises);

        // Create a map from team ID to team data for quick lookup
        const teamMap = new Map();
        teamsData.forEach(team => {
            teamMap.set(team.id, team);
        });

        // Enrich results with team names and other team data
        const enrichedResults = resultsData.map(result => ({
            ...result,
            teamName: teamMap.get(result.team)?.name || 'Unknown',
            teamRanking: teamMap.get(result.team)?.ranking || 0,
            teamTotalPoints: teamMap.get(result.team)?.total_points || 0,
        }));

        // Return the enriched results and discipline data to the page
        return {
            results: enrichedResults,
            discipline: disciplineData
        };

    } else {
        throw redirect(302, "/login");
    }
};