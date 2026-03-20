<script lang="ts">
	import { goto } from '$app/navigation';
	import { tick } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { flip } from 'svelte/animate';
	import type { Alert } from '$lib/types/alert';
	import AlertDetailModal from '$lib/components/AlertDetailModal.svelte';
	import { clearStoredToken, getAuthToken } from '$lib/auth';

	const API_BASE = 'http://127.0.0.1:8000';
	const PAGE_SIZE = 15;
	const AUTO_REFRESH_MS = 15000;

	let alerts = $state<Alert[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let selectedAlert = $state<Alert | null>(null);
	let currentPage = $state(1);
	let tableScrollEl = $state<HTMLDivElement | null>(null);
	let lastUpdatedAt = $state<Date | null>(null);
	let activeRequest = $state(false);

	async function goToPage(page: number) {
		currentPage = page;
		await tick();
		tableScrollEl?.scrollTo({ top: 0, behavior: 'smooth' });
	}

	const totalPages = $derived(Math.max(1, Math.ceil(alerts.length / PAGE_SIZE)));
	const paginatedAlerts = $derived(
		alerts.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
	);

	$effect(() => {
		if (currentPage > totalPages && totalPages >= 1) currentPage = totalPages;
	});

	function levelClass(level: number): string {
		if (level >= 12) return 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200';
		if (level >= 8) return 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200';
		if (level >= 5) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-200';
		return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
	}

	function integrityClass(status: Alert['integrity_status']): string {
		if (status === 'valid') return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200';
		if (status === 'invalid') return 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200';
		return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
	}

	function integrityLabel(status: Alert['integrity_status']): string {
		if (status === 'valid') return 'Valid';
		if (status === 'invalid') return 'Invalid';
		return 'Missing';
	}

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

	async function fetchAlerts() {
		if (activeRequest) return;
		activeRequest = true;
		loading = true;
		error = null;
		try {
			const res = await apiFetch('/alerts/verified');
			if (!res.ok) throw new Error(`API ${res.status}`);
			alerts = await res.json();
			lastUpdatedAt = new Date();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load verified alerts';
			alerts = [];
		} finally {
			loading = false;
			activeRequest = false;
		}
	}

	function formatLastUpdated(ts: Date | null): string {
		return ts ? ts.toLocaleTimeString() : 'Not synced yet';
	}

	$effect(() => {
		fetchAlerts();
		const intervalId = window.setInterval(() => {
			if (!document.hidden && !selectedAlert) fetchAlerts();
		}, AUTO_REFRESH_MS);
		const onVisible = () => {
			if (!document.hidden) fetchAlerts();
		};
		const onFocus = () => fetchAlerts();
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
			<h1 class="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-2xl">Verified alerts</h1>
			<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Alerts you have marked as reviewed.</p>
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
			out:fade={{ duration: 150 }}
			class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-3 py-3 text-red-800 sm:gap-4 sm:px-4 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200"
		>
			<span class="min-w-0 flex-1 text-sm font-medium">{error}</span>
			<button
				type="button"
				onclick={fetchAlerts}
				class="min-h-[44px] shrink-0 rounded-lg bg-red-100 px-4 py-2 text-sm font-medium hover:bg-red-200 dark:bg-red-900/50 dark:hover:bg-red-900"
			>
				Retry
			</button>
		</div>
	{/if}

	{#if loading && alerts.length === 0}
		<div
			in:fade={{ duration: 200 }}
			out:fade={{ duration: 150 }}
			class="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white py-16 shadow-sm dark:border-slate-700 dark:bg-slate-800/50"
		>
			<div
				class="h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-emerald-600 dark:border-slate-600 dark:border-t-emerald-400"
				aria-hidden="true"
			></div>
			<p class="mt-4 text-sm font-medium text-slate-600 dark:text-slate-400">Loading verified alerts…</p>
		</div>
	{:else if alerts.length === 0 && !loading}
		<div
			in:fade={{ duration: 300 }}
			class="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white py-16 shadow-sm dark:border-slate-700 dark:bg-slate-800/50"
		>
			<div
				class="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-900/50 dark:text-emerald-300"
				aria-hidden="true"
			>
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="h-7 w-7">
					<path
						fill-rule="evenodd"
						d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z"
						clip-rule="evenodd"
					/>
				</svg>
			</div>
			<p class="mt-4 text-sm font-medium text-slate-600 dark:text-slate-400">No verified alerts yet</p>
			<p class="mt-1 text-xs text-slate-500 dark:text-slate-500">Verify alerts from the Unverified tab to see them here.</p>
		</div>
	{:else}
		<div
			in:fly={{ y: 15, duration: 300 }}
			out:fade={{ duration: 150 }}
			class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm sm:rounded-2xl dark:border-slate-700 dark:bg-slate-800/50"
		>
			<div
				bind:this={tableScrollEl}
				class="max-h-[28rem] overflow-x-auto overflow-y-auto -webkit-overflow-scrolling-touch"
			>
				<table class="min-w-[640px] divide-y divide-slate-200 dark:divide-slate-600 md:min-w-full">
					<thead class="sticky top-0 z-10">
						<tr class="bg-slate-50/80 shadow-sm dark:bg-slate-800/80">
							<th
								scope="col"
								class="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5"
							>
								Time
							</th>
							<th
								scope="col"
								class="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5"
							>
								Agent
							</th>
							<th
								scope="col"
								class="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5"
							>
								Level
							</th>
							<th
								scope="col"
								class="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5"
							>
								Rule
							</th>
							<th
								scope="col"
								class="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5"
							>
								Log
							</th>
							<th
								scope="col"
								class="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5"
							>
								Integrity
							</th>
							<th
								scope="col"
								class="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5"
							>
								Verified by
							</th>
							<th scope="col" class="relative px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5">
								Action
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100 bg-white dark:divide-slate-700 dark:bg-slate-800/30">
						{#each paginatedAlerts as alert, i (alert.id)}
							<tr
								class="transition-colors hover:bg-slate-50/70 dark:hover:bg-slate-700/50"
								animate:flip={{ duration: 350 }}
								in:fly={{ y: 20, duration: 280, delay: Math.min(i * 35, 200) }}
							>
								<td class="whitespace-nowrap px-3 py-2.5 text-sm text-slate-600 dark:text-slate-400 sm:px-5 sm:py-3.5">
									{alert.timestamp}
								</td>
								<td class="whitespace-nowrap px-3 py-2.5 sm:px-5 sm:py-3.5">
									<span class="font-medium text-slate-900 dark:text-slate-100">{alert.agent_name}</span>
									<span class="text-slate-400 dark:text-slate-500"> · </span>
									<span class="text-slate-500 dark:text-slate-400">{alert.agent_id}</span>
								</td>
								<td class="whitespace-nowrap px-3 py-2.5 sm:px-5 sm:py-3.5">
									<span
										class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium {levelClass(alert.rule_level)}"
									>
										{alert.rule_level}
									</span>
								</td>
								<td class="max-w-[180px] px-3 py-2.5 sm:max-w-[240px] sm:px-5 sm:py-3.5 md:max-w-[240px]">
									<p class="truncate text-sm text-slate-700 dark:text-slate-300" title={alert.rule_description}>
										{alert.rule_description}
									</p>
								</td>
								<td class="max-w-[160px] px-3 py-2.5 sm:max-w-[280px] sm:px-5 sm:py-3.5 md:max-w-[280px]">
									<code
										class="block truncate rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-300"
										title={(alert.full_log ?? '') || '—'}
									>
										{(() => {
											const log = alert.full_log ?? '';
											return log ? `${log.slice(0, 72)}${log.length > 72 ? '…' : ''}` : '—';
										})()}
									</code>
								</td>
								<td class="whitespace-nowrap px-3 py-2.5 sm:px-5 sm:py-3.5">
									<span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium {integrityClass(alert.integrity_status)}">
										{integrityLabel(alert.integrity_status)}
									</span>
								</td>
								<td class="whitespace-nowrap px-3 py-2.5 text-sm sm:px-5 sm:py-3.5">
									<span class="font-medium text-slate-700 dark:text-slate-200">{alert.verified_by ?? '—'}</span>
									{#if alert.verified_at}
										<div class="text-xs text-slate-500 dark:text-slate-400">{alert.verified_at}</div>
									{/if}
								</td>
								<td class="whitespace-nowrap px-3 py-2.5 text-right sm:px-5 sm:py-3.5">
									<button
										type="button"
										onclick={() => (selectedAlert = alert)}
										class="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600 sm:min-h-0 sm:min-w-0 sm:py-1.5"
									>
										Details
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<!-- Pagination -->
			<div
				class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800/30 sm:px-4"
			>
				<p class="text-sm text-slate-600 dark:text-slate-400">
					Showing
					{alerts.length === 0
						? '0'
						: `${(currentPage - 1) * PAGE_SIZE + 1}–${Math.min(currentPage * PAGE_SIZE, alerts.length)}`}
					of {alerts.length} alert{alerts.length === 1 ? '' : 's'}
				</p>
				<div class="flex items-center gap-2">
					<button
						type="button"
						onclick={() => goToPage(Math.max(1, currentPage - 1))}
						disabled={currentPage <= 1}
						class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 disabled:pointer-events-none dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
					>
						Previous
					</button>
					<span class="text-sm text-slate-600 dark:text-slate-400">
						Page {currentPage} of {totalPages}
					</span>
					<button
						type="button"
						onclick={() => goToPage(Math.min(totalPages, currentPage + 1))}
						disabled={currentPage >= totalPages}
						class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 disabled:pointer-events-none dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
					>
						Next
					</button>
				</div>
			</div>
		</div>
	{/if}

	{#if selectedAlert}
		<AlertDetailModal alert={selectedAlert} onclose={() => (selectedAlert = null)} />
	{/if}
</div>
