<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, RouterLink, useRoute } from 'vue-router'
import { wsStatus, isGpuActive } from '@/store/systemStatus'
import SkylineLogo from '@/assets/logo/skyline_logo.png'

const route = useRoute()
const pageTitle = computed(() => (route.meta?.title as string) ?? 'SKYLINE')

const wsLabel = computed(() => ({
  connected:    'ONLINE',
  connecting:   'SYNCING',
  disconnected: 'OFFLINE',
}[wsStatus.value]))
</script>

<template>
  <div class="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-200">

    <!-- ── Sidebar ──────────────────────────────────────────────────────────── -->
    <aside class="w-56 flex-shrink-0 flex flex-col bg-slate-950 border-r border-slate-800">

      <!-- Logo -->
      <div class="h-16 flex items-center px-5 border-b border-slate-800 flex-shrink-0">
        <div class="flex items-center gap-2.5">
          <div class="relative w-9 h-9 flex-shrink-0">
            <img
              :src="SkylineLogo"
              alt="Skyline"
              class="relative w-full h-full object-contain"
              draggable="false"
              @error="($event.target as HTMLImageElement).style.display='none'"
            />
            <!-- Fallback if logo image is missing -->
            <div
              class="absolute inset-0 rounded-full bg-gradient-to-br from-blue-400 to-emerald-400 flex items-center justify-center"
              :class="SkylineLogo ? 'opacity-0' : ''"
            >
              <span class="text-white font-bold text-xs">SK</span>
            </div>
          </div>
          <div>
            <div class="text-sm font-bold tracking-widest text-white">SKYLINE</div>
            <div class="text-xs text-slate-500 tracking-wider leading-none">AI VISION</div>
          </div>
        </div>
      </div>

      <!-- Nav -->
      <nav class="flex-1 px-3 py-4 space-y-1">
        <RouterLink
          to="/"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group"
          :class="$route.path === '/'
            ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
            : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'"
        >
          <span class="text-base">🏠</span>
          <div>
            <div class="font-medium">系统总览</div>
            <div class="text-xs opacity-60">Dashboard</div>
          </div>
        </RouterLink>

        <RouterLink
          to="/detection"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group"
          :class="$route.path === '/detection'
            ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
            : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'"
        >
          <span class="text-base">🔍</span>
          <div>
            <div class="font-medium">智能检测舱</div>
            <div class="text-xs opacity-60">Detection</div>
          </div>
        </RouterLink>

        <RouterLink
          to="/history"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150"
          :class="$route.path === '/history'
            ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
            : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'"
        >
          <span class="text-base">📁</span>
          <div>
            <div class="font-medium">历史记录库</div>
            <div class="text-xs opacity-60">History</div>
          </div>
        </RouterLink>

        <RouterLink
          to="/performance"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150"
          :class="$route.path === '/performance'
            ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
            : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'"
        >
          <span class="text-base">📊</span>
          <div>
            <div class="font-medium">性能分析</div>
            <div class="text-xs opacity-60">Performance</div>
          </div>
        </RouterLink>
      </nav>

      <!-- Sidebar footer -->
      <div class="px-4 py-3 border-t border-slate-800 flex-shrink-0">
        <div class="text-xs text-slate-600 tracking-wider">v1.0.0 · SKYLINE IVAP</div>
      </div>
    </aside>

    <!-- ── Main area (header + content) ────────────────────────────────────── -->
    <div class="flex-1 flex flex-col overflow-hidden min-w-0">

      <!-- Header -->
      <header class="h-16 flex-shrink-0 flex items-center justify-between px-6
                     bg-slate-900/80 border-b border-slate-800 backdrop-blur">

        <!-- Page title -->
        <div>
          <h1 class="text-base font-semibold text-white tracking-wide">{{ pageTitle }}</h1>
          <p class="text-xs text-slate-500">Intelligent Visual Analysis Platform</p>
        </div>

        <!-- Status indicators -->
        <div class="flex items-center gap-4">
          <!-- WebSocket status -->
          <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700">
            <span
              class="w-2 h-2 rounded-full flex-shrink-0"
              :class="{
                'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]': wsStatus === 'connected',
                'bg-yellow-400 shadow-[0_0_6px_rgba(250,204,21,0.8)] animate-pulse': wsStatus === 'connecting',
                'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.8)]': wsStatus === 'disconnected',
              }"
            ></span>
            <span class="text-xs font-mono font-medium"
              :class="{
                'text-emerald-400': wsStatus === 'connected',
                'text-yellow-400': wsStatus === 'connecting',
                'text-red-400': wsStatus === 'disconnected',
              }"
            >WS · {{ wsLabel }}</span>
          </div>

          <!-- GPU status -->
          <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700">
            <span
              class="w-2 h-2 rounded-full flex-shrink-0"
              :class="isGpuActive
                ? 'bg-blue-400 shadow-[0_0_6px_rgba(96,165,250,0.8)] animate-pulse'
                : 'bg-slate-600'"
            ></span>
            <span class="text-xs font-mono font-medium"
              :class="isGpuActive ? 'text-blue-400' : 'text-slate-500'"
            >GPU · {{ isGpuActive ? 'ACTIVE' : 'IDLE' }}</span>
          </div>
        </div>
      </header>

      <!-- Router view -->
      <main class="flex-1 overflow-hidden">
        <RouterView />
      </main>
    </div>
  </div>
</template>
