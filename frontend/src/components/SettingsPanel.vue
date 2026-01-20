<script setup lang="ts">
import { ref } from 'vue'

// Mock settings
const hereApiKey = ref('***')
const mapStyle = ref('normal.day')
</script>

<template>
  <div class="flex-1 p-6 overflow-y-auto bg-gray-50">
    <div class="max-w-2xl mx-auto">
      <h2 class="text-2xl font-bold mb-6">Settings</h2>
      
      <div class="bg-white rounded-lg shadow p-6 space-y-6">
        <!-- Map Settings -->
        <div>
          <h3 class="text-lg font-semibold mb-4 border-b pb-2">Map Configuration</h3>
          
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">
                HERE Maps API Key
              </label>
              <input 
                v-model="hereApiKey"
                type="password" 
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter your HERE API key"
              />
              <p class="text-xs text-gray-500 mt-1">
                Get your free API key at <a href="https://developer.here.com/" target="_blank" class="text-blue-600 hover:underline">developer.here.com</a>
              </p>
            </div>
          </div>
        </div>

        <!-- Map Settings -->
        <div>
          <h3 class="text-lg font-semibold mb-4 border-b pb-2">Map</h3>
          
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">
                Map Style
              </label>
              <select 
                v-model="mapStyle"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="normal.day">Normal Day</option>
                <option value="normal.night">Normal Night</option>
                <option value="satellite.day">Satellite</option>
                <option value="terrain.day">Terrain</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex gap-3 pt-4 border-t">
          <button class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors">
            Save Changes
          </button>
          <button class="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors">
            Reset to Defaults
          </button>
        </div>
      </div>

      <!-- Info Section -->
      <div class="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 class="font-semibold text-blue-900 mb-2">💡 About</h4>
        <p class="text-sm text-blue-800">
          This is the <strong>Settings workspace</strong> - a separate app from the Simulation workspace.
          Each tab in the sidebar represents a different workspace/application.
        </p>
      </div>
    </div>
  </div>
</template>
