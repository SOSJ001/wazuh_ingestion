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
	let verifyingId = $state<string | null>(null);
	let selectedAlert = $state<Alert | null>(null);
	let lastUpdatedAt = $state<Date | null>(null);
	let activeRequest = $state(false);

	type AgentFilterMode = 'all' | 'include' | 'exclude';
	let agentFilterMode = $state<AgentFilterMode>('all');
	let selectedAgentIds = $state<Set<string>>(new Set());
	let agentFilterOpen = $state(false);
	let currentPage = $state(1);
	let tableScrollEl = $state<HTMLDivElement | null>(null);

	async function goToPage(page: number) {
		currentPage = page;
		await tick();
		tableScrollEl?.scrollTo({ top: 0, behavior: 'smooth' });
	}

	const uniqueAgents = $derived(
		Array.from(
			new Map(alerts.map((a) => [a.agent_id, { id: a.agent_id, name: a.agent_name }])).values()
		).sort((a, b) => a.name.localeCompare(b.name))
	);

	const filteredAlerts = $derived.by(() => {
		if (agentFilterMode === 'all') return alerts;
		if (selectedAgentIds.size === 0) return alerts;
		if (agentFilterMode === 'include') return alerts.filter((a) => selectedAgentIds.has(a.agent_id));
		return alerts.filter((a) => !selectedAgentIds.has(a.agent_id));
	});

	const totalPages = $derived(Math.max(1, Math.ceil(filteredAlerts.length / PAGE_SIZE)));
	const paginatedAlerts = $derived(
		filteredAlerts.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
	);

	$effect(() => {
		if (currentPage > totalPages && totalPages >= 1) currentPage = totalPages;
	});

	function toggleAgentSelection(agentId: string) {
		selectedAgentIds = new Set(selectedAgentIds);
		if (selectedAgentIds.has(agentId)) selectedAgentIds.delete(agentId);
		else selectedAgentIds.add(agentId);
		selectedAgentIds = new Set(selectedAgentIds);
	}

	function clearAgentFilter() {
		agentFilterMode = 'all';
		selectedAgentIds = new Set();
		agentFilterOpen = false;
	}

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
			const res = await apiFetch('/alerts');
			if (!res.ok) throw new Error(`API ${res.status}`);
			alerts = await res.json();
			lastUpdatedAt = new Date();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load alerts';
			alerts = [];
		} finally {
			loading = false;
			activeRequest = false;
		}
	}

	async function verify(id: string) {
		verifyingId = id;
		try {
			const res = await apiFetch(`/verify/${encodeURIComponent(id)}`, {
				method: 'POST'
			});
			if (!res.ok) throw new Error('Verify failed');
			alerts = alerts.filter((a) => a.id !== id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Verify failed';
		} finally {
			verifyingId = null;
		}
	}

	function formatLastUpdated(ts: Date | null): string {
		return ts ? ts.toLocaleTimeString() : 'Not synced yet';
	}

	$effect(() => {
		fetchAlerts();
		const intervalId = window.setInterval(() => {
			if (!document.hidden && !selectedAlert && !verifyingId) fetchAlerts();
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

	function handleClickOutside(e: MouseEvent) {
		const target = e.target as Node;
		if (agentFilterOpen && !document.querySelector('[data-agent-filter]')?.contains(target)) {
			agentFilterOpen = false;
		}
	}
</script>

<svelte:window onclick={handleClickOutside} />

<div class="space-y-6" in:fade={{ duration: 200 }} out:fade={{ duration: 150 }}>
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div class="min-w-0">
			<h1 class="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-2xl">Unverified alerts</h1>
			<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Review and mark alerts as verified for human-in-the-loop.</p>
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
			<p class="mt-4 text-sm font-medium text-slate-600 dark:text-slate-400">Loading alerts…</p>
		</div>
	{:else if alerts.length === 0 && !loading}
		<div
			in:fade={{ duration: 300 }}
			class="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white py-16 shadow-sm dark:border-slate-700 dark:bg-slate-800/50"
		>
			<div
				class="flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500"
				aria-hidden="true"
			>
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="h-7 w-7">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
			</div>
			<p class="mt-4 text-sm font-medium text-slate-600 dark:text-slate-400">No unverified alerts</p>
			<p class="mt-1 text-xs text-slate-500 dark:text-slate-500">New alerts will appear here when the ingestion script fetches them.</p>
		</div>
	{:else if alerts.length > 0}
		<!-- Agent filter -->
		<div
			data-agent-filter
			class="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-3 dark:border-slate-700 dark:bg-slate-800/50 sm:px-4"
		>
			<span class="text-sm font-medium text-slate-600 dark:text-slate-400">Filter by agent</span>
			<div class="flex flex-wrap items-center gap-2">
				<button
					type="button"
					onclick={() => { agentFilterMode = 'all'; selectedAgentIds = new Set(); agentFilterOpen = false; }}
					class="rounded-lg px-3 py-1.5 text-sm font-medium transition {agentFilterMode === 'all'
						? 'bg-white text-emerald-700 shadow-sm dark:bg-slate-700 dark:text-emerald-300'
						: 'text-slate-600 hover:bg-slate-200/80 dark:text-slate-400 dark:hover:bg-slate-700'}"
				>
					All
				</button>
				<button
					type="button"
					onclick={() => { agentFilterMode = 'include'; agentFilterOpen = agentFilterMode !== 'include' || !agentFilterOpen; }}
					class="rounded-lg px-3 py-1.5 text-sm font-medium transition {agentFilterMode === 'include'
						? 'bg-white text-emerald-700 shadow-sm dark:bg-slate-700 dark:text-emerald-300'
						: 'text-slate-600 hover:bg-slate-200/80 dark:text-slate-400 dark:hover:bg-slate-700'}"
				>
					Include
				</button>
				<button
					type="button"
					onclick={() => { agentFilterMode = 'exclude'; agentFilterOpen = agentFilterMode !== 'exclude' || !agentFilterOpen; }}
					class="rounded-lg px-3 py-1.5 text-sm font-medium transition {agentFilterMode === 'exclude'
						? 'bg-white text-emerald-700 shadow-sm dark:bg-slate-700 dark:text-emerald-300'
						: 'text-slate-600 hover:bg-slate-200/80 dark:text-slate-400 dark:hover:bg-slate-700'}"
				>
					Exclude
				</button>
			</div>
			{#if agentFilterMode !== 'all'}
				<div class="relative">
					<button
						type="button"
						onclick={() => (agentFilterOpen = !agentFilterOpen)}
						class="inline-flex min-h-[36px] items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
						aria-expanded={agentFilterOpen}
						aria-haspopup="listbox"
					>
						{selectedAgentIds.size === 0
							? 'Select agents…'
							: `${selectedAgentIds.size} agent${selectedAgentIds.size === 1 ? '' : 's'} selected`}
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4 {agentFilterOpen ? 'rotate-180' : ''}">
							<path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
						</svg>
					</button>
					{#if agentFilterOpen}
						<div
							class="absolute left-0 top-full z-20 mt-1 max-h-56 w-64 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-600 dark:bg-slate-800"
							role="listbox"
						>
							{#each uniqueAgents as agent}
								<button
									type="button"
									role="option"
									aria-selected={selectedAgentIds.has(agent.id)}
									onclick={() => toggleAgentSelection(agent.id)}
									class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700"
								>
									<span
										class="flex h-4 w-4 shrink-0 items-center justify-center rounded border border-slate-300 dark:border-slate-500 {selectedAgentIds.has(agent.id)
											? 'bg-emerald-600 text-white dark:bg-emerald-500'
											: ''}"
									>
										{#if selectedAgentIds.has(agent.id)}
											<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-3 w-3">
												<path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
											</svg>
										{/if}
									</span>
									<span class="min-w-0 truncate font-medium">{agent.name}</span>
									<span class="shrink-0 text-slate-400 dark:text-slate-500">({agent.id})</span>
								</button>
							{/each}
						</div>
					{/if}
				</div>
				{#if selectedAgentIds.size > 0}
					<button
						type="button"
						onclick={clearAgentFilter}
						class="text-sm text-slate-500 underline hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
					>
						Clear filter
					</button>
				{/if}
			{/if}
			<span class="ml-auto text-sm text-slate-500 dark:text-slate-400">
				{filteredAlerts.length} of {alerts.length} alert{alerts.length === 1 ? '' : 's'}
			</span>
		</div>

		{#if filteredAlerts.length === 0}
			<div
				in:fade={{ duration: 200 }}
				class="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white py-12 shadow-sm dark:border-slate-700 dark:bg-slate-800/50"
			>
				<p class="text-sm font-medium text-slate-600 dark:text-slate-400">No alerts match the current filter.</p>
				<button
					type="button"
					onclick={clearAgentFilter}
					class="mt-3 text-sm text-emerald-600 underline hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300"
				>
					Clear filter
				</button>
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
							<th scope="col" class="relative px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5">
								<span class="sr-only">Action</span>
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100 bg-white dark:divide-slate-700 dark:bg-slate-800/30">
						{#each paginatedAlerts as alert, i (alert.id)}
							<tr
								class="transition-colors hover:bg-slate-50/70 dark:hover:bg-slate-700/50"
								animate:flip={{ duration: 350 }}
								in:fly={{ y: 20, duration: 280, delay: Math.min(i * 35, 200) }}
								out:fly={{ y: -24, duration: 320 }}
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
								<td class="whitespace-nowrap px-3 py-2.5 text-right sm:px-5 sm:py-3.5">
									<div class="flex flex-wrap items-center justify-end gap-1.5 sm:gap-2">
										<button
											type="button"
											onclick={() => (selectedAlert = alert)}
											class="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600 sm:min-h-0 sm:min-w-0 sm:py-1.5"
										>
											Details
										</button>
										<button
											type="button"
											onclick={() => verify(alert.id)}
											disabled={verifyingId === alert.id}
											class="inline-flex min-h-[44px] min-w-[5.5rem] items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white shadow-sm transition hover:scale-105 hover:bg-emerald-700 active:scale-95 disabled:scale-100 disabled:opacity-80 dark:bg-emerald-500 dark:hover:bg-emerald-600 sm:py-1.5"
										>
											{#if verifyingId === alert.id}
												<span
													class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
													aria-hidden="true"
												></span>
												<span>Verifying…</span>
											{:else}
												<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
													<path
														fill-rule="evenodd"
														d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
														clip-rule="evenodd"
													/>
												</svg>
												Verify
											{/if}
										</button>
									</div>
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
					{filteredAlerts.length === 0
						? '0'
						: `${(currentPage - 1) * PAGE_SIZE + 1}–${Math.min(currentPage * PAGE_SIZE, filteredAlerts.length)}`}
					of {filteredAlerts.length} alert{filteredAlerts.length === 1 ? '' : 's'}
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
	{/if}

	{#if selectedAlert}
		<AlertDetailModal alert={selectedAlert} onclose={() => (selectedAlert = null)} />
	{/if}
</div>
