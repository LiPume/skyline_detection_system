<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// ── Scene video data ───────────────────────────────────────────────────────────
const sceneVideos = [
  {
    key: 'yolo-highlights',
    title: 'YOLO-World 检测集锦',
    subtitle: '开放词汇目标检测与多目标识别展示',
    src: '/demo/homepage-showcase/yolo-world-highlights.mp4',
    tag: 'Open-Vocabulary',
  },
  {
    key: 'highway-patrol',
    title: '高速公路巡检',
    subtitle: '面向道路车辆场景的实时检测展示',
    src: '/demo/homepage-showcase/highway-patrol.mp4',
    tag: 'Highway',
  },
  {
    key: 'low-light',
    title: '低照度场景检测',
    subtitle: '弱光环境下的目标识别与感知展示',
    src: '/demo/homepage-showcase/low-light.mp4',
    tag: 'Low Light',
  },
  {
    key: 'pedestrians-overpass',
    title: '天桥行人场景',
    subtitle: '复杂背景下的行人目标检测展示',
    src: '/demo/homepage-showcase/pedestrians-on-overpass.mp4',
    tag: 'Pedestrian',
  },
]

// ── Main banner video ─────────────────────────────────────────────────────────
const mainVideoSrc = '/demo/homepage-showcase/yolo-world-highlights.mp4'

// ── Capability cards ──────────────────────────────────────────────────────────
const capabilities = [
  {
    icon: '🎯',
    title: '高精度复杂场景检测',
    desc: '面向小目标密集、背景复杂与尺度变化场景提升稳健识别能力',
    tags: ['多尺度增强', '上下文建模', '稳定检测'],
  },
  {
    icon: '🧠',
    title: '开放类别识别扩展',
    desc: '支持任务驱动类别配置，增强跨场景目标扩展能力',
    tags: ['YOLO-World', '在线词表', '类别扩展'],
  },
  {
    icon: '⚡',
    title: '实时分析与智能交互',
    desc: '结合实时推理链路与AI任务助手，提升检测过程的交互性',
    tags: ['ONNX', '模型推荐', 'AI报告'],
  },
]

// ── Feature entry cards ───────────────────────────────────────────────────────
const featureEntries = [
  {
    icon: '🔍',
    title: '智能检测舱',
    desc: '实时视频流接入、模型配置与目标检测展示',
    route: '/detection',
  },
  {
    icon: '📁',
    title: '历史记录',
    desc: '检测结果回溯与结构化记录查看',
    route: '/history',
  },
  {
    icon: '📊',
    title: '模型评估',
    desc: '训练过程、PR 曲线与类别表现分析',
    route: '/performance',
  },
]

// ── Video error handling ──────────────────────────────────────────────────────
const videoErrors = ref<Record<string, boolean>>({})

function onVideoError(key: string) {
  videoErrors.value[key] = true
}

function retryVideo(key: string) {
  videoErrors.value[key] = false
}
</script>

<template>
  <div class="h-full overflow-y-auto">

    <!-- ── Grid background pattern ──────────────────────────────────────────── -->
    <div
      class="fixed inset-0 pointer-events-none z-0"
      style="background-image: linear-gradient(rgba(30,41,59,0.3) 1px, transparent 1px),
                                linear-gradient(90deg, rgba(30,41,59,0.3) 1px, transparent 1px);
             background-size: 48px 48px;"
    ></div>

    <div class="relative z-10 px-6 py-6 space-y-8 max-w-screen-2xl mx-auto">

      <!-- SECTION 1: Banner / Main Visual -->
      <section>
        <!-- Decorative top accent line -->
        <div class="flex items-center gap-3 mb-5">
          <div class="h-px flex-1 bg-gradient-to-r from-blue-600/60 via-blue-500/30 to-transparent"></div>
          <div class="w-2 h-2 rounded-full bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]"></div>
        </div>

        <div class="grid grid-cols-[1fr_1.15fr] gap-6 items-stretch">

          <!-- Left: Title & meta -->
          <div class="flex flex-col justify-center space-y-5">
            <!-- Version badge -->
            <div class="inline-flex items-center gap-2 self-start px-3 py-1 rounded-full
                        bg-blue-500/10 border border-blue-500/25 text-blue-400 text-xs font-mono">
              <span class="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></span>
              COMPETITION WORK — 2026
            </div>

            <!-- Title -->
            <div>
              <h1 class="text-5xl font-black tracking-tight text-white leading-none mb-2">
                天际线
                <span class="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-cyan-400 to-blue-400">
                  SKYLINE
                </span>
              </h1>
              <p class="text-base text-slate-400 font-medium leading-snug">
                多场景无人机目标智能检测与识别系统
              </p>
            </div>

            <!-- One-liner -->
            <p class="text-sm text-slate-500 leading-relaxed max-w-lg">
              面向复杂航拍视频流的高精度检测、开放类别扩展与实时部署一体化方案
            </p>

            <!-- Capability tags -->
            <div class="flex flex-wrap gap-2">
              <span
                v-for="tag in ['复杂场景稳检', '开放类别扩展', '实时部署优化','AI任务辅助']"
                :key="tag"
                class="px-3 py-1 rounded-md text-xs font-medium
                       bg-slate-800 border border-slate-700 text-slate-300
                       hover:border-cyan-500/50 hover:text-cyan-400 transition-all duration-200 cursor-default"
              >
                {{ tag }}
              </span>
            </div>
          </div>

          <!-- Right: Main video showcase -->
          <div
            class="rounded-2xl border border-slate-700/80 bg-slate-900/60 overflow-hidden
                   shadow-2xl shadow-black/50 relative group"
            style="min-height: 280px;"
          >
            <!-- Corner HUD decorations -->
            <div class="absolute top-3 left-3 w-6 h-6 border-l-2 border-t-2 border-cyan-500/40 rounded-tl-lg z-10 pointer-events-none"></div>
            <div class="absolute top-3 right-3 w-6 h-6 border-r-2 border-t-2 border-cyan-500/40 rounded-tr-lg z-10 pointer-events-none"></div>
            <div class="absolute bottom-3 left-3 w-6 h-6 border-l-2 border-b-2 border-cyan-500/40 rounded-bl-lg z-10 pointer-events-none"></div>
            <div class="absolute bottom-3 right-3 w-6 h-6 border-r-2 border-b-2 border-cyan-500/40 rounded-br-lg z-10 pointer-events-none"></div>

            <!-- Video or placeholder -->
            <template v-if="!videoErrors['__main__']">
              <video
                :src="mainVideoSrc"
                autoplay
                muted
                loop
                playsinline
                class="w-full h-full object-cover"
                style="min-height: 280px;"
                @error="onVideoError('__main__')"
              ></video>
            </template>
            <template v-else>
              <div
                class="w-full flex flex-col items-center justify-center gap-3"
                style="min-height: 280px;"
              >
                <div class="text-4xl opacity-30">🖼</div>
                <span class="text-sm text-slate-600">视频待接入</span>
                <button
                  class="mt-1 px-3 py-1 rounded-md text-xs border border-slate-700
                         text-slate-500 hover:text-slate-300 hover:border-slate-500 transition-all"
                  @click="retryVideo('__main__')"
                >
                  重试
                </button>
              </div>
            </template>

            <!-- Bottom gradient overlay -->
            <div class="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-slate-950/90 to-transparent pointer-events-none"></div>

            <!-- Bottom-left status -->
            <div class="absolute bottom-3 left-4 flex items-center gap-2">
              <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-mono font-bold
                           bg-red-500/90 text-white shadow-[0_0_8px_rgba(239,68,68,0.6)]">
                <span class="w-1.5 h-1.5 rounded-full bg-white animate-pulse"></span>
                LIVE DEMO
              </span>
              <span class="text-xs text-slate-400 font-mono">UAV Detection Preview</span>
            </div>

            <!-- Top-right tag -->
            <div class="absolute top-3 right-4">
              <span class="px-2 py-0.5 rounded-md text-xs font-mono
                           bg-slate-800/80 border border-slate-600/60 text-slate-400">
                Multi-scene Analysis
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- SECTION 2: Three Core Capabilities -->
      <section>
        <div class="flex items-center gap-3 mb-4">
          <div class="h-px flex-1 bg-gradient-to-r from-slate-700 via-slate-800 to-slate-700"></div>
          <span class="text-xs font-mono text-slate-600 tracking-widest uppercase">Core Capabilities</span>
          <div class="h-px flex-1 bg-gradient-to-r from-slate-700 via-slate-800 to-slate-700"></div>
        </div>

        <div class="grid grid-cols-3 gap-4">
          <div
            v-for="cap in capabilities"
            :key="cap.title"
            class="rounded-xl border border-slate-800 bg-slate-900/50 p-5
                   hover:border-blue-500/40 hover:bg-slate-900/70
                   transition-all duration-200 hover:-translate-y-0.5"
          >
            <div class="flex items-start gap-3 mb-3">
              <span class="text-2xl leading-none mt-0.5">{{ cap.icon }}</span>
              <h3 class="text-sm font-semibold text-white leading-snug">{{ cap.title }}</h3>
            </div>
            <p class="text-xs text-slate-500 leading-relaxed mb-4">{{ cap.desc }}</p>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="tag in cap.tags"
                :key="tag"
                class="px-2 py-0.5 rounded text-xs font-mono
                       bg-blue-500/10 border border-blue-500/20 text-blue-400/80"
              >
                {{ tag }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- SECTION 3: Scene Demo Videos (2x2 Grid) -->
      <section>
        <div class="flex items-center gap-3 mb-1">
          <div class="h-px flex-1 bg-gradient-to-r from-transparent via-blue-600/40 to-transparent"></div>
          <span class="text-xs font-mono text-blue-500/70 tracking-widest uppercase">Application Scenarios</span>
          <div class="h-px flex-1 bg-gradient-to-r from-transparent via-blue-600/40 to-transparent"></div>
        </div>
        <div class="flex items-center gap-3 mb-5">
          <h2 class="text-xl font-bold text-white">典型应用场景</h2>
          <span class="text-sm text-slate-500">多场景无人机检测任务演示</span>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div
            v-for="scene in sceneVideos"
            :key="scene.key"
            class="rounded-2xl border border-slate-800 bg-slate-900/50 overflow-hidden
                   hover:border-blue-500/50 hover:-translate-y-0.5
                   transition-all duration-200 group"
          >
            <!-- Video container -->
            <div class="relative overflow-hidden" style="height: 220px;">
              <!-- Corner HUD decorations -->
              <div class="absolute top-2 left-2 w-4 h-4 border-l border-t border-slate-500/40 z-10 pointer-events-none rounded-tl"></div>
              <div class="absolute top-2 right-2 w-4 h-4 border-r border-t border-slate-500/40 z-10 pointer-events-none rounded-tr"></div>
              <div class="absolute bottom-2 left-2 w-4 h-4 border-l border-b border-slate-500/40 z-10 pointer-events-none rounded-bl"></div>
              <div class="absolute bottom-2 right-2 w-4 h-4 border-r border-b border-slate-500/40 z-10 pointer-events-none rounded-br"></div>

              <!-- Video or placeholder -->
              <template v-if="!videoErrors[scene.key]">
                <video
                  :src="scene.src"
                  autoplay
                  muted
                  loop
                  playsinline
                  class="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-500"
                  @error="onVideoError(scene.key)"
                ></video>
              </template>
              <template v-else>
                <div class="w-full h-full bg-slate-900 flex flex-col items-center justify-center gap-2">
                  <div class="text-3xl opacity-25">🖼</div>
                  <span class="text-xs text-slate-600">视频待接入</span>
                  <button
                    class="mt-1 px-2 py-0.5 rounded text-xs border border-slate-700
                           text-slate-500 hover:text-slate-300 hover:border-slate-500 transition-all"
                    @click="retryVideo(scene.key)"
                  >
                    重试
                  </button>
                </div>
              </template>

              <!-- Gradient overlay -->
              <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent pointer-events-none"></div>

              <!-- Scene tag (top-right) -->
              <div class="absolute top-2 right-2 z-10">
                <span class="px-2 py-0.5 rounded-md text-xs font-mono
                             bg-slate-800/85 border border-slate-600/50 text-slate-300 backdrop-blur-sm">
                  {{ scene.tag }}
                </span>
              </div>

              <!-- Bottom: title + subtitle -->
              <div class="absolute bottom-0 left-0 right-0 p-3 z-10">
                <h3 class="text-sm font-semibold text-white leading-none mb-1">{{ scene.title }}</h3>
                <p class="text-xs text-slate-400">{{ scene.subtitle }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- SECTION 4: Feature Entry Cards -->
      <section>
        <div class="flex items-center gap-3 mb-4">
          <div class="h-px flex-1 bg-gradient-to-r from-transparent via-emerald-600/30 to-transparent"></div>
          <span class="text-xs font-mono text-emerald-500/60 tracking-widest uppercase">Modules</span>
          <div class="h-px flex-1 bg-gradient-to-r from-transparent via-emerald-600/30 to-transparent"></div>
        </div>

        <div class="grid grid-cols-3 gap-4">
          <RouterLink
            v-for="entry in featureEntries"
            :key="entry.route"
            :to="entry.route"
            class="group rounded-xl border border-slate-800 bg-slate-900/50 p-5
                   hover:border-emerald-500/50 hover:bg-slate-900/70
                   hover:shadow-[0_0_20px_rgba(16,185,129,0.08)]
                   transition-all duration-200 hover:-translate-y-0.5"
          >
            <div class="flex items-center justify-between mb-3">
              <span class="text-2xl">{{ entry.icon }}</span>
              <span
                class="text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-1
                       transition-all duration-200 text-sm"
              >&#x2192;</span>
            </div>
            <h3 class="text-sm font-semibold text-white group-hover:text-emerald-300 transition-colors mb-2">
              {{ entry.title }}
            </h3>
            <p class="text-xs text-slate-500 leading-relaxed">{{ entry.desc }}</p>
            <div
              class="h-0.5 rounded-full mt-3
                     group-hover:bg-gradient-to-r group-hover:from-emerald-500/80 group-hover:via-emerald-400/40 group-hover:to-transparent
                     transition-all duration-300"
            ></div>
          </RouterLink>
        </div>
      </section>

      <!-- Bottom padding -->
      <div class="h-4"></div>
    </div>
  </div>
</template>
