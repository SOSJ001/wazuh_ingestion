<script lang="ts">
	import { goto } from '$app/navigation';
	import { fade, fly } from 'svelte/transition';
	import { clearStoredToken, getAuthToken } from '$lib/auth';

	const API_BASE = 'http://127.0.0.1:8000';
	const AUTO_REFRESH_MS = 15000;

	type HealthResponse = {
		api_status: string;
		api_time: string;
		current_user: string;
		ingestion: {
			last_poll_started_at: string | null;
			last_poll_completed_at: string | null;
			last_poll_status: string;
			last_error: string | null;
			last_inserted_count: number;
			last_validation_reject_count: number;
		};
	};

	type ConfigResponse = {
		current_user: string;
		poll_interval_seconds: number;
		security_mode: {
			hmac_enabled: boolean;
			bearer_required: boolean;
			tls_verify_enabled: boolean;
			ssh_host_verification_enabled: boolean;
		};
		paths: {
			status_path: string;
			ca_cert_path: string;
			ssh_known_hosts_path: string;
		};
	};

	let loading = $state(true);
	let error = $state<string | null>(null);
	let health = $state<HealthResponse | null>(null);
	let config = $state<ConfigResponse | null>(null);
	let lastUpdatedAt = $state<Date | null>(null);
	let activeRequest = $state(false);

	async function apiFetch(path: string, init: RequestInit = {}) {
		const token = getAuthToken();
		if (!token) {
			await goto('/login');
			throw new Error('Missing auth token. Redirecting to login.');
		}
		const headers = new Headers(init.headers ?? {});
		headers.set('Authorization', `Bearer ${token}`);
		const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
		if (res.status === 401) {
			clearStoredToken();
			await goto('/login');
		}
		return res;
	}

	async function fetchStatus() {
		if (activeRequest) return;
		activeRequest = true;
		loading = true;
		error = null;
		try {
			const [healthRes, configRes] = await Promise.all([apiFetch('/system/health'), apiFetch('/system/config')]);
			if (!healthRes.ok) throw new Error(`Health API ${healthRes.status}`);
			if (!configRes.ok) throw new Error(`Config API ${configRes.status}`);
			health = await healthRes.json();
			config = await configRes.json();
			lastUpdatedAt = new Date();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to fetch system status';
		} finally {
			loading = false;
			activeRequest = false;
		}
	}

	function formatLastUpdated(ts: Date | null): string {
		return ts ? ts.toLocaleTimeString() : 'Not synced yet';
	}

	function badgeClass(on: boolean): string {
		return on
			? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200'
			: 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200';
	}

	function pollStatusClass(status: string): string {
		if (status === 'ok') return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200';
		if (status === 'running') return 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200';
		if (status === 'error') return 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200';
		return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
	}

	$effect(() => {
		fetchStatus();
		const intervalId = window.setInterval(() => {
			if (!document.hidden) fetchStatus();
		}, AUTO_REFRESH_MS);
		const onVisible = () => {
			if (!document.hidden) fetchStatus();
		};
		const onFocus = () => fetchStatus();
		document.addEventListener('visibilitychange', onVisible);
		window.addEventListener('focus', onFocus);
		return () => {
			window.clearInterval(intervalId);
			document.removeEventListener('visibilitychange', onVisible);
			window.removeEventListener('focus', onFocus);
		};
	});
</script>

<div class="space-y-6" in:fade={{ duration: 200 }} out:fade={{ duration: 150 }}>
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div class="min-w-0">
			<h1 class="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-2xl">System status</h1>
			<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Operational health, security mode, and configuration visibility.</p>
		</div>
		<div class="flex flex-wrap items-center justify-end gap-2 text-xs sm:text-sm">
			<span class="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-1 font-medium text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300">
				<span class="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
				Live
			</span>
			<span class="text-slate-500 dark:text-slate-400">Auto-refresh every {Math.round(AUTO_REFRESH_MS / 1000)}s</span>
			<span class="text-slate-500 dark:text-slate-400">Last updated: {formatLastUpdated(lastUpdatedAt)}</span>
			{#if activeRequest}
				<span class="text-emerald-600 dark:text-emerald-400">Updating…</span>
			{/if}
		</div>
	</div>

	{#if error}
		<div
			in:fly={{ y: -8, duration: 250 }}
			class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800 dark:border-rose-800 dark:bg-rose-950/50 dark:text-rose-200"
		>
			{error}
		</div>
	{/if}

	{#if health && config}
		<div class="grid gap-4 md:grid-cols-2">
			<div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
				<h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">API health</h2>
				<div class="mt-3 space-y-2 text-sm text-slate-700 dark:text-slate-300">
					<p><span class="font-medium">API status:</span> {health.api_status}</p>
					<p><span class="font-medium">Current user:</span> {health.current_user}</p>
					<p><span class="font-medium">API time:</span> {health.api_time}</p>
					<p><span class="font-medium">Last poll started:</span> {health.ingestion.last_poll_started_at ?? '—'}</p>
					<p><span class="font-medium">Last poll completed:</span> {health.ingestion.last_poll_completed_at ?? '—'}</p>
					<p>
						<span class="font-medium">Poll status:</span>
						<span class="ml-2 inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium {pollStatusClass(health.ingestion.last_poll_status)}">
							{health.ingestion.last_poll_status}
						</span>
					</p>
					<p><span class="font-medium">Last inserted count:</span> {health.ingestion.last_inserted_count}</p>
					<p><span class="font-medium">Validation rejects:</span> {health.ingestion.last_validation_reject_count}</p>
					<p><span class="font-medium">Last error:</span> {health.ingestion.last_error ?? 'None'}</p>
				</div>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
				<h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Security & config</h2>
				<div class="mt-3 space-y-2 text-sm text-slate-700 dark:text-slate-300">
					<p><span class="font-medium">Current user:</span> {config.current_user}</p>
					<p><span class="font-medium">Poll interval:</span> {config.poll_interval_seconds}s</p>
					<p class="flex items-center gap-2">
						<span class="font-medium">HMAC enabled:</span>
						<span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium {badgeClass(config.security_mode.hmac_enabled)}">
							{config.security_mode.hmac_enabled ? 'Enabled' : 'Disabled'}
						</span>
					</p>
					<p class="flex items-center gap-2">
						<span class="font-medium">Bearer required:</span>
						<span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium {badgeClass(config.security_mode.bearer_required)}">
							{config.security_mode.bearer_required ? 'Enabled' : 'Disabled'}
						</span>
					</p>
					<p class="flex items-center gap-2">
						<span class="font-medium">TLS verify:</span>
						<span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium {badgeClass(config.security_mode.tls_verify_enabled)}">
							{config.security_mode.tls_verify_enabled ? 'Enabled' : 'Disabled'}
						</span>
					</p>
					<p class="flex items-center gap-2">
						<span class="font-medium">SSH host verification:</span>
						<span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium {badgeClass(config.security_mode.ssh_host_verification_enabled)}">
							{config.security_mode.ssh_host_verification_enabled ? 'Enabled' : 'Disabled'}
						</span>
					</p>
					<p><span class="font-medium">Status path:</span> {config.paths.status_path}</p>
					<p><span class="font-medium">CA cert path:</span> {config.paths.ca_cert_path}</p>
					<p><span class="font-medium">known_hosts path:</span> {config.paths.ssh_known_hosts_path}</p>
				</div>
			</div>
		</div>
	{/if}
</div>
