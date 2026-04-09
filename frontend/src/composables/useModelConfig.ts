/**
 * Skyline — useModelConfig composable
 * Manages model selection, capabilities fetching, and dynamic configuration rendering.
 * 
 * This is the core logic that drives the "model capability driven UI" pattern.
 * 
 * Usage:
 * ```ts
 * const {
 *   selectedModelId,
 *   currentCapabilities,
 *   isLoading,
 *   promptInput,
 *   selectedClasses,
 *   modelInfo,
 *   selectModel,
 *   getActiveClasses,
 *   isOpenVocabModel,
 * } = useModelConfig()
 * ```
 */
import { ref, computed, watch } from 'vue'
import { listModels, getModelCapabilities } from '@/api/models'
import type { 
  ModelCapabilities, 
  ModelListItem, 
  ModelType,
  VideoFrame 
} from '@/types/skyline'

// Quick chip definitions for open-vocabulary models
export const QUICK_CHIPS = [
  { label: '汽车',   en: 'car' },
  { label: '行人',   en: 'person' },
  { label: '无人机', en: 'drone' },
  { label: '卡车',   en: 'truck' },
  { label: '摩托车', en: 'motorcycle' },
  { label: '船只',   en: 'boat' },
  { label: '背包',   en: 'backpack' },
] as const

export function useModelConfig(defaultModelId: string = 'YOLO-World-V2') {
  // ── State ────────────────────────────────────────────────────────────────────

  /** List of available models fetched from backend */
  const modelList = ref<ModelListItem[]>([])
  
  /** Currently selected model ID */
  const selectedModelId = ref<string>(defaultModelId)
  
  /** Capabilities for the currently selected model */
  const currentCapabilities = ref<ModelCapabilities | null>(null)
  
  /** Loading state when fetching capabilities */
  const isLoading = ref<boolean>(false)
  
  /** Error message if capability fetch fails */
  const fetchError = ref<string | null>(null)

  // ── Open-vocabulary model state ───────────────────────────────────────────────

  /** Prompt input for open-vocabulary models (YOLO-World) */
  const promptInput = ref<string>('car, person, drone')

  // ── Closed-set model state ───────────────────────────────────────────────────

  /** Selected classes for closed-set models (YOLOv8) - used for filtering */
  const selectedClasses = ref<Set<string>>(new Set())

  // ── Computed ─────────────────────────────────────────────────────────────────

  /** Whether the currently selected model is open-vocabulary */
  const isOpenVocabModel = computed<boolean>(() => {
    return currentCapabilities.value?.model_type === 'open_vocab'
  })

  /** Whether the currently selected model is closed-set */
  const isClosedSetModel = computed<boolean>(() => {
    return currentCapabilities.value?.model_type === 'closed_set'
  })

  /** Whether the current model supports class filtering */
  const supportsClassFilter = computed<boolean>(() => {
    return currentCapabilities.value?.class_filter_enabled ?? false
  })

  /** Whether the current model supports custom prompts */
  const supportsPrompt = computed<boolean>(() => {
    return currentCapabilities.value?.supports_prompt ?? false
  })

  /** Parsed target classes from prompt input */
  const targetClasses = computed<string[]>(() => {
    return promptInput.value
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
  })

  /** Get the active classes to send to backend based on model type */
  const getActiveClasses = computed<{ promptClasses: string[], selectedClasses: string[] }>(() => {
    if (isOpenVocabModel.value) {
      // For open-vocab models: use prompt input as detection targets
      return {
        promptClasses: targetClasses.value,
        selectedClasses: [],
      }
    } else {
      // For closed-set models: use selected classes for filtering
      return {
        promptClasses: [],
        selectedClasses: Array.from(selectedClasses.value),
      }
    }
  })

  /** Model display info for UI */
  const modelInfo = computed<{
    name: string
    type: ModelType
    typeLabel: string
    description: string
    supportsCustomClasses: boolean
  }>(() => {
    const caps = currentCapabilities.value
    const listItem = modelList.value.find(m => m.model_id === selectedModelId.value)
    
    return {
      name: caps?.display_name ?? listItem?.display_name ?? selectedModelId.value,
      type: (caps?.model_type ?? listItem?.model_type ?? 'open_vocab') as ModelType,
      typeLabel: (caps?.model_type ?? listItem?.model_type) === 'open_vocab' ? '开放词汇检测' : '固定类别检测',
      description: caps?.description ?? listItem?.description ?? '',
      supportsCustomClasses: caps?.supports_prompt ?? false,
    }
  })

  // ── Methods ───────────────────────────────────────────────────────────────────

  /** Fetch available models from backend */
  async function fetchModelList() {
    try {
      const response = await listModels()
      modelList.value = response.models
    } catch (e) {
      console.error('[useModelConfig] Failed to fetch model list:', e)
    }
  }

  /** Fetch capabilities for a specific model */
  async function fetchCapabilities(modelId: string): Promise<ModelCapabilities | null> {
    isLoading.value = true
    fetchError.value = null
    try {
      const caps = await getModelCapabilities(modelId)
      currentCapabilities.value = caps
      return caps
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      fetchError.value = `无法加载模型能力: ${msg}`
      console.error('[useModelConfig] Failed to fetch capabilities for', modelId, e)
      return null
    } finally {
      isLoading.value = false
    }
  }

  /** Select a model and fetch its capabilities, optionally executing a callback after load */
  async function selectModel(modelId: string, postLoadAction?: () => void) {
    if (modelId === selectedModelId.value && currentCapabilities.value) {
      postLoadAction?.()
      return // Already selected, no need to refetch
    }
    
    selectedModelId.value = modelId
    await fetchCapabilities(modelId)
    
    // Handle state cleanup when switching models
    handleModelSwitch()
    postLoadAction?.()
  }

  /** Handle state cleanup when switching between models */
  function handleModelSwitch() {
    const caps = currentCapabilities.value
    if (!caps) return

    if (caps.model_type === 'open_vocab') {
      // Switching to open-vocab: clear selected classes (not applicable)
      selectedClasses.value = new Set()
    } else {
      // Switching to closed-set: filter out incompatible selected classes
      const supportedLower = new Set(caps.supported_classes.map(c => c.toLowerCase()))
      const validSelections = Array.from(selectedClasses.value)
        .filter(cls => supportedLower.has(cls.toLowerCase()))
      selectedClasses.value = new Set(validSelections)
      
      // Clear prompt input for closed-set models
      // (but don't clear completely - keep for when user switches back)
    }
  }

  /** Toggle a class selection for closed-set models */
  function toggleClass(className: string) {
    if (selectedClasses.value.has(className)) {
      selectedClasses.value.delete(className)
    } else {
      selectedClasses.value.add(className)
    }
    // Trigger reactivity
    selectedClasses.value = new Set(selectedClasses.value)
  }

  /** Select all classes for closed-set models */
  function selectAllClasses() {
    if (currentCapabilities.value?.supported_classes) {
      selectedClasses.value = new Set(currentCapabilities.value.supported_classes)
    }
  }

  /** Clear all selected classes for closed-set models */
  function clearAllClasses() {
    selectedClasses.value = new Set()
  }

  /** Add a chip class to prompt input for open-vocab models */
  function appendChip(en: string) {
    const existing = targetClasses.value
    if (!existing.includes(en)) {
      promptInput.value = existing.length 
        ? existing.join(', ') + ', ' + en 
        : en
    }
  }

  /** Build the detection_model object for saving to history */
  function buildModelConfig() {
    return {
      model_id: selectedModelId.value,
      display_name: modelInfo.value.name,
      model_type: modelInfo.value.type,
      prompt_classes: isOpenVocabModel.value ? targetClasses.value : [],
      selected_classes: isClosedSetModel.value ? Array.from(selectedClasses.value) : [],
    }
  }

  /** Build VideoFrame payload with correct fields based on model type */
  function buildVideoFramePayload(frame: Omit<VideoFrame, 'model_id' | 'prompt_classes' | 'selected_classes'>): VideoFrame {
    const active = getActiveClasses.value
    
    return {
      ...frame,
      model_id: selectedModelId.value,
      prompt_classes: active.promptClasses,
      selected_classes: active.selectedClasses,
      // Legacy fields for backward compatibility
      selected_model: selectedModelId.value,
      target_classes: active.promptClasses,
    }
  }

  // ── Initialization ───────────────────────────────────────────────────────────

  /** Initialize by fetching model list and capabilities for default model */
  async function initialize() {
    await fetchModelList()
    await fetchCapabilities(selectedModelId.value)
  }

  // Watch for model ID changes to refetch capabilities
  watch(selectedModelId, async (newId) => {
    // Skip if already have capabilities for this model
    if (currentCapabilities.value?.model_id !== newId) {
      await fetchCapabilities(newId)
      handleModelSwitch()
    }
  })

  return {
    // State
    modelList,
    selectedModelId,
    currentCapabilities,
    isLoading,
    fetchError,
    
    // Open-vocab state
    promptInput,
    targetClasses,
    
    // Closed-set state
    selectedClasses,
    
    // Computed
    isOpenVocabModel,
    isClosedSetModel,
    supportsClassFilter,
    supportsPrompt,
    getActiveClasses,
    modelInfo,
    
    // Methods
    fetchModelList,
    fetchCapabilities,
    selectModel,
    toggleClass,
    selectAllClasses,
    clearAllClasses,
    appendChip,
    buildModelConfig,
    buildVideoFramePayload,
    initialize,
  }
}
