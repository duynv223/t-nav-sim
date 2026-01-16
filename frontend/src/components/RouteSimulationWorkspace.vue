<script setup lang="ts">
import { Route } from '@/types/route'
import RouteControlPanel from './RouteControlPanel.vue'
import MapView from './MapView.vue'

defineProps<{
  route: Route
  mode: 'view' | 'add'
  telemetry: any
  simState: 'idle' | 'running' | 'paused' | 'stopped'
  simStatus: { stage: string; detail?: string } | null
  onModeChange: (mode: 'view' | 'add') => void
  onReset: () => void
  onRun: () => void
  onRunFromSegment: () => void
  onStop: () => void
  onSelectWaypoint: (idx: number) => void
  onSelectSegment: (idx: number) => void
  onFocusStart: () => void
  onSplitSegment: () => void
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
      :telemetry="telemetry"
      :simState="simState"
      :simStatus="simStatus"
      :onModeChange="onModeChange"
      :onReset="onReset"
      :onRun="onRun"
      :onRunFromSegment="onRunFromSegment"
      :onStop="onStop"
      :onSelectWaypoint="onSelectWaypoint"
      :onSelectSegment="onSelectSegment"
      :onFocusStart="onFocusStart"
      :onSplitSegment="onSplitSegment"
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
        :telemetry="telemetry"
      />
    </div>
  </div>
</template>
