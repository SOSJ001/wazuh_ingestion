<script lang="ts">
	import { fade, fly } from 'svelte/transition';
	import type { Alert } from '$lib/types/alert';

	interface Props {
		alert: Alert | null;
		onclose: () => void;
	}

	let { alert, onclose }: Props = $props();

	function levelClass(level: number): string {
		if (level >= 12) return 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200';
		if (level >= 8) return 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200';
		if (level >= 5) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-200';
		return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
	}

	$effect(() => {
		if (!alert || typeof document === 'undefined') return;
		document.addEventListener('keydown', handleKeydown);
		return () => document.removeEventListener('keydown', handleKeydown);
	});
</script>

{#if alert}
	<div
		role="dialog"
		aria-modal="true"
		aria-labelledby="alert-detail-title"
		class="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4"
		transition:fade={{ duration: 150 }}
	>
		<button
			type="button"
			class="absolute inset-0 bg-black/50"
			aria-label="Close modal"
			onclick={onclose}
		></button>
		<div
			class="relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col rounded-t-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-800 sm:rounded-2xl sm:border-b"
			in:fly={{ y: 20, duration: 200 }}
			out:fly={{ y: 10, duration: 150 }}
		>
			<div class="flex min-h-[56px] shrink-0 items-center justify-between border-b border-slate-200 px-3 py-3 dark:border-slate-700 sm:px-5 sm:py-4">
				<h2 id="alert-detail-title" class="text-base font-semibold text-slate-900 dark:text-slate-100 sm:text-lg">
					Alert details
				</h2>
				<button
					type="button"
					class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-700 dark:hover:text-slate-300"
					aria-label="Close"
					onclick={onclose}
				>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="h-5 w-5">
						<path
							fill-rule="evenodd"
							d="M5.47 5.47a.75.75 0 011.06 0L12 10.94l5.47-5.47a.75.75 0 111.06 1.06L13.06 12l5.47 5.47a.75.75 0 11-1.06 1.06L12 13.06l-5.47 5.47a.75.75 0 01-1.06-1.06L10.94 12 5.47 6.53a.75.75 0 010-1.06z"
							clip-rule="evenodd"
						/>
					</svg>
				</button>
			</div>
			<div class="flex-1 overflow-y-auto overflow-x-hidden px-3 py-3 sm:max-h-[calc(90vh-8rem)] sm:px-5 sm:py-4">
				<dl class="space-y-3 text-sm">
					<div>
						<dt class="font-medium text-slate-500 dark:text-slate-400">ID</dt>
						<dd class="mt-0.5 font-mono text-slate-900 dark:text-slate-100">{alert.id}</dd>
					</div>
					<div>
						<dt class="font-medium text-slate-500 dark:text-slate-400">Timestamp</dt>
						<dd class="mt-0.5 text-slate-900 dark:text-slate-100">{alert.timestamp}</dd>
					</div>
					<div>
						<dt class="font-medium text-slate-500 dark:text-slate-400">Agent</dt>
						<dd class="mt-0.5 text-slate-900 dark:text-slate-100">
							{alert.agent_name} <span class="text-slate-500 dark:text-slate-400">({alert.agent_id})</span>
						</dd>
					</div>
					<div>
						<dt class="font-medium text-slate-500 dark:text-slate-400">Rule level</dt>
						<dd class="mt-0.5">
							<span
								class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium {levelClass(alert.rule_level)}"
							>
								{alert.rule_level}
							</span>
						</dd>
					</div>
					<div>
						<dt class="font-medium text-slate-500 dark:text-slate-400">Rule ID</dt>
						<dd class="mt-0.5 font-mono text-slate-900 dark:text-slate-100">{alert.rule_id}</dd>
					</div>
					<div>
						<dt class="font-medium text-slate-500 dark:text-slate-400">Rule description</dt>
						<dd class="mt-0.5 text-slate-900 dark:text-slate-100">{alert.rule_description}</dd>
					</div>
					<div>
						<dt class="font-medium text-slate-500 dark:text-slate-400">Created at</dt>
						<dd class="mt-0.5 text-slate-900 dark:text-slate-100">{alert.created_at}</dd>
					</div>
				</dl>
				<div class="mt-5">
					<dt class="text-sm font-medium text-slate-500 dark:text-slate-400">Full log</dt>
					<pre
						class="mt-1.5 max-h-32 overflow-x-auto overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-mono text-slate-800 whitespace-pre-wrap dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 sm:max-h-48"
					>{(alert.full_log ?? '') || '—'}</pre>
				</div>
			</div>
			<div class="flex shrink-0 justify-end border-t border-slate-200 px-3 py-3 dark:border-slate-700 sm:px-5 sm:py-4">
				<button
					type="button"
					onclick={onclose}
					class="min-h-[44px] min-w-[80px] rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
				>
					Close
				</button>
			</div>
		</div>
	</div>
{/if}
