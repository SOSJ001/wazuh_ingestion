const TOKEN_KEY = 'wazuh_dashboard_token';

export function getStoredToken(): string {
	if (typeof localStorage === 'undefined') return '';
	return localStorage.getItem(TOKEN_KEY) ?? '';
}

export function setStoredToken(token: string): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.removeItem(TOKEN_KEY);
}

export function getDefaultToken(): string {
	return import.meta.env.VITE_DASHBOARD_BEARER_TOKEN ?? '';
}

export function getAuthToken(): string {
	const stored = getStoredToken();
	return stored || getDefaultToken();
}
