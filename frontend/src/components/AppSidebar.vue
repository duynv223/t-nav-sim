<script setup lang="ts">
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'
import { Car, Settings } from 'lucide-vue-next'
import { ref } from 'vue'

const emit = defineEmits<{
  (e: 'tab-change', tab: string): void
}>()

const activeTab = ref('simulation')

function selectTab(tab: string) {
  activeTab.value = tab
  emit('tab-change', tab)
}
</script>

<template>
  <Sidebar collapsible="icon" class="border-r">
    <SidebarHeader>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton size="lg">
            <div class="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-accent text-sidebar-foreground">
              <img src="/favicon.svg" alt="NavSim" class="h-5 w-5" />
            </div>
            <div class="grid flex-1 text-left text-sm leading-tight">
              <span class="truncate font-semibold">Dsim</span>
              <span class="truncate text-xs">v1.0</span>
            </div>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarHeader>
    
    <SidebarContent>
      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton 
                :is-active="activeTab === 'simulation'"
                @click="selectTab('simulation')"
                :title="'Route Simulation'"
              >
                <Car class="size-4" />
                <span>Route Simulation</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton 
                :is-active="activeTab === 'settings'"
                @click="selectTab('settings')"
                :title="'Settings'"
              >
                <Settings class="size-4" />
                <span>Settings</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>
    
    <SidebarRail />
  </Sidebar>
</template>
