<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { AppSettings } from '@/types/settings'

const apiBaseUrl = import.meta.env.VITE_SIM_API_URL || 'http://localhost:8000'

const loading = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

const settings = reactive<AppSettings>(defaultSettings())

function defaultSettings(): AppSettings {
  return {
    iq_generator: {
      iq_bits: 8,
      iq_sample_rate_hz: 2600000
    },
    gps_transmitter: {
      center_freq_hz: 1575420000,
      sample_rate_hz: 2600000,
      txvga_gain: 40,
      amp_enabled: true
    },
    controller: {
      port: 'COM4'
    }
  }
}

function applySettings(value: AppSettings) {
  if (!value) return
  if (value.iq_generator) {
    Object.assign(settings.iq_generator, value.iq_generator)
  }
  if (value.gps_transmitter) {
    Object.assign(settings.gps_transmitter, value.gps_transmitter)
  }
  if (value.controller) {
    Object.assign(settings.controller, value.controller)
  }
}

async function loadSettings() {
  loading.value = true
  error.value = null
  success.value = null
  try {
    const response = await fetch(`${apiBaseUrl}/settings`)
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || 'Failed to load settings')
    }
    const data = await response.json()
    applySettings(data)
  } catch (err: any) {
    error.value = err?.message || 'Failed to load settings'
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  loading.value = true
  error.value = null
  success.value = null
  try {
    const payload = JSON.parse(JSON.stringify(settings))
    const response = await fetch(`${apiBaseUrl}/settings`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || 'Failed to save settings')
    }
    const data = await response.json()
    applySettings(data)
    success.value = 'Settings saved'
  } catch (err: any) {
    error.value = err?.message || 'Failed to save settings'
  } finally {
    loading.value = false
  }
}

function resetDefaults() {
  const defaults = defaultSettings()
  applySettings(defaults)
  error.value = null
  success.value = null
}

onMounted(() => {
  loadSettings()
})
</script>

<template>
  <div class="flex-1 p-6 overflow-y-auto bg-gray-50">
    <div class="max-w-3xl mx-auto">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold">Settings</h2>
        <span v-if="loading" class="text-xs text-gray-500">Loading...</span>
      </div>

      <div class="bg-white rounded-lg shadow p-6 space-y-6">
        <div class="space-y-4">
          <div class="border border-gray-200 rounded-md p-4">
            <h4 class="text-sm font-semibold text-gray-800 mb-3">IQ Generator</h4>
            <div class="grid grid-cols-1 gap-3 text-xs">
              <div class="grid grid-cols-2 gap-3">
                <label class="flex flex-col gap-1">
                  <span class="text-gray-600">IQ bits</span>
                  <input
                    v-model.number="settings.iq_generator.iq_bits"
                    type="number"
                    min="1"
                    step="1"
                    class="w-full px-2 py-1 border border-gray-300 rounded"
                  />
                </label>
                  <label class="flex flex-col gap-1">
                    <span class="text-gray-600">IQ sample rate (Hz)</span>
                    <input
                      v-model.number="settings.iq_generator.iq_sample_rate_hz"
                    type="number"
                    min="1"
                    step="1"
                    class="w-full px-2 py-1 border border-gray-300 rounded"
                  />
                </label>
              </div>
            </div>
          </div>

          <div class="border border-gray-200 rounded-md p-4">
            <h4 class="text-sm font-semibold text-gray-800 mb-3">GPS Transmitter</h4>
            <div class="grid grid-cols-1 gap-3 text-xs">
              <div class="grid grid-cols-2 gap-3">
                <label class="flex flex-col gap-1">
                  <span class="text-gray-600">Center freq (Hz)</span>
                  <input
                    v-model.number="settings.gps_transmitter.center_freq_hz"
                    type="number"
                    step="1"
                    min="0"
                    class="w-full px-2 py-1 border border-gray-300 rounded"
                  />
                </label>
                <label class="flex flex-col gap-1">
                  <span class="text-gray-600">Sample rate (Hz)</span>
                  <input
                    v-model.number="settings.gps_transmitter.sample_rate_hz"
                    type="number"
                    step="1"
                    min="0"
                    class="w-full px-2 py-1 border border-gray-300 rounded"
                  />
                </label>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <label class="flex flex-col gap-1">
                  <span class="text-gray-600">TXVGA gain</span>
                  <input
                    v-model.number="settings.gps_transmitter.txvga_gain"
                    type="number"
                    step="1"
                    min="0"
                    max="47"
                    class="w-full px-2 py-1 border border-gray-300 rounded"
                  />
                </label>
                <label class="flex items-center gap-2 mt-5">
                  <input
                    v-model="settings.gps_transmitter.amp_enabled"
                    type="checkbox"
                    class="h-4 w-4 text-blue-600 border-gray-300 rounded"
                  />
                    <span class="text-gray-700">Amp enabled</span>
                  </label>
                </div>
            </div>
          </div>

          <div class="border border-gray-200 rounded-md p-4">
            <h4 class="text-sm font-semibold text-gray-800 mb-3">Controller</h4>
            <div class="grid grid-cols-1 gap-3 text-xs">
              <label class="flex flex-col gap-1">
                <span class="text-gray-600">Port</span>
                <input
                  v-model="settings.controller.port"
                  type="text"
                  class="w-full px-2 py-1 border border-gray-300 rounded"
                />
              </label>
            </div>
          </div>
        </div>

        <div class="flex flex-col gap-2 border-t pt-4">
          <div v-if="error" class="text-xs text-red-600">{{ error }}</div>
          <div v-if="success" class="text-xs text-green-600">{{ success }}</div>
          <div class="flex gap-3">
            <button
              @click="saveSettings"
              :disabled="loading"
              class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Save Settings
            </button>
            <button
              @click="loadSettings"
              :disabled="loading"
              class="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors text-sm disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Reload
            </button>
            <button
              @click="resetDefaults"
              :disabled="loading"
              class="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors text-sm disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Reset to defaults
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

