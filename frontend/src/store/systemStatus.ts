/**
 * Skyline — Shared System Status Store
 *
 * Module-level reactive refs so any component can read/write WS + GPU state
 * without a full Pinia/Vuex setup. MainLayout reads; Detection.vue writes.
 */
import { ref } from 'vue'

export const wsStatus   = ref<'connected' | 'connecting' | 'disconnected'>('disconnected')
export const isGpuActive = ref(false)
