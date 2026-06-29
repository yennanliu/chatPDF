<script setup lang="ts">
// Dependency-free grouped bar chart (one group per metric, one bar per config).
// Pure SVG so the bundle stays light and there's nothing to keep up to date.
import { computed } from 'vue'

interface Series { label: string; color: string }
interface Group { label: string; values: (number | null)[] }  // values align to series order

const props = withDefaults(defineProps<{
  series: Series[]
  groups: Group[]
  max?: number
  pct?: boolean
  height?: number
}>(), { max: 1, pct: true, height: 210 })

const W = 680
const PAD_L = 36, PAD_R = 10, PAD_T = 12, PAD_B = 46
const innerW = computed(() => W - PAD_L - PAD_R)
const innerH = computed(() => props.height - PAD_T - PAD_B)

const groupW = computed(() => innerW.value / Math.max(props.groups.length, 1))
const barW = computed(() => (groupW.value * 0.72) / Math.max(props.series.length, 1))

const ticks = computed(() => [0, 0.25, 0.5, 0.75, 1].map(f => ({ f, v: f * props.max })))
function yOf(v: number) { return PAD_T + innerH.value * (1 - Math.min(v / props.max, 1)) }
function fmtTick(v: number) { return props.pct ? Math.round(v * 100) + '%' : v.toFixed(1) }
function groupX(gi: number) { return PAD_L + gi * groupW.value }
function barX(gi: number, si: number) {
  const groupInner = barW.value * props.series.length
  const start = groupX(gi) + (groupW.value - groupInner) / 2
  return start + si * barW.value
}
</script>

<template>
  <div class="chart-wrap">
    <svg :viewBox="`0 0 ${W} ${height}`" preserveAspectRatio="xMidYMid meet" role="img">
      <!-- gridlines + y labels -->
      <g v-for="t in ticks" :key="t.f">
        <line :x1="PAD_L" :x2="W - PAD_R" :y1="yOf(t.v)" :y2="yOf(t.v)" class="grid" />
        <text :x="PAD_L - 6" :y="yOf(t.v) + 3" class="ytick">{{ fmtTick(t.v) }}</text>
      </g>

      <!-- bars -->
      <g v-for="(g, gi) in groups" :key="g.label">
        <template v-for="(v, si) in g.values" :key="si">
          <rect
            v-if="v !== null"
            :x="barX(gi, si)"
            :y="yOf(v)"
            :width="Math.max(barW - 2, 1)"
            :height="Math.max(yOf(0) - yOf(v), 0)"
            :fill="series[si]?.color"
            rx="2"
          >
            <title>{{ series[si]?.label }} · {{ g.label }}: {{ fmtTick(v) }}</title>
          </rect>
        </template>
        <text :x="groupX(gi) + groupW / 2" :y="height - PAD_B + 16" class="xtick">{{ g.label }}</text>
      </g>
    </svg>

    <div class="legend">
      <span v-for="s in series" :key="s.label" class="legend-item">
        <span class="swatch" :style="{ background: s.color }" />{{ s.label }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.chart-wrap { width: 100%; }
svg { width: 100%; height: auto; display: block; }
.grid { stroke: var(--border); stroke-width: 1; }
.ytick { fill: var(--text-muted); font-size: 10px; text-anchor: end; font-variant-numeric: tabular-nums; }
.xtick { fill: var(--text-muted); font-size: 10.5px; text-anchor: middle; }
.legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; justify-content: center; }
.legend-item { display: inline-flex; align-items: center; gap: 6px; font-size: .76rem; color: var(--text-muted); }
.swatch { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
</style>
