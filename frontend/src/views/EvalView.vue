<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useEvalStore, blankItem, type VariantResult, type Metrics } from '@/stores/evaluation'
import { useDocumentsStore } from '@/stores/documents'

const evalStore = useEvalStore()
const docStore  = useDocumentsStore()

const k          = ref(5)
const judge      = ref(false)
const selected   = reactive<Record<string, boolean>>({})   // preset label → chosen
const expanded   = reactive<Record<string, boolean>>({})   // variant label → drill-down open

const indexedDocs = computed(() => docStore.documents.filter(d => d.status === 'indexed'))

onMounted(async () => {
  await Promise.all([
    evalStore.fetchGold(),
    evalStore.fetchPresets(),
    docStore.documents.length ? Promise.resolve() : docStore.fetchDocuments(),
  ])
  // Default selection: dense + hybrid α0.5 + hybrid + rerank.
  evalStore.presets.forEach((p, i) => { selected[p.label] = i !== 2 })
})

// ── Gold editor helpers ───────────────────────────────────────────────────────

function addQuestion() { evalStore.gold.push(blankItem()) }
function removeQuestion(id: string) {
  const i = evalStore.gold.findIndex(g => g.id === id)
  if (i !== -1) evalStore.gold.splice(i, 1)
}
function toggleDoc(itemId: string, docId: string) {
  const item = evalStore.gold.find(g => g.id === itemId)
  if (!item) return
  const i = item.doc_ids.indexOf(docId)
  if (i === -1) item.doc_ids.push(docId)
  else item.doc_ids.splice(i, 1)
}
/** Substrings are edited as one-per-line text; map to/from the array model. */
function substringsText(item: { relevant_substrings: string[] }): string {
  return item.relevant_substrings.join('\n')
}
function setSubstrings(item: { relevant_substrings: string[] }, val: string) {
  item.relevant_substrings = val.split('\n').map(s => s.trim()).filter(Boolean)
}

// ── Run ───────────────────────────────────────────────────────────────────────

const chosenPresets = computed(() => evalStore.presets.filter(p => selected[p.label]))
const canRun = computed(() =>
  !evalStore.running &&
  chosenPresets.value.length > 0 &&
  evalStore.gold.some(g => g.question.trim() && g.doc_ids.length),
)

async function run() {
  // Persist the gold set first so the backend evaluates exactly what's on screen.
  const ok = await evalStore.saveGold()
  if (!ok) return
  await evalStore.runEval({
    configs: chosenPresets.value.map(p => ({ label: p.label, overrides: p.overrides })),
    k: k.value,
    judge: { enabled: judge.value },
  })
}

// ── Results formatting ─────────────────────────────────────────────────────────

interface Col { key: keyof Metrics; label: string; pct?: boolean; suffix?: string; higher: boolean }
const baseCols: Col[] = [
  { key: 'hit@k',       label: 'Hit@k',     pct: true, higher: true },
  { key: 'recall@k',    label: 'Recall@k',  pct: true, higher: true },
  { key: 'mrr',         label: 'MRR',                  higher: true },
  { key: 'ndcg@k',      label: 'nDCG@k',               higher: true },
  { key: 'precision@k', label: 'Prec@k',    pct: true, higher: true },
  { key: 'p50_latency_ms', label: 'p50 lat', suffix: ' ms', higher: false },
]
const judgeCols: Col[] = [
  { key: 'faithfulness',     label: 'Faithful', pct: true, higher: true },
  { key: 'answer_relevance', label: 'Ans rel',  pct: true, higher: true },
]
const columns = computed<Col[]>(() =>
  evalStore.result?.judge_enabled ? [...baseCols, ...judgeCols] : baseCols,
)

function fmt(v: number | null, col: Col): string {
  if (v === null || v === undefined) return '—'
  if (col.suffix) return Math.round(v) + col.suffix
  if (col.pct) return (v * 100).toFixed(0) + '%'
  return v.toFixed(2)
}

/** Index of the best variant for a column, to highlight the winner. */
function bestIdx(results: VariantResult[], col: Col): number {
  let best = -1, val = col.higher ? -Infinity : Infinity
  results.forEach((r, i) => {
    const m = r.metrics[col.key]
    if (m === null || m === undefined) return
    if ((col.higher && m > val) || (!col.higher && m < val)) { val = m; best = i }
  })
  return best
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="page-eyebrow">
        <span class="eyebrow-dot" style="background:var(--brand-blue)" />
        Evaluate
      </div>
      <h1>RAG Evaluation</h1>
      <p>
        Measure retrieval quality with standard IR metrics (Hit@k, Recall@k, MRR, nDCG, Precision)
        and — optionally — answer quality with an LLM-as-judge (the RAGAs faithfulness / answer-relevance
        triad). Define a small gold set, pick which pipeline configurations to compare, and run.
      </p>
    </div>

    <!-- ── Gold set ─────────────────────────────────────────────────────────── -->
    <section class="block">
      <div class="block-head">
        <h2>1 · Gold set</h2>
        <span class="muted">Questions paired with the documents and the text snippets that contain the answer.</span>
      </div>

      <p v-if="!indexedDocs.length" class="empty-note">
        No indexed documents yet — upload PDFs on the Documents page first.
      </p>

      <div v-for="item in evalStore.gold" :key="item.id" class="card gold-card">
        <div class="gold-row">
          <input
            v-model="item.question"
            class="input"
            placeholder="Question a user might ask…"
          />
          <button class="btn btn-ghost btn-xs" title="Remove" @click="removeQuestion(item.id)">✕</button>
        </div>

        <label class="field-label">Documents in scope</label>
        <div class="doc-chips">
          <button
            v-for="d in indexedDocs"
            :key="d.doc_id"
            :class="['chip', item.doc_ids.includes(d.doc_id) ? 'chip-on' : '']"
            @click="toggleDoc(item.id, d.doc_id)"
          >{{ d.name }}</button>
        </div>

        <div class="grid-2">
          <div>
            <label class="field-label">Expected snippets <span class="muted">(one per line)</span></label>
            <textarea
              class="input mono"
              rows="3"
              :value="substringsText(item)"
              placeholder="exponential backoff&#10;max 5 retries"
              @input="setSubstrings(item, ($event.target as HTMLTextAreaElement).value)"
            />
          </div>
          <div>
            <label class="field-label">Reference answer <span class="muted">(optional)</span></label>
            <textarea v-model="item.reference_answer" class="input" rows="3" placeholder="The ideal answer…" />
          </div>
        </div>
      </div>

      <button class="btn btn-ghost btn-sm add-btn" @click="addQuestion">+ Add question</button>
    </section>

    <!-- ── Configurations ───────────────────────────────────────────────────── -->
    <section class="block">
      <div class="block-head">
        <h2>2 · Configurations to compare</h2>
        <span class="muted">Each preset is a different RAG pipeline; metrics are reported side by side.</span>
      </div>

      <div class="preset-grid">
        <label v-for="p in evalStore.presets" :key="p.label" class="preset" :class="{ on: selected[p.label] }">
          <input v-model="selected[p.label]" type="checkbox" />
          <span>{{ p.label }}</span>
        </label>
      </div>

      <div class="run-bar">
        <label class="inline-field">
          top-k
          <input v-model.number="k" type="number" min="1" max="20" class="input k-input" />
        </label>
        <label class="inline-field toggle">
          <input v-model="judge" type="checkbox" />
          Score answer quality (LLM judge)
          <span class="muted">— needs an API key, costs tokens</span>
        </label>
        <button class="btn btn-primary" :disabled="!canRun" @click="run">
          <span v-if="evalStore.running" class="spinner" />
          {{ evalStore.running ? 'Running…' : 'Run evaluation' }}
        </button>
      </div>
    </section>

    <!-- ── Results ──────────────────────────────────────────────────────────── -->
    <section v-if="evalStore.result" class="block">
      <div class="block-head">
        <h2>3 · Results</h2>
        <span class="muted">
          {{ evalStore.result.n_questions }} question{{ evalStore.result.n_questions === 1 ? '' : 's' }} ·
          k = {{ evalStore.result.k }} ·
          {{ evalStore.result.judge_enabled ? 'retrieval + generation' : 'retrieval only' }}
        </span>
      </div>

      <div v-if="evalStore.result.warnings.length" class="warn">
        <p v-for="(w, i) in evalStore.result.warnings" :key="i">⚠ {{ w }}</p>
      </div>

      <div class="table-scroll">
        <table class="metrics">
          <thead>
            <tr>
              <th class="left">Configuration</th>
              <th v-for="c in columns" :key="c.key">{{ c.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, ri) in evalStore.result.results" :key="r.label">
              <td class="left">
                <button class="link" @click="expanded[r.label] = !expanded[r.label]">
                  {{ expanded[r.label] ? '▾' : '▸' }} {{ r.label }}
                </button>
              </td>
              <td
                v-for="c in columns"
                :key="c.key"
                :class="{ best: bestIdx(evalStore.result.results, c) === ri }"
              >{{ fmt(r.metrics[c.key], c) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Per-question drill-down -->
      <template v-for="r in evalStore.result.results" :key="r.label + '-d'">
        <div v-if="expanded[r.label]" class="drill">
          <h3>{{ r.label }} — per question</h3>
          <div v-for="(q, qi) in r.per_question" :key="qi" class="qcard">
            <div class="qhead">
              <span :class="['badge', q.hit ? 'badge-indexed' : 'badge-error']">
                {{ q.hit ? `hit @${q.first_relevant_rank}` : 'miss' }}
              </span>
              <span class="qtext">{{ q.question }}</span>
              <span class="qmeta">nDCG {{ q['ndcg@k'].toFixed(2) }} · {{ Math.round(q.latency_ms) }} ms</span>
            </div>

            <div v-if="q.answer" class="answer">
              <div v-if="q.faithfulness !== null" class="answer-scores">
                faithful {{ (q.faithfulness * 100).toFixed(0) }}% ·
                relevant {{ ((q.answer_relevance ?? 0) * 100).toFixed(0) }}%
              </div>
              <p>{{ q.answer }}</p>
            </div>

            <ul class="chunks">
              <li v-for="(c, ci) in q.retrieved" :key="ci" :class="{ rel: c.relevant }">
                <span class="rank">{{ ci + 1 }}</span>
                <span class="ctext">{{ c.preview }}<span v-if="c.preview.length >= 200">…</span></span>
                <span class="cscore">{{ c.score.toFixed(2) }}</span>
              </li>
              <li v-if="!q.retrieved.length" class="muted">No chunks retrieved.</li>
            </ul>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.page { padding: 40px 36px; max-width: 1000px; }
.page-header { margin-bottom: 28px; }
.page-eyebrow {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: .75rem; font-weight: 600; letter-spacing: .07em;
  text-transform: uppercase; color: var(--brand-blue); margin-bottom: 10px;
}
.eyebrow-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.page-header h1 { margin-bottom: 8px; }
.page-header p { max-width: 70ch; }

.block { margin-bottom: 34px; }
.block-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.muted { color: var(--text-muted); font-size: .8rem; }
.empty-note { color: var(--text-muted); font-size: .875rem; margin-bottom: 12px; }

/* ── Gold editor ──────────────────────────────────────────────────────────── */
.gold-card { padding: 16px 18px; margin-bottom: 12px; }
.gold-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.gold-row .input { flex: 1; font-weight: 500; }
.field-label { display: block; font-size: .75rem; font-weight: 600; color: var(--text-muted); margin: 4px 0 6px; }
.doc-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.chip {
  padding: 4px 11px; border-radius: var(--radius-pill);
  border: 1.5px solid var(--border); background: var(--bg);
  font-size: .78rem; color: var(--text-muted); cursor: pointer;
  font-family: inherit; max-width: 220px; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
.chip-on { background: rgba(26,188,254,.12); border-color: var(--brand-blue); color: #0b7fb0; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .82rem; }
textarea.input { resize: vertical; line-height: 1.5; }
.add-btn { margin-top: 4px; }

/* ── Configurations ──────────────────────────────────────────────────────── */
.preset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; margin-bottom: 18px; }
.preset {
  display: flex; align-items: center; gap: 9px;
  padding: 11px 14px; border: 1.5px solid var(--border);
  border-radius: var(--radius-sm); cursor: pointer; font-size: .85rem; font-weight: 500;
  transition: border-color .15s, background .15s;
}
.preset.on { border-color: var(--brand-purple); background: rgba(162,89,255,.06); }
.preset input { accent-color: var(--brand-purple); }

.run-bar { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.inline-field { display: inline-flex; align-items: center; gap: 7px; font-size: .85rem; color: var(--text); }
.inline-field.toggle { gap: 8px; }
.k-input { width: 64px; padding: 6px 8px; }
.run-bar .btn-primary { margin-left: auto; }

/* ── Results table ───────────────────────────────────────────────────────── */
.table-scroll { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius-md); }
table.metrics { width: 100%; border-collapse: collapse; font-size: .85rem; }
table.metrics th, table.metrics td {
  padding: 11px 14px; text-align: right; white-space: nowrap;
  border-bottom: 1px solid var(--border);
}
table.metrics thead th { color: var(--text-muted); font-weight: 600; font-size: .76rem; text-transform: uppercase; letter-spacing: .03em; }
table.metrics tbody tr:last-child td { border-bottom: none; }
table.metrics .left { text-align: left; }
table.metrics td.best { color: #0a7a4e; font-weight: 700; background: rgba(10,207,131,.07); }
.link { background: none; border: none; cursor: pointer; color: var(--brand-purple); font-weight: 600; font-family: inherit; font-size: .85rem; padding: 0; }

.warn {
  background: rgba(245,158,11,.1); border: 1px solid rgba(245,158,11,.3);
  border-radius: var(--radius-sm); padding: 10px 14px; margin-bottom: 16px;
}
.warn p { color: #92400e; font-size: .82rem; margin: 2px 0; }

/* ── Drill-down ──────────────────────────────────────────────────────────── */
.drill { margin-top: 18px; }
.drill h3 { margin-bottom: 10px; }
.qcard { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; margin-bottom: 10px; }
.qhead { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.qtext { font-weight: 500; flex: 1; min-width: 200px; }
.qmeta { color: var(--text-muted); font-size: .76rem; }
.answer { margin: 10px 0; padding: 10px 12px; background: var(--bg-alt); border-radius: var(--radius-sm); }
.answer-scores { font-size: .76rem; color: var(--text-muted); margin-bottom: 4px; }
.answer p { color: var(--text); font-size: .85rem; margin: 0; }
.chunks { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.chunks li { display: flex; gap: 10px; align-items: baseline; font-size: .8rem; color: var(--text-muted); padding: 5px 8px; border-radius: 6px; }
.chunks li.rel { background: rgba(10,207,131,.08); color: var(--text); }
.rank { flex-shrink: 0; width: 18px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.ctext { flex: 1; }
.cscore { flex-shrink: 0; font-variant-numeric: tabular-nums; color: var(--text-muted); }

@media (max-width: 768px) {
  .page { padding: 20px 16px; }
  .grid-2 { grid-template-columns: 1fr; }
  .run-bar .btn-primary { margin-left: 0; }
}
</style>
