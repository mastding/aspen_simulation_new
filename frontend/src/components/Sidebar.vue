<template>
  <aside class="w-80 bg-aspen-panel border-r border-slate-700 flex flex-col h-full overflow-hidden">
    <div class="p-5 border-b border-slate-700">
      <h1 class="text-xl font-bold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
        Aspen 智能流模拟
      </h1>
    </div>

    <div class="flex-1 overflow-y-auto p-4 space-y-6">
      <div v-for="(blocks, category) in equipmentData" :key="category">
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2">
          {{ categoryMap[category] }}
        </h3>
        <div class="grid grid-cols-1 gap-1">
          <button
            v-for="item in blocks" :key="item.id"
            @click="$emit('select-task', item.id)"
            class="flex items-center p-2.5 text-sm rounded-lg hover:bg-slate-700/50 transition-all text-slate-300 hover:text-white group"
          >
            <span class="text-lg mr-3 group-hover:scale-110 transition-transform">{{ item.icon }}</span>
            <span class="truncate">{{ item.name }}</span>
          </button>
        </div>
      </div>

      <div class="pt-4">
        <button
          @click="$emit('select-process')"
          class="w-full py-3 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-bold shadow-lg shadow-blue-900/20 transition-all active:scale-95"
        >
          ⛓️ 全流程模拟示例
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup>
defineProps(['equipmentData']);
const categoryMap = {
  simple: '常规单元',
  heat: '热交换',
  transport: '流体输送',
  tower: '塔设备',
  reactor: '反应器'
};
</script>