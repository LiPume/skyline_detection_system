<script setup lang="ts">
/**
 * TaskAssistantPanel — 任务助手区
 * 轻量级自然语言任务解析建议面板。
 * 只展示推荐结果，不修改现有 Detection 表单状态。
 */
import { ref, onUnmounted } from 'vue'
import { parseTask } from '@/api/agent'
import type { AgentRecommendation } from '@/types/skyline'

// ── State ─────────────────────────────────────────────────────────────────────

const userInput       = ref('')
const isLoading       = ref(false)
const result          = ref<AgentRecommendation | null>(null)
const errorMsg        = ref<string | null>(null)

// 阶段提示
const stageIndex      = ref(0)
const LONG_WAIT_MS    = 8000
const stages           = ['正在理解你的任务', '正在匹配可用模型与类别', '正在生成推荐方案']

let stageTimer: ReturnType<typeof setInterval> | null = null
let longWaitTimer: ReturnType<typeof setTimeout> | null = null
let longWaitShown = ref(false)

function startTimers() {
  stopTimers()
  stageIndex.value = 0
  longWaitShown.value = false
  stageTimer = setInterval(() => {
    if (stageIndex.value < stages.length - 1) stageIndex.value++
  }, 1200)
  longWaitTimer = setTimeout(() => {
    longWaitShown.value = true
  }, LONG_WAIT_MS)
}

function stopTimers() {
  if (stageTimer !== null) { clearInterval(stageTimer); stageTimer = null }
  if (longWaitTimer !== null) { clearTimeout(longWaitTimer); longWaitTimer = null }
  stageIndex.value = 0
  longWaitShown.value = false
}

onUnmounted(stopTimers)

// ── Actions ───────────────────────────────────────────────────────────────────

async function handleParse() {
  const text = userInput.value.trim()
  if (!text) return

  isLoading.value = true
  errorMsg.value  = null
  result.value    = null
  startTimers()

  try {
    result.value = await parseTask(text)
  } catch (err: unknown) {
    errorMsg.value = '任务理解失败，请稍后重试。你也可以直接手动配置模型和类别。'
  } finally {
    isLoading.value = false
    stopTimers()
  }
}

function confidenceLabel(c: string): string {
  return { high: '高', medium: '中', low: '低' }[c] ?? c
}

function confidenceColor(c: string): string {
  return { high: 'text-emerald-400', medium: 'text-amber-400', low: 'text-slate-500' }[c] ?? 'text-slate-400'
}

function confidenceBg(c: string): string {
  return { high: 'bg-emerald-500/10 border-emerald-500/30', medium: 'bg-amber-500/10 border-amber-500/30', low: 'bg-slate-800/50 border-slate-700/50' }[c] ?? 'bg-slate-800/50 border-slate-700/50'
}
</script>

<template>
  <div class="rounded-xl border border-slate-700/60 bg-slate-800/40 overflow-hidden">

    <!-- Header -->
    <div class="px-4 py-3 border-b border-slate-700/50 flex items-center gap-2">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
           class="text-blue-400 flex-shrink-0">
        <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z" opacity=".3"/>
        <path d="M12 6v6l4 2"/>
      </svg>
      <span class="text-xs font-semibold text-slate-200 tracking-wide uppercase">
        任务助手
      </span>
      <span class="ml-auto text-[10px] text-slate-600">AI 辅助配置</span>
    </div>

    <!-- Input area -->
    <div class="px-4 py-3 space-y-3">
      <textarea
        v-model="userInput"
        placeholder="例如：帮我检测视频中的汽车和行人"
        rows="3"
        spellcheck="false"
        class="w-full bg-slate-900/70 border border-slate-700 rounded-lg
               px-3 py-2 text-sm text-slate-200 resize-none outline-none
               placeholder:text-slate-600 font-mono
               focus:border-blue-500/60 focus:ring-1 focus:ring-blue-500/20
               transition-all"
        :disabled="isLoading"
        @keydown.ctrl.enter.prevent="handleParse"
      ></textarea>

      <button
        class="w-full py-2 rounded-lg text-xs font-semibold tracking-wide transition-all duration-150
               flex items-center justify-center gap-2"
        :class="isLoading || !userInput.trim()
          ? 'bg-slate-700/50 border border-slate-600 text-slate-500 cursor-not-allowed'
          : 'bg-blue-600/20 border border-blue-500/50 text-blue-400 hover:bg-blue-600/30 hover:border-blue-500/70 active:scale-[0.98]'"
        :disabled="isLoading || !userInput.trim()"
        @click="handleParse"
      >
        <svg v-if="isLoading" class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2a10 10 0 1 0 10 10"/>
          <polyline points="12,6 12,12 16,14"/>
        </svg>
        {{ isLoading ? stages[stageIndex] : '理解任务' }}
      </button>

      <!-- Stage hint & long-wait hint -->
      <div v-if="isLoading" class="flex items-center gap-2">
        <span class="text-[10px] text-slate-500 leading-relaxed">{{ stages[stageIndex] }}…</span>
      </div>
      <div v-if="isLoading && longWaitShown" class="text-[10px] text-slate-600 leading-relaxed">
        智能解析较慢，你也可以稍后直接手动配置
      </div>
    </div>

    <!-- Error -->
    <div v-if="errorMsg" class="mx-4 mb-3 px-3 py-2 rounded-lg bg-red-950/50 border border-red-800/60">
      <p class="text-xs text-red-400">{{ errorMsg }}</p>
    </div>

    <!-- Result -->
    <div v-if="result" class="px-4 pb-4 space-y-2.5">

      <div class="border-t border-slate-700/50 pt-3">
        <p class="text-[10px] uppercase tracking-wider text-slate-600 mb-2 font-semibold">推荐结果</p>

        <!-- 推荐模型 -->
        <div class="flex items-center justify-between">
          <span class="text-xs text-slate-500">推荐模型</span>
          <span class="text-xs font-semibold text-white">{{ result.recommended_model_id }}</span>
        </div>

        <!-- 确信度 -->
        <div class="flex items-center justify-between mt-1.5">
          <span class="text-xs text-slate-500">确信度</span>
          <span class="text-xs font-medium" :class="confidenceColor(result.confidence)">
            {{ confidenceLabel(result.confidence) }}
          </span>
        </div>

        <!-- 推荐类别 -->
        <div v-if="result.target_classes.length > 0" class="mt-2">
          <span class="text-xs text-slate-500">推荐类别</span>
          <div class="flex flex-wrap gap-1 mt-1">
            <span
              v-for="cls in result.target_classes"
              :key="cls"
              class="inline-flex items-center px-2 py-0.5 rounded-md
                     bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-mono"
            >{{ cls }}</span>
          </div>
        </div>

        <!-- 报告建议 -->
        <div v-if="result.report_required" class="mt-2 flex items-center gap-1.5">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-emerald-400 flex-shrink-0">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14,2 14,8 20,8"/>
          </svg>
          <span class="text-xs text-emerald-400">建议生成检测报告</span>
        </div>

        <!-- 推荐原因 -->
        <div v-if="result.reason" class="mt-2 px-2.5 py-2 rounded-lg" :class="confidenceBg(result.confidence)">
          <p class="text-xs text-slate-400 leading-relaxed">{{ result.reason }}</p>
        </div>
      </div>

    </div>

  </div>
</template>
