<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';

	let { children } = $props();
	let dark = $state(false);

	function toggleTheme() {
		dark = !dark;
		if (typeof document !== 'undefined') {
			document.documentElement.classList.toggle('dark', dark);
			localStorage.setItem('theme', dark ? 'dark' : 'light');
		}
	}

	onMount(() => {
		dark = document.documentElement.classList.contains('dark');
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
	<link
		href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap"
		rel="stylesheet"
	/>
</svelte:head>

<header
	class="sticky top-0 z-10 border-b border-slate-200/80 bg-white/95 shadow-sm backdrop-blur dark:border-slate-700/80 dark:bg-slate-900/95"
>
	<div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-3 py-3 sm:px-6 sm:py-4 lg:px-8">
		<a
			href="/"
			class="flex min-w-0 shrink-0 items-center gap-2 font-semibold text-slate-800 no-underline dark:text-slate-100"
		>
			<span
				class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-sm dark:bg-emerald-500"
				aria-hidden="true"
			>
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="h-5 w-5">
					<path
						fill-rule="evenodd"
						d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z"
						clip-rule="evenodd"
					/>
				</svg>
			</span>
			<span class="hidden truncate sm:inline">Wazuh Integration</span>
		</a>
		<div class="flex min-w-0 shrink-0 items-center gap-2">
			<nav class="flex gap-0.5 rounded-lg bg-slate-100 p-1 dark:bg-slate-800 sm:gap-1" aria-label="Main">
				<a
					href="/"
					class="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition-colors sm:min-h-0 sm:min-w-0 sm:px-4 {$page.url.pathname === '/'
						? 'bg-white text-emerald-700 shadow-sm dark:bg-slate-700 dark:text-emerald-300'
						: 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'}"
				>
					Unverified
				</a>
				<a
					href="/verified"
					class="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition-colors sm:min-h-0 sm:min-w-0 sm:px-4 {$page.url.pathname.startsWith('/verified')
						? 'bg-white text-emerald-700 shadow-sm dark:bg-slate-700 dark:text-emerald-300'
						: 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'}"
				>
					Verified
				</a>
			</nav>
			<button
				type="button"
				onclick={toggleTheme}
				class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-100 text-slate-600 transition hover:scale-105 active:scale-95 hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700 sm:h-9 sm:w-9"
				aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
			>
				{#if dark}
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="h-5 w-5">
						<path
							d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.166a.75.75 0 00-1.06-1.06l-1.591 1.59a.75.75 0 101.06 1.061l1.591-1.59zM21.75 12a.75.75 0 01-.75.75h-2.25a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.834 18.894a.75.75 0 001.06-1.06l-1.591-1.591a.75.75 0 10-1.061 1.06l1.59 1.591zM12 18a.75.75 0 01.75.75V21a.75.75 0 01-1.5 0v-2.25A.75.75 0 0112 18zM7.758 17.303a.75.75 0 00-1.061-1.06l-1.591 1.59a.75.75 0 001.06 1.061l1.591-1.59zM6 12a.75.75 0 01-.75.75H3a.75.75 0 010-1.5h2.25A.75.75 0 016 12zM6.697 7.757a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 00-1.061 1.06l1.59 1.591z"
						/>
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="h-5 w-5">
						<path
							fill-rule="evenodd"
							d="M9.528 1.718a.75.75 0 01.162.819A8.97 8.97 0 009 6a9 9 0 009 9 8.97 8.97 0 003.463-.69.75.75 0 01.981.98 10.503 10.503 0 01-9.694 6.46c-5.799 0-10.5-4.701-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 01.818.162z"
							clip-rule="evenodd"
						/>
					</svg>
				{/if}
			</button>
		</div>
	</div>
</header>

<main class="mx-auto max-w-7xl px-3 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8">
	{#key $page.url.pathname}
		<div in:fade={{ duration: 220 }} out:fade={{ duration: 150 }}>
			{@render children()}
		</div>
	{/key}
</main>
