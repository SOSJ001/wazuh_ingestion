<script lang="ts">
	import { goto } from '$app/navigation';
	import { fade, fly } from 'svelte/transition';
	import { setStoredToken } from '$lib/auth';

	const API_BASE = 'http://127.0.0.1:8000';
	const DEFAULT_USER = import.meta.env.VITE_DASHBOARD_AUTH_USER ?? 'admin';

	let username = $state(DEFAULT_USER);
	let password = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);

	async function login() {
		loading = true;
		error = null;
		try {
			const res = await fetch(`${API_BASE}/auth/token`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password })
			});
			if (!res.ok) throw new Error(`Login failed (${res.status})`);
			const data = await res.json();
			if (!data.access_token) throw new Error('Token missing in response');
			setStoredToken(data.access_token);
			await goto('/status');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to authenticate';
		} finally {
			loading = false;
		}
	}
</script>

<div class="mx-auto max-w-md space-y-6" in:fade={{ duration: 200 }} out:fade={{ duration: 150 }}>
	<div>
		<h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Sign in</h1>
		<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Authenticate to access protected API routes.</p>
	</div>

	{#if error}
		<div in:fly={{ y: -8, duration: 250 }} class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800 dark:border-rose-800 dark:bg-rose-950/50 dark:text-rose-200">
			{error}
		</div>
	{/if}

	<form
		class="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800/50"
		onsubmit={(e) => {
			e.preventDefault();
			login();
		}}
	>
		<label class="block space-y-1">
			<span class="text-sm font-medium text-slate-700 dark:text-slate-300">Username</span>
			<input
				bind:value={username}
				type="text"
				class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none ring-emerald-500 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
				required
			/>
		</label>

		<label class="block space-y-1">
			<span class="text-sm font-medium text-slate-700 dark:text-slate-300">Password</span>
			<input
				bind:value={password}
				type="password"
				class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none ring-emerald-500 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
				required
			/>
		</label>

		<button
			type="submit"
			disabled={loading}
			class="inline-flex min-h-[44px] w-full items-center justify-center rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-70 dark:bg-emerald-500 dark:hover:bg-emerald-600"
		>
			{loading ? 'Signing in…' : 'Sign in'}
		</button>
	</form>
</div>
