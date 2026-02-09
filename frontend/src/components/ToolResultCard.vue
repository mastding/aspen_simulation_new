<template>
  <div class="my-4 border border-slate-700 rounded-xl overflow-hidden bg-slate-900/50 shadow-inner">
    <div class="bg-slate-800 px-4 py-2 flex justify-between items-center border-b border-slate-700">
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
        <span class="text-xs font-mono text-emerald-400 font-bold uppercase tracking-tight">
          Tool Call: {{ tool.function_name }}
        </span>
      </div>
      <button @click="isCollapsed = !isCollapsed" class="text-slate-500 hover:text-white text-xs">
        {{ isCollapsed ? '展开' : '收起' }}
      </button>
    </div>

    <div v-show="!isCollapsed" class="p-4 space-y-3 font-mono text-[13px]">
      <div>
        <p class="text-slate-500 mb-1">// Arguments</p>
        <pre class="text-blue-300 whitespace-pre-wrap">{{ formatJSON(tool.args) }}</pre>
      </div>

      <div v-if="tool.result" class="pt-3 border-t border-slate-800">
        <p class="text-slate-500 mb-1">// Result Output</p>
        <pre class="text-slate-300 whitespace-pre-wrap">{{ tool.result }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
defineProps(['tool']);

const isCollapsed = ref(false);
const formatJSON = (val) => typeof val === 'string' ? val : JSON.stringify(val, null, 2);
</script>