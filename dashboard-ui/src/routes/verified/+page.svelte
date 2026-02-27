<script lang="ts">
	import { tick } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { flip } from 'svelte/animate';
	import type { Alert } from '$lib/types/alert';
	import AlertDetailModal from '$lib/components/AlertDetailModal.svelte';

	const API_BASE = 'http://127.0.0.1:8000';
	const PAGE_SIZE = 15;

	let alerts = $state<Alert[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let selectedAlert = $state<Alert | null>(null);
	let currentPage = $state(1);
	let tableScrollEl = $state<HTMLDivElement | null>(null);

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

	async function fetchAlerts() {
		loading = true;
		error = null;
		try {
			const res = await fetch(`${API_BASE}/alerts/verified`);
			if (!res.ok) throw new Error(`API ${res.status}`);
			alerts = await res.json();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load verified alerts';
			alerts = [];
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		fetchAlerts();
	});
</script>

<div class="space-y-6" in:fade={{ duration: 200 }} out:fade={{ duration: 150 }}>
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div class="min-w-0">
			<h1 class="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-2xl">Verified alerts</h1>
			<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Alerts you have marked as reviewed.</p>
		</div>
		<button
			type="button"
			onclick={fetchAlerts}
			disabled={loading}
			class="inline-flex min-h-[44px] min-w-[7rem] shrink-0 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition hover:scale-[1.02] hover:bg-slate-50 active:scale-[0.98] disabled:scale-100 disabled:opacity-80 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
		>
			{#if loading}
				<span
					class="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-transparent dark:border-slate-500"
					aria-hidden="true"
				></span>
				<span>Refreshing…</span>
			{:else}
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="1.5"
					stroke="currentColor"
					class="h-4 w-4"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
					/>
				</svg>
				Refresh
			{/if}
		</button>
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
							<th scope="col" class="relative px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 sm:px-5 sm:py-3.5">
								Action
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100 bg-white dark:divide-slate-700 dark:bg-slate-800/30">
						{#each alerts as alert, i (alert.id)}
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
