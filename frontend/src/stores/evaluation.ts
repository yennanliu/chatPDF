import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'
import { useToast } from '@/composables/useToast'

// ── Types mirroring the backend eval API (routers/eval.py) ────────────────────

export interface GoldItem {
  id: string
  question: string
  doc_ids: string[]
  relevant_substrings: string[]
  reference_answer: string | null
}

export interface Preset {
  label: string
  overrides: Record<string, unknown>
}

export interface RetrievedChunk {
  doc_name: string
  page: number | null
  preview: string
  score: number
  relevant: boolean
}

export interface QuestionResult {
  id: string | null
  question: string
  hit: boolean
  first_relevant_rank: number | null
  mrr: number
  'ndcg@k': number
  'precision@k': number
  substring_recall: number
  latency_ms: number
  retrieved: RetrievedChunk[]
  answer: string | null
  faithfulness: number | null
  answer_relevance: number | null
  answer_correctness: number | null
  context_precision: number | null
  context_recall: number | null
}

export interface Metrics {
  'hit@k': number
  'recall@k': number
  mrr: number
  'ndcg@k': number
  'precision@k': number
  p50_latency_ms: number
  context_precision: number | null
  context_recall: number | null
  faithfulness: number | null
  answer_relevance: number | null
  answer_correctness: number | null
}

export interface VariantResult {
  label: string
  config: Record<string, unknown>
  metrics: Metrics
  per_question: QuestionResult[]
}

export interface RunResult {
  k: number
  n_questions: number
  judge_enabled: boolean
  results: VariantResult[]
  warnings: string[]
  tracing_enabled?: boolean
}

/** One variant's headline metrics, as persisted in run history. */
export interface RunSummary {
  label: string
  config: Record<string, unknown>
  metrics: Metrics
}

export interface HistoryRun {
  id: string
  created_at: string
  k: number
  n_questions: number
  judge_enabled: boolean
  summary: RunSummary[]
}

export interface TracingStatus {
  enabled: boolean
  host: string | null
}

let _seq = 0
function newId(): string {
  // Browser-unique enough for editor rows; the backend treats id as opaque.
  return `q_${Date.now().toString(36)}_${_seq++}`
}

export function blankItem(): GoldItem {
  return { id: newId(), question: '', doc_ids: [], relevant_substrings: [], reference_answer: '' }
}

export const useEvalStore = defineStore('evaluation', () => {
  const gold = ref<GoldItem[]>([])
  const presets = ref<Preset[]>([])
  const result = ref<RunResult | null>(null)
  const history = ref<HistoryRun[]>([])
  const tracing = ref<TracingStatus>({ enabled: false, host: null })
  const loadingGold = ref(false)
  const saving = ref(false)
  const running = ref(false)
  const toast = useToast()

  function _fail(e: unknown): void {
    toast.error(e instanceof Error ? e.message : String(e))
  }

  async function fetchGold(): Promise<void> {
    loadingGold.value = true
    try {
      const data = await api.get<{ items: GoldItem[] }>('/api/eval/gold')
      gold.value = data.items.map(it => ({ ...blankItem(), ...it, id: it.id || newId() }))
    } catch (e) {
      _fail(e)
    } finally {
      loadingGold.value = false
    }
  }

  async function fetchPresets(): Promise<void> {
    try {
      const data = await api.get<{ presets: Preset[] }>('/api/eval/presets')
      presets.value = data.presets
    } catch (e) {
      _fail(e)
    }
  }

  async function fetchHistory(): Promise<void> {
    try {
      const data = await api.get<{ runs: HistoryRun[] }>('/api/eval/history')
      history.value = data.runs
    } catch (e) {
      _fail(e)
    }
  }

  async function fetchTracing(): Promise<void> {
    // Best-effort: the status banner is informational, never block the page on it.
    try {
      tracing.value = await api.get<TracingStatus>('/api/eval/tracing')
    } catch { /* leave default (disabled) */ }
  }

  async function saveGold(): Promise<boolean> {
    saving.value = true
    try {
      // Drop empty rows so the persisted set stays clean.
      const items = gold.value.filter(g => g.question.trim())
      await api.putJson('/api/eval/gold', { items })
      gold.value = items
      toast.success(`Saved ${items.length} question${items.length === 1 ? '' : 's'}`)
      return true
    } catch (e) {
      _fail(e)
      return false
    } finally {
      saving.value = false
    }
  }

  interface RunOptions {
    configs: { label: string; overrides: Record<string, unknown> }[]
    k: number
    judge: { enabled: boolean }
  }

  async function runEval(opts: RunOptions): Promise<void> {
    running.value = true
    result.value = null
    try {
      // Generation + judge can take a while over many questions × configs.
      result.value = await api.postJson<RunResult>('/api/eval/run', opts, 180_000)
      if (result.value?.warnings?.length) {
        result.value.warnings.forEach(w => toast.error(w))
      }
      // Refresh the trend charts with the run just persisted server-side.
      await fetchHistory()
    } catch (e) {
      _fail(e)
    } finally {
      running.value = false
    }
  }

  return {
    gold, presets, result, history, tracing, loadingGold, saving, running,
    fetchGold, fetchPresets, fetchHistory, fetchTracing, saveGold, runEval,
  }
})
