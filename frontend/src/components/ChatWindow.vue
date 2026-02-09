<template>
  <div class="flex-1 overflow-y-auto p-6 space-y-8 scroll-smooth" ref="scrollContainer">
    <div v-for="(msg, index) in messages" :key="index"
         :class="msg.role === 'user' ? 'flex flex-col items-end' : 'flex flex-col items-start'">

      <div v-if="msg.role === 'user'"
           class="bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-tr-none max-w-[80%] shadow-lg transition-all hover:bg-blue-500">
        {{ msg.content }}
      </div>

      <div v-else class="w-full max-w-[95%]">
        <div v-if="msg.thought" class="mb-4 ml-2">
          <div @click="msg.isThoughtExpanded = !msg.isThoughtExpanded"
               class="flex items-center gap-2 cursor-pointer text-amber-500/80 hover:text-amber-400 transition-colors">
            <span class="text-[10px] font-black tracking-widest uppercase">Thinking Process</span>
            <div class="h-[1px] flex-1 bg-amber-500/20"></div>
            <span class="text-xs">{{ msg.isThoughtExpanded ? '收起' : '展开' }}</span>
          </div>

          <div v-show="msg.isThoughtExpanded !== false"
               class="mt-2 pl-4 border-l-2 border-amber-500/30 text-slate-400 text-sm leading-relaxed italic whitespace-pre-wrap">
            {{ msg.thought }}
          </div>
        </div>

        <div v-if="msg.tool_calls && msg.tool_calls.length > 0" class="space-y-3 mb-4">
          <ToolResultCard
            v-for="tool in msg.tool_calls"
            :key="tool.id"
            :tool="tool"
          />
        </div>

        <div v-if="msg.content"
             class="bg-slate-800/50 p-6 rounded-2xl rounded-tl-none border border-slate-700 shadow-xl relative group">
          <div class="prose prose-invert prose-blue max-w-none text-slate-200"
               v-html="renderMarkdown(msg.content)">
          </div>

          <div v-if="detectFiles(msg.content)" class="mt-6 flex flex-wrap gap-3 border-t border-slate-700/50 pt-4">
            <button
              v-for="file in extractFiles(msg.content)" :key="file"
              @click="$emit('download-file', file)"
              class="flex items-center gap-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-4 py-2 rounded-xl text-xs font-bold transition-all active:scale-95"
            >
              <span class="text-base">📊</span> 下载结果文件: {{ file }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="flex items-center gap-3 p-4 text-slate-500 italic text-sm">
      <div class="flex gap-1">
        <div class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
        <div class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
        <div class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce"></div>
      </div>
      <span>Aspen 智能体正在执行深度模拟...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import ToolResultCard from './ToolResultCard.vue';

const props = defineProps({
  messages: Array,
  loading: Boolean
});

const scrollContainer = ref(null);

// 自动滚动到底部
const scrollToBottom = async () => {
  await nextTick();
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight;
  }
};

// 监听消息变化触发滚动
watch(() => props.messages, scrollToBottom, { deep: true });
watch(() => props.loading, (newVal) => { if (newVal) scrollToBottom(); });

// 安全渲染 Markdown
const renderMarkdown = (text) => {
  if (!text) return '';
  const rawHtml = marked.parse(text);
  return DOMPurify.sanitize(rawHtml);
};

// 辅助功能：从文本中检测并提取生成的文件名（假设后端在返回中提到了文件名）
const detectFiles = (text) => {
  return text.includes('.xlsx') || text.includes('.json') || text.includes('.bkp');
};

const extractFiles = (text) => {
  const regex = /[\w\d\-\.]+\.(xlsx|json|bkp|csv)/gi;
  const matches = text.match(regex);
  return matches ? [...new Set(matches)] : [];
};
</script>

<style scoped>
/* 针对 Markdown 内部代码块的微调 */
:deep(.prose pre) {
  @apply bg-slate-950 border border-slate-800 rounded-lg p-4 my-4 overflow-x-auto;
}
:deep(.prose code) {
  @apply text-blue-400 bg-slate-900 px-1.5 py-0.5 rounded font-mono text-sm;
}
:deep(.prose table) {
  @apply w-full text-sm border-collapse my-4;
}
:deep(.prose th) {
  @apply bg-slate-900 border border-slate-700 p-2 text-left text-slate-400;
}
:deep(.prose td) {
  @apply border border-slate-700 p-2;
}
</style>