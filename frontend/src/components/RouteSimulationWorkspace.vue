<script setup lang="ts">
import { Route } from '@/types/route'
import RouteControlPanel from './RouteControlPanel.vue'
import MapView from './MapView.vue'

defineProps<{
  route: Route
  mode: 'view' | 'add'
  live: any
  simState: 'idle' | 'running' | 'paused' | 'stopped'
  simStatus: { stage: string; detail?: string } | null
  simMode: 'demo' | 'live'
  speedMultiplier: number
  onModeChange: (mode: 'view' | 'add') => void
  onSimModeChange: (simMode: 'demo' | 'live') => void
  onSpeedMultiplierChange: (multiplier: number) => void
  onReset: () => void
  onRun: () => void
  onRunFromSegment: () => void
  onStop: () => void
  onSelectWaypoint: (idx: number) => void
  onSelectSegment: (idx: number) => void
  onFocusStart: () => void
  onAddWaypoint: (p: { lat: number; lon: number }) => void
  onDeleteWaypoint: (idx: number) => void
  onMoveWaypoint: (idx: number, p: { lat: number; lon: number }) => void
}>()
</script>

<template>
  <div class="flex-1 flex">
    <!-- Route Control Panel -->
    <RouteControlPanel 
      :route="route"
      :mode="mode"
      :live="live"
      :simState="simState"
      :simStatus="simStatus"
      :simMode="simMode"
      :speedMultiplier="speedMultiplier"
      :onModeChange="onModeChange"
      :onSimModeChange="onSimModeChange"
      :onSpeedMultiplierChange="onSpeedMultiplierChange"
      :onReset="onReset"
      :onRun="onRun"
      :onRunFromSegment="onRunFromSegment"
      :onStop="onStop"
      :onSelectWaypoint="onSelectWaypoint"
      :onSelectSegment="onSelectSegment"
      :onFocusStart="onFocusStart"
    />
    
    <!-- Map Area -->
    <div class="flex-1 relative">
      <MapView
        :mode="mode"
        :onAddWaypoint="onAddWaypoint"
        :onDeleteWaypoint="onDeleteWaypoint"
        :onMoveWaypoint="onMoveWaypoint"
        :onSelectWaypoint="onSelectWaypoint"
        :onSelectSegment="onSelectSegment"
        :route="route"
        :live="live"
      />
    </div>
  </div>
</template>
