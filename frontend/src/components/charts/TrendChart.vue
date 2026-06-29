<script setup lang="ts">
// Dependency-free multi-line trend chart: one line per config, x = run order.
// Used to track a chosen metric across evaluation runs over time.
import { computed } from 'vue'

interface Line { label: string; color: string; points: (number | null)[] }

const props = withDefaults(defineProps<{
  lines: Line[]
  xLabels: string[]
  max?: number
  pct?: boolean
  height?: number
}>(), { max: 1, pct: true, height: 220 })

const W = 680
const PAD_L = 36, PAD_R = 12, PAD_T = 12, PAD_B = 40
const innerW = computed(() => W - PAD_L - PAD_R)
const innerH = computed(() => props.height - PAD_T - PAD_B)

const n = computed(() => props.xLabels.length)
const ticks = computed(() => [0, 0.25, 0.5, 0.75, 1].map(f => ({ f, v: f * props.max })))

function xOf(i: number) {
  if (n.value <= 1) return PAD_L + innerW.value / 2
  return PAD_L + (innerW.value * i) / (n.value - 1)
}
function yOf(v: number) { return PAD_T + innerH.value * (1 - Math.min(v / props.max, 1)) }
function fmtTick(v: number) { return props.pct ? Math.round(v * 100) + '%' : v.toFixed(1) }

/** Path through the non-null points (skips gaps). */
function pathFor(points: (number | null)[]): string {
  let d = '', pen = false
  points.forEach((v, i) => {
    if (v === null) { pen = false; return }
    d += `${pen ? 'L' : 'M'}${xOf(i).toFixed(1)} ${yOf(v).toFixed(1)} `
    pen = true
  })
  return d.trim()
}
// Show at most ~6 x-axis labels to avoid crowding.
const labelEvery = computed(() => Math.max(1, Math.ceil(n.value / 6)))
</script>

<template>
  <div class="chart-wrap">
    <svg :viewBox="`0 0 ${W} ${height}`" preserveAspectRatio="xMidYMid meet" role="img">
      <g v-for="t in ticks" :key="t.f">
        <line :x1="PAD_L" :x2="W - PAD_R" :y1="yOf(t.v)" :y2="yOf(t.v)" class="grid" />
        <text :x="PAD_L - 6" :y="yOf(t.v) + 3" class="ytick">{{ fmtTick(t.v) }}</text>
      </g>

      <g v-for="line in lines" :key="line.label">
        <path
          :d="pathFor(line.points)"
          :stroke="line.color"
          fill="none"
          stroke-width="2"
          stroke-linejoin="round"
          stroke-linecap="round"
        />
        <template v-for="(v, i) in line.points" :key="i">
          <circle v-if="v !== null" :cx="xOf(i)" :cy="yOf(v)" r="3" :fill="line.color">
            <title>{{ line.label }} · {{ xLabels[i] }}: {{ fmtTick(v) }}</title>
          </circle>
        </template>
      </g>

      <text
        v-for="(lbl, i) in xLabels"
        v-show="i % labelEvery === 0"
        :key="i"
        :x="xOf(i)"
        :y="height - PAD_B + 16"
        class="xtick"
      >{{ lbl }}</text>
    </svg>

    <div class="legend">
      <span v-for="l in lines" :key="l.label" class="legend-item">
        <span class="swatch" :style="{ background: l.color }" />{{ l.label }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.chart-wrap { width: 100%; }
svg { width: 100%; height: auto; display: block; }
.grid { stroke: var(--border); stroke-width: 1; }
.ytick { fill: var(--text-muted); font-size: 10px; text-anchor: end; font-variant-numeric: tabular-nums; }
.xtick { fill: var(--text-muted); font-size: 10px; text-anchor: middle; }
.legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; justify-content: center; }
.legend-item { display: inline-flex; align-items: center; gap: 6px; font-size: .76rem; color: var(--text-muted); }
.swatch { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
</style>
