<template>
  <div class="flex h-screen bg-slate-100 text-gray-800 font-sans overflow-hidden">
    <!-- 左侧菜单栏 - 可拖拽调整宽度 -->
    <div class="relative h-full" ref="sidebarResizer">
      <aside
        ref="sidebar"
        class="w-64 h-full bg-[#1e293b] border-r border-slate-700 flex flex-col shadow-xl"
        :style="{ width: sidebarWidth + 'px' }"
      >
        <div class="p-6 border-b border-slate-700">
          <h1 class="text-xl font-bold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
            Aspen AI 智能体
          </h1>
          <p class="text-[10px] text-slate-500 mt-1 uppercase tracking-widest">Chemical Simulation Next-Gen</p>
        </div>

        <div class="flex-1 overflow-y-auto p-4 custom-scrollbar">
          <!-- 主菜单项 -->
          <div class="space-y-2">
            <button
              @click="selectMenu('unit')"
              :class="[
                'w-full flex items-center p-4 text-sm rounded-xl transition-all group mb-2',
                activeMenu === 'unit'
                  ? 'bg-blue-600/30 text-blue-300 border border-blue-500/30'
                  : 'hover:bg-blue-600/20 hover:text-blue-400'
              ]"
            >
              <span class="mr-3 text-xl group-hover:scale-125 transition-transform">⚗️</span>
              <div class="flex-1 text-left">
                <div class="font-medium">单元模拟</div>
                <div class="text-xs text-slate-400 mt-1">单个设备模拟计算</div>
              </div>
            </button>

            <button
              @click="selectMenu('process')"
              :class="[
                'w-full flex items-center p-4 text-sm rounded-xl transition-all group',
                activeMenu === 'process'
                  ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/30'
                  : 'hover:bg-emerald-600/20 hover:text-emerald-400'
              ]"
            >
              <span class="mr-3 text-xl group-hover:scale-125 transition-transform">🚀</span>
              <div class="flex-1 text-left">
                <div class="font-medium">流程模拟</div>
                <div class="text-xs text-slate-400 mt-1">完整工艺流程模拟</div>
              </div>
            </button>
          </div>

          <!-- 连接状态 -->
          <div class="mt-8 p-3 bg-slate-800/50 rounded-lg">
            <div class="flex items-center gap-2">
              <div :class="wsConnected ? 'bg-emerald-500' : 'bg-red-500'"
                   class="w-2 h-2 rounded-full animate-pulse"></div>
              <span class="text-xs text-slate-300">
                {{ wsConnected ? '已连接后端服务' : '正在连接...' }}
              </span>
            </div>
            <div class="text-[10px] text-slate-500 mt-1">
              WebSocket: {{ wsConnected ? 'online' : 'offline' }}
            </div>
          </div>
        </div>
      </aside>

      <!-- 左侧菜单栏拖拽条 -->
      <div
        class="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-blue-400 active:bg-blue-500 transition-colors"
        @mousedown="startSidebarResize"
      ></div>
    </div>

    <!-- 右侧主区域 -->
    <main class="flex-1 flex flex-col min-w-0 bg-slate-100 h-full">
      <!-- 垂直布局：两个可调整高度的主要区域 -->
      <div class="flex-1 flex flex-col p-4 gap-4 overflow-hidden">
        <!-- 区域1: 智能体对话显示框 -->
        <div
          ref="chatContainer"
          class="bg-white rounded-xl shadow-md border border-slate-300 overflow-hidden flex flex-col"
          :style="{ height: chatHeight + 'px' }"
        >
          <div class="px-4 py-3 border-b border-slate-300 bg-gradient-to-r from-blue-50 to-white">
            <h2 class="font-bold text-gray-700 flex items-center gap-2">
              <span class="text-blue-600">🤖</span> 智能体对话与执行过程
              <span v-if="loading" class="text-xs font-normal text-blue-500 animate-pulse">
                (处理中...)
              </span>
            </h2>
          </div>
          <div class="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar" ref="chatBox">
            <!-- 用户消息 -->
            <div v-for="(msg, index) in messages" :key="msg.id">
              <!-- 用户消息 -->
              <div v-if="msg.type === 'user'" class="flex justify-end mb-4">
                <div class="max-w-[60%] bg-blue-600 text-white p-3 rounded-2xl rounded-tr-none shadow-lg text-xs">
                  {{ msg.content }}
                </div>
              </div>

              <!-- 思维链事件 -->
              <div v-else-if="msg.type === 'thought'" class="flex justify-start mb-4">
                <div class="max-w-[90%] w-full">
                  <div class="border border-amber-200 rounded-lg overflow-hidden shadow-sm">
                    <div
                      class="bg-amber-50 px-3 py-2 flex justify-between items-center border-b border-amber-200 cursor-pointer hover:bg-amber-100 transition-colors"
                      @click="toggleCollapse(msg.id)"
                    >
                      <div class="flex items-center gap-2">
                        <span class="text-amber-600 font-bold text-xs">🤔 思考过程</span>
                        <span class="text-[10px] text-amber-500 bg-amber-100 px-2 py-0.5 rounded-full">
                          {{ msg.collapsed ? '已折叠' : '已展开' }}
                        </span>
                      </div>
                      <span class="text-amber-600 text-xs">
                        {{ msg.collapsed ? '▼' : '▲' }}
                      </span>
                    </div>
                    <div v-if="!msg.collapsed" class="p-3">
                      <pre class="whitespace-pre-wrap text-xs text-gray-700 font-mono leading-relaxed">{{ msg.content }}</pre>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 工具调用请求 - 现在包含执行结果 -->
              <div v-else-if="msg.type === 'tool_request'" class="flex justify-start mb-4">
                <div class="max-w-[90%] w-full">
                  <div class="border border-purple-200 rounded-lg overflow-hidden shadow-sm">
                    <div
                      class="bg-purple-50 px-3 py-2 flex justify-between items-center border-b border-purple-200 cursor-pointer hover:bg-purple-100 transition-colors"
                      @click="toggleCollapse(msg.id)"
                    >
                      <div class="flex items-center gap-2">
                        <span class="text-purple-600 font-bold text-xs">🛠️ {{ msg.function_name }}</span>
                        <span class="text-[10px] text-purple-500 bg-purple-100 px-2 py-0.5 rounded-full">
                          {{ msg.collapsed ? '已折叠' : '已展开' }}
                        </span>
                        <span v-if="msg.result" class="text-[10px] text-gray-500">
                          {{ msg.is_error ? '❌ 执行失败' : '✅ 已执行' }}
                        </span>
                      </div>
                      <span class="text-purple-600 text-xs">
                        {{ msg.collapsed ? '▼' : '▲' }}
                      </span>
                    </div>
                    <div v-if="!msg.collapsed" class="p-3 space-y-3">
                      <div>
                        <div class="text-[10px] font-semibold text-blue-600 mb-1">输入参数:</div>
                        <pre class="whitespace-pre-wrap text-xs text-gray-700 bg-gray-50 p-2 rounded border border-gray-200 font-mono">{{ JSON.stringify(msg.args, null, 2) }}</pre>
                      </div>
                      <div v-if="msg.result" class="pt-2 border-t border-gray-200">
                        <div class="text-[10px] font-semibold text-emerald-600 mb-1">执行结果:</div>
                        <pre class="whitespace-pre-wrap text-xs text-gray-800 bg-white p-2 rounded border border-gray-200 font-mono max-h-60 overflow-y-auto">{{ msg.result }}</pre>

                        <!-- 文件下载区域 -->
                        <div v-if="msg.file_paths && msg.file_paths.length > 0" class="mt-2 pt-2 border-t border-gray-200">
                          <div class="text-[10px] font-semibold text-indigo-600 mb-1">生成文件:</div>
                          <div class="space-y-1">
                            <div v-for="(fileInfo, index) in msg.file_paths" :key="index"
                                 class="flex items-center justify-between bg-indigo-50 p-2 rounded border border-indigo-200">
                              <div class="flex items-center gap-2">
                                <span class="text-indigo-600 text-xs">
                                  {{ getFileIcon(fileInfo.type) }}
                                </span>
                                <div class="flex flex-col">
                                  <span class="text-xs text-gray-700">
                                    {{ getFileName(fileInfo.path) }}
                                  </span>
                                  <span class="text-[10px] text-gray-500">
                                    {{ getFileTypeName(fileInfo.type) }}
                                  </span>
                                </div>
                              </div>
                              <button
                                @click.stop="downloadFile(fileInfo.path)"
                                class="text-[10px] text-white bg-indigo-600 hover:bg-indigo-700 px-2 py-1 rounded transition-colors flex items-center gap-1"
                              >
                                <span>↓</span>
                                下载
                              </button>
                            </div>
                          </div>
                          <p class="text-[10px] text-gray-500 mt-1">
                            注：成功时会生成3个文件（流程文件、配置文件、结果文件），失败时生成1个模拟文件
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 助手最终回复 -->
              <div v-else-if="msg.type === 'assistant'" class="flex justify-start mb-4">
                <div class="max-w-[90%] w-full">
                  <div class="border border-blue-200 rounded-lg overflow-hidden shadow-sm">
                    <div
                      class="bg-blue-50 px-3 py-2 flex justify-between items-center border-b border-blue-200 cursor-pointer hover:bg-blue-100 transition-colors"
                      @click="toggleCollapse(msg.id)"
                    >
                      <div class="flex items-center gap-2">
                        <span class="text-blue-600 font-bold text-xs">🤖 智能体回复</span>
                        <span class="text-[10px] text-blue-500 bg-blue-100 px-2 py-0.5 rounded-full">
                          {{ msg.collapsed ? '已折叠' : '已展开' }}
                        </span>
                      </div>
                      <span class="text-blue-600 text-xs">
                        {{ msg.collapsed ? '▼' : '▲' }}
                      </span>
                    </div>
                    <div v-if="!msg.collapsed" class="p-4">
                      <div v-html="renderMarkdown(msg.content)" class="text-gray-800 text-sm prose-sm"></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 文件下载消息 -->
              <div v-else-if="msg.type === 'file_download'" class="flex justify-start mb-4">
                <div class="max-w-[90%] w-full">
                  <div class="border border-green-200 rounded-lg overflow-hidden shadow-sm bg-green-50">
                    <div class="px-4 py-3 border-b border-green-200">
                      <div class="flex items-center gap-2">
                        <span class="text-green-600 font-bold text-sm">📁 模拟文件下载</span>
                        <span class="text-xs text-green-500 bg-green-100 px-2 py-0.5 rounded-full">
                          {{ msg.file_paths.length }} 个文件
                        </span>
                      </div>
                    </div>
                    <div class="p-4">
                      <div class="space-y-3">
                        <div v-for="(fileInfo, index) in msg.file_paths" :key="index"
                             class="flex items-center justify-between bg-white p-3 rounded-lg border border-green-200">
                          <div class="flex items-center gap-2">
                            <span class="text-green-600 text-lg">
                              {{ getFileIcon(fileInfo.type) }}
                            </span>
                            <div>
                              <div class="text-sm font-medium text-gray-800">
                                {{ getFileName(fileInfo.path) }}
                              </div>
                              <div class="text-xs text-gray-500">
                                {{ getFileTypeName(fileInfo.type) }}
                              </div>
                            </div>
                          </div>
                          <button
                            @click.stop="downloadFile(fileInfo.path)"
                            class="text-xs text-white bg-green-600 hover:bg-green-700 px-3 py-2 rounded-lg transition-colors"
                          >
                            下载
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 加载状态 -->
            <div v-if="loading && (!messages.length || messages[messages.length-1].type === 'user')"
                 class="flex items-center gap-2 p-4 text-gray-600 text-xs">
              <span class="animate-spin">⟳</span>
              <span>🤖 智能体正在计算并操作 Aspen...</span>
            </div>
          </div>
        </div>

        <!-- 两个区域之间的拖拽条 -->
        <div
          class="h-1 bg-slate-300 hover:bg-blue-400 cursor-row-resize rounded transition-colors"
          @mousedown="startHeightResize"
        ></div>

        <!-- 区域2: 用户输入区域 -->
        <div class="bg-white rounded-xl shadow-md border border-slate-300 overflow-hidden flex flex-col" style="height: 300px;">
          <div class="px-4 py-3 border-b border-slate-300 bg-gradient-to-r from-emerald-50 to-white">
            <h2 class="font-bold text-gray-700 flex items-center gap-2">
              <span class="text-emerald-600">💬</span>
              {{ activeMenu === 'process' ? '流程模拟配置' : '单元模拟配置' }}
            </h2>
          </div>

          <div class="flex-1 overflow-y-auto p-4 custom-scrollbar">
            <!-- 单元模拟类型选择 -->
            <div v-if="activeMenu === 'unit'" class="mb-4">
              <!-- 单元类型标签 - 带小图标 -->
              <div class="flex flex-wrap gap-1 mb-3">
                <button
                  v-for="(categoryName, categoryKey) in categoryNames"
                  :key="categoryKey"
                  @click="toggleCategory(categoryKey)"
                  :class="[
                    'flex items-center px-2 py-1 text-[10px] rounded transition-all border',
                    selectedCategory === categoryKey
                      ? 'bg-blue-100 text-blue-700 border-blue-400'
                      : 'bg-gray-50 text-gray-600 border-gray-300 hover:border-blue-300 hover:text-blue-600'
                  ]"
                >
                  <span class="mr-1 text-xs">{{ getCategoryIcon(categoryKey) }}</span>
                  <span>{{ categoryName }}</span>
                </button>
              </div>

              <!-- 具体单元设备 -->
              <div v-if="selectedCategory" class="animate-fadeIn mb-3">
                <div class="flex flex-wrap gap-1">
                  <button
                    v-for="item in equipmentData[selectedCategory]"
                    :key="item.id"
                    @click="applyPrompt(item.id)"
                    :class="[
                      'px-2 py-1 text-[10px] rounded transition-all border',
                      selectedEquipment === item.id
                        ? 'bg-blue-50 text-blue-700 border-blue-400 font-medium'
                        : 'bg-gray-50 text-gray-600 border-gray-300 hover:border-blue-300 hover:text-blue-600'
                    ]"
                  >
                    {{ item.name }}
                  </button>
                </div>
              </div>
            </div>

            <!-- 流程模拟示例 -->
            <div v-if="activeMenu === 'process'" class="mb-4">
                <!-- 示例标签 - 水平排列 -->
              <div class="flex flex-wrap gap-1 mb-3">
                <button
                  v-for="(exampleName, exampleId) in processExampleNames"
                  :key="exampleId"
                  @click="applyProcessPrompt(exampleId)"
                  :class="[
                    'flex items-center px-2 py-1 text-[10px] rounded transition-all border',
                    selectedProcessExample === exampleId
                      ? 'bg-emerald-100 text-emerald-700 border-emerald-400'
                      : 'bg-gray-50 text-gray-600 border-gray-300 hover:border-emerald-300 hover:text-emerald-600'
                  ]"
                >
                  <span class="mr-1 text-xs">{{ getProcessExampleIcon(exampleId) }}</span>
                  <span>{{ exampleName }}</span>
                </button>
              </div>
            </div>

            <!-- 当前选择提示 -->
            <div v-if="selectedEquipment || (activeMenu === 'process' && selectedProcessExample)"
                 class="mb-3 p-1.5 bg-blue-50 rounded border border-blue-200">
              <div class="flex items-center justify-between">
                <div class="text-[10px] text-blue-700">
                  <span v-if="selectedEquipment">
                    <span class="font-semibold">已选择设备:</span>
                    {{ equipmentData[selectedCategory]?.find(e => e.id === selectedEquipment)?.name || selectedEquipment }}
                  </span>
                  <span v-else-if="selectedProcessExample" class="font-semibold text-emerald-700">
                    已选择流程示例: {{ processExampleNames[selectedProcessExample] }}
                  </span>
                </div>
                <button
                  v-if="selectedEquipment || selectedProcessExample"
                  @click="clearSelection"
                  class="text-[8px] text-gray-500 hover:text-red-500 hover:bg-red-50 px-1.5 py-0.5 rounded"
                >
                  取消
                </button>
              </div>
            </div>

            <!-- 输入框区域 - 字体调小 -->
            <div class="space-y-3">
              <div class="flex gap-3">
                <textarea
                  v-model="userInput"
                  @keydown.enter.prevent="sendMessage"
                  :placeholder="getPlaceholder()"
                  class="flex-1 bg-white border border-slate-300 rounded-xl p-3 text-gray-800 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none shadow-sm text-xs"
                  rows="5"
                ></textarea>

                <button
                  @click="sendMessage"
                  :disabled="!userInput || loading"
                  :class="[
                    'px-6 py-4 rounded-xl font-bold transition-all shadow-lg active:scale-95 flex items-center justify-center min-w-[100px]',
                    !userInput || loading
                      ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      : 'bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white'
                  ]"
                >
                  <span v-if="!loading" class="text-sm">发送</span>
                  <span v-else class="animate-spin">⟳</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onUnmounted } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

// --- 静态数据 (设备配置) ---
const categoryNames = {
  simple: '常规单元',
  heat: '热交换',
  transport: '流体输送',
  tower: '塔设备',
  reactor: '反应器'
};

// 获取类别图标
const getCategoryIcon = (category) => {
  const icons = {
    simple: '⚗️',
    heat: '🔥',
    transport: '🚚',
    tower: '🏗️',
    reactor: '⚡'
  };
  return icons[category] || '📁';
};

// 获取流程示例图标
const getProcessExampleIcon = (exampleId) => {
  const icons = {
    'ethylbenzene_styrene': '⚡',
    'azeotropic_distillation': '🏗️',
    'benzene_ethylene': '⚗️'
  };
  return icons[exampleId] || '📋';
};

const equipmentData = {
  simple: [
    { id: 'mixer', name: '混合器 Mixer' },
    { id: 'sep', name: '分离器 Sep' },
    { id: 'sep2', name: '分离器 Sep2' },
    { id: 'flash', name: '闪蒸罐 Flash' },
    { id: 'flash3', name: '三相闪蒸 Flash3' },
    { id: 'decanter', name: '倾析器 Decanter' },
    { id: 'fsplit', name: '分流器 FSplit' },
    { id: 'valve', name: '阀门 Valve' }
  ],
  heat: [
    { id: 'heater', name: '换热器 Heater' },
    { id: 'heatx', name: '换热器 HeatX' }
  ],
  transport: [
    { id: 'pump', name: '离心泵 Pump' },
    { id: 'compr', name: '压缩机 Compr' },
    { id: 'mcompr', name: '多级压缩机 MCompr' }
  ],
  tower: [
    { id: 'radfrac', name: '精馏塔 RadFrac' },
    { id: 'distl', name: '精馏塔 Distl' },
    { id: 'dstwu', name: '精馏塔设计 DSTWU' },
    { id: 'dupl', name: '塔器 Dupl' },
    { id: 'extract', name: '萃取塔 Extract' }
  ],
  reactor: [
    { id: 'rstoic', name: '反应器 RStoic' },
    { id: 'rplug', name: '反应器 RPlug' },
    { id: 'rcstr', name: '反应器 RCSTR' }
  ]
};

const equipmentPrompts = {
  'mixer': `将如下三股物流混合，计算混合后产品物流的温度、压力及各组分流量。物性方法采用CHAO-SEA。三股进料物流的条件如下：
FEED1：温度：100℃，压力：2 MPa；组成及流量（kmol/h）：丙烷(C3)：10，正丁烷(NC4)：15，正戊烷(NC5)：15，正己烷(NC6)：10
FEED2：温度：120℃，压力：2.5 MPa；组成及流量（kmol/h）：丙烷(C3)：15，正丁烷(NC4)：15，正戊烷(NC5)：10，正己烷(NC6)：10
FEED3：温度：100℃，气相分数：0.5；组成及流量（kmol/h）：丙烷(C3)：25，正丁烷(NC4)：0，正戊烷(NC5)：15，正己烷(NC6)：10`,

  'sep': `将一股温度 70℃，压力 0.1MPa的进料物流，分离成两股产品。进料中甲醇、水和乙醇的流量分别为50kmol/h、100kmol/h和150kmol/h。
要求分离器顶部产品流量50kmol/h，甲醇的摩尔分数0.95，乙醇的摩尔分数0.04。计算分离器底部产品的流量与组成。物性方法采用 UNIQUAC。`,

  'flash': `进料物流进入第一个闪蒸器分离成汽液两相，液相再进入第二个闪蒸器进行闪蒸分离。
已知进料温度100℃，压力3.8MPa，进料中氢气、甲烷、苯和甲苯的流量分别为185kmol/h、45kmol/h、45kmol/h 和5kmol/h。
第一个闪蒸器温度100℃，压降0；第二个闪蒸器绝热闪蒸，压力0.1MPa，计算第二个闪蒸器的温度。物性方法采用 PENG-ROB。`,

  'flash3': `使用三相闪蒸罐（Flash3）将进料分离成汽相、第一液相和第二液相三相。请给定进料条件（温度、压力、流量、组成/单位）以及闪蒸操作条件（如温度、压力或负荷等），计算三相产物的流量与组成。物性方法请指定（如 NRTL/UNIQUAC）。`,

  'heater': `软水(温度 25°C，压力 0.4MPa，流量 5000kg/h)在锅炉中被加热成 0.45MPa 的饱和蒸汽。求所需的锅炉供热量及蒸汽温度。热力学方法选择针对水(蒸汽)体系的IAPWS-95。`,

  'compr': `物流的温度100°C，压力 690kPa，用多变压缩机将该物流压缩至3450kPa，压缩机的多变效率80%，驱动机的机械效率95%。进料组分流量如下（单位为kmol/h）：
甲烷：0.05，乙烷：0.45，丙烷：4.55，正丁烷：8.60，异丁烷：9.00，1,3-丁二烯：9.00。
计算产品物流的温度和体积流量，压缩机的指示功率、轴功率以及损失的功率。物性方法采用 PENG-ROB。`,

  'mcompr': `使用多级压缩机（MCompr）将物流进行多级压缩。请给定进料条件（温度、压力、流量、组成/单位），并指定压缩级数、各级压缩比/出口压力、效率等操作条件，计算各级出口物流的温度、压力与功率。物性方法请指定（如 PENG-ROB）。`,

  'pump': `一台泵将压力 170kPa 的物流升压到 690kPa，进料温度 -10°C，进料组分流量如下（单位为kmol/h）：
甲烷：0.05，乙烷：0.45，丙烷：4.55，正丁烷：8.60，异丁烷：9.00，1,3-丁二烯：9.00
泵效率 80%，驱动机效率 95%，计算泵的有效功率（泵提供给流体的功率）、轴功率以及驱动机消耗的电功率。物性方法采用 PENG-ROB。`,

  'rstoic': `模拟甲醇制烯烃反应，只使用反应器。进料温度：180°C，压力：0.18 MPa；甲醇（CH3OH）：8000 kg/h、水蒸气（H2O）：3000 kg/h。反应器的温度为 475°C，压力为 0.15 MPa。涉及的反应及转化率如下：
R1：2CH₃OH → C₂H₄ + 2H₂O，转化率：0.25
R2：3CH₃OH → C₃H₆ + 3H₂O，转化率：0.20
R3：4CH₃OH → C₄H₈ + 4H₂O，转化率：0.08
R4：CH₃OH → CO + 2H₂，转化率：0.02
R5：CH₃OH → C + H₂O + H₂，转化率：0.005
根据给定的各反应转化率数据，计算主要产物乙烯、丙烯(别名C3H6-2)等对甲醇的选择性。物性方法选用 RK-SOAVE。`,

  'rcstr': `模拟全混釜反应器（RCSTR）中的反应过程。进料温度：100°C，压力：0.5 MPa；进料组分流量如下（单位为kmol/h）：
甲醇（CH3OH）：100，水（H2O）：50。
反应器操作条件：温度 150°C，压力 0.5 MPa，反应器体积 2 m³。涉及的反应为：
R1：CH₃OH + H₂O → CO₂ + 3H₂
使用动力学反应模型，计算反应器出口物流的组成和流量。物性方法采用 NRTL。`,

  'radfrac': `进料量是12500kg/h，温度45℃，压力101.325kPa，进料组成是乙苯0.5843（质量分数）乙苯CAS号为100-41-4，name为C8H10-4，
苯乙烯0.415（质量分数）苯乙烯CAS号为100-42-5，焦油0.0007（质量分数），焦油CAS号为629-78-7,name为C17H36。
塔顶用全凝器，压力6kPa，再沸器压力14kPa，回流比是最小回流比的1.2倍。根据纯度要求计算得出塔顶乙苯的摩尔回收率为99.91%，塔底苯乙烯的摩尔回收率为98.58%。
产品要求塔顶乙苯不低于0.99，塔底苯乙烯不低于0.997。物性方法用PENG-ROB。请使用精馏塔进行严格计算`,

  'distl': `使用精馏塔（Distl）分离二元混合物。请给定进料温度、压力、总流量及组成（注明单位），并指定塔板数、回流比/馏出与进料比等操作条件，计算塔顶与塔底产品的流量与组成。物性方法请指定（如 NRTL/UNIQUAC）。`,

  'dupl': `使用塔器单元（Dupl）进行塔器/列相关计算。请给定进料温度、压力、流量与组成（注明单位），并按需要给出塔板数、回流/再沸等关键操作参数。物性方法请指定（如 NRTL/UNIQUAC）。`,

  'extract': `使用萃取塔（Extract）进行液液萃取分离。请给定进料/溶剂等各股物流的温度、压力、总流量与组成（注明单位），指定塔板数或操作方式（如温度/负荷规范），并选择物性方法（如 NRTL/UNIQUAC）。`,

  'fsplit': `使用分流器（FSplit）将进料按指定分流比/分率拆分成多股出口物流。请给定进料条件（温度、压力、流量、组成/单位）以及各出口的分流分率或分流方式，计算各出口物流。物性方法请指定（如 NRTL/UNIQUAC）。`,

  'valve': `使用阀门（Valve）控制物流压力。请给定进料条件（温度、压力、流量、组成/单位），指定出口压力或压降，计算出口物流的温度、压力与流量。物性方法请指定（如 PENG-ROB）。`,

  'decanter': `使用倾析器（Decanter）进行液液分离。请给定进料条件（温度、压力、流量、组成/单位），指定操作温度或压力，计算两相产物的流量与组成。物性方法请指定（如 NRTL/UNIQUAC）。`,

  'sep2': `使用分离器2（Sep2）进行多产品分离。请给定进料条件（温度、压力、流量、组成/单位），指定各产品的分离要求（如流量、组成等），计算各出口产品的流量与组成。物性方法请指定（如 NRTL/UNIQUAC）。`,

  'heatx': `使用换热器（HeatX）进行两股物流的换热。请给定热物流和冷物流的进料条件（温度、压力、流量、组成/单位），指定换热要求（如热物流出口温度、冷物流出口温度、换热负荷等），计算两股出口物流的温度、压力与流量。物性方法请指定（如 PENG-ROB）。`,

  'dstwu': `使用精馏塔设计（DSTWU）进行精馏塔的初步设计。请给定进料条件（温度、压力、流量、组成/单位），指定轻关键组分和重关键组分的回收率，计算所需的理论板数、最小回流比和进料板位置。物性方法请指定（如 NRTL/UNIQUAC）。`,

  'rplug': `模拟平推流反应器（RPlug）中的反应过程。进料温度：100°C，压力：0.5 MPa；进料组分流量如下（单位为kmol/h）：
甲醇（CH3OH）：100，水（H2O）：50。
反应器操作条件：温度 150°C，压力 0.5 MPa，反应器体积 2 m³。涉及的反应为：
R1：CH₃OH + H₂O → CO₂ + 3H₂
使用动力学反应模型，计算反应器出口物流的组成和流量。物性方法采用 NRTL。`
};

// 流程模拟示例
const processExamples = {
  'ethylbenzene_styrene': `生成乙苯催化脱氢制苯乙烯的工艺流程。进料中纯乙苯，流量4815kg/h，温度为25℃，压力为0.1MPa；纯水，流量327kg/h，温度为25℃，压力为0.1MPa。要求产品苯乙烯纯度0.972。优先使用RStoic反应器。`,

  'azeotropic_distillation': `以单股混合烃为进料，组成为 n-己烷(nC6)、n-辛烷(nC8)、n-癸烷(nC10)、n-十二烷(nC12) 四组分（等摩尔 0.25/0.25/0.25/0.25），总流量 100 kmol/h；进料压力约 1.2 bar，温度100℃，进料为液相进料。
T1轻端切割塔先把最轻组分 nC6 从混合物中分出，塔顶得到高纯 nC6 产品；塔底为 nC8+nC10+nC12 的重端混合物流，作为T2进料。
T2中轻端切割塔从塔1底部物流中进一步切出第二轻组分 nC8，塔顶得到高纯 nC8 产品；塔底为 nC10+nC12 的更重混合物流，作为T3进料。
T3重端精分塔将剩余二元重端体系 nC10 与 nC12 做最终分离，塔顶得到高纯 nC10 产品；塔底得到高纯 nC12 产品。`,

  'benzene_ethylene': `含苯（BENZENE）和丙烯（PROPENE）的原料物流(FEED)进入反应器（REACTOR），经反应生成异丙苯（PRO-BEN，），反应后的混合物经冷凝器（COOLER）冷凝，再进入分离器（SEP），
分离器（SEP）顶部物流（RECYCLE）循环回反应器（REACTOR），分离器(SEP)底部物流作为产品（PRODUCT）流出，求产品(PRODUCT)中异丙苯的摩尔流量。物性方法选择 RK-SOAVE。`
};

const processExampleNames = {
  'azeotropic_distillation': '共沸精馏 - 分离精馏',
  'benzene_ethylene': '苯和乙烯反应生成异丙苯',
    'ethylbenzene_styrene': '乙苯催化脱氢制苯乙烯'
};

// --- 状态变量 ---
const userInput = ref('');
const messages = ref([]);
const loading = ref(false);
const wsConnected = ref(false);
const chatBox = ref(null);
const activeMenu = ref('unit'); // 'unit' 或 'process'
const selectedCategory = ref(null);
const selectedEquipment = ref(null);
const selectedProcessExample = ref(null);

// 拖拽相关变量
const sidebar = ref(null);
const sidebarWidth = ref(256); // 初始宽度为256px (w-64)
const chatContainer = ref(null);
const chatHeight = ref(400); // 初始高度为400px

let socket = null;
let isResizingSidebar = false;
let isResizingHeight = false;
let startX = 0;
let startWidth = 0;
let startY = 0;
let startHeight = 0;

// --- 拖拽逻辑 ---
const startSidebarResize = (e) => {
  isResizingSidebar = true;
  startX = e.clientX;
  startWidth = sidebarWidth.value;

  document.addEventListener('mousemove', handleSidebarResize);
  document.addEventListener('mouseup', stopSidebarResize);
  e.preventDefault();
};

const handleSidebarResize = (e) => {
  if (!isResizingSidebar) return;

  const deltaX = e.clientX - startX;
  let newWidth = startWidth + deltaX;

  // 限制宽度在合理范围内
  newWidth = Math.max(200, Math.min(500, newWidth));

  sidebarWidth.value = newWidth;
};

const stopSidebarResize = () => {
  isResizingSidebar = false;
  document.removeEventListener('mousemove', handleSidebarResize);
  document.removeEventListener('mouseup', stopSidebarResize);
};

const startHeightResize = (e) => {
  isResizingHeight = true;
  startY = e.clientY;
  startHeight = chatHeight.value;

  document.addEventListener('mousemove', handleHeightResize);
  document.addEventListener('mouseup', stopHeightResize);
  e.preventDefault();
};

const handleHeightResize = (e) => {
  if (!isResizingHeight) return;

  const deltaY = e.clientY - startY;
  let newHeight = startHeight + deltaY;

  // 限制高度在合理范围内
  newHeight = Math.max(200, Math.min(600, newHeight));

  chatHeight.value = newHeight;
};

const stopHeightResize = () => {
  isResizingHeight = false;
  document.removeEventListener('mousemove', handleHeightResize);
  document.removeEventListener('mouseup', stopHeightResize);
};

// 组件卸载时清理事件监听器
onUnmounted(() => {
  document.removeEventListener('mousemove', handleSidebarResize);
  document.removeEventListener('mouseup', stopSidebarResize);
  document.removeEventListener('mousemove', handleHeightResize);
  document.removeEventListener('mouseup', stopHeightResize);
});

// --- 消息ID计数器 ---
let messageIdCounter = 0;

// 创建不同消息类型的函数
const createUserMessage = (content) => {
  return {
    id: `msg_${Date.now()}_${messageIdCounter++}`,
    type: 'user',
    content: content,
    collapsed: false
  };
};

const createThoughtMessage = (thought) => {
  return {
    id: `msg_${Date.now()}_${messageIdCounter++}`,
    type: 'thought',
    content: thought,
    collapsed: false
  };
};

const createToolRequestMessage = (toolCall) => {
  return {
    id: `msg_${Date.now()}_${messageIdCounter++}`,
    type: 'tool_request',
    call_id: toolCall.id,
    function_name: toolCall.function_name,
    args: toolCall.args,
    result: '',
    file_paths: [], // 添加文件路径数组
    is_error: false,
    collapsed: false
  };
};

const createAssistantMessage = (content) => {
  return {
    id: `msg_${Date.now()}_${messageIdCounter++}`,
    type: 'assistant',
    content: content,
    collapsed: false
  };
};

// 折叠/展开切换
const toggleCollapse = (msgId) => {
  const msg = messages.value.find(m => m.id === msgId);
  if (msg) {
    msg.collapsed = !msg.collapsed;
  }
};

// 文件处理辅助函数
const getFileIcon = (fileType) => {
  const icons = {
    'aspen': '🏭',    // Aspen模拟文件
    'config': '⚙️',   // 配置文件
    'result': '📊'    // 结果文件
  };
  return icons[fileType] || '📎';
};

const getFileName = (filePath) => {
  // 提取文件名（去除路径）
  const parts = filePath.split(/[\\/]/);
  return parts[parts.length - 1];
};

const getFileTypeName = (fileType) => {
  const typeNames = {
    'aspen': 'Aspen模拟文件',
    'config': '配置文件',
    'result': '结果文件'
  };
  return typeNames[fileType] || '文件';
};

const downloadFile = async (filePath) => {
  try {
    // 对文件路径进行编码
    const encodedPath = encodeURIComponent(filePath);
    const downloadUrl = `http://localhost:8000/download?file_path=${encodedPath}`;

    // 创建隐藏的a标签触发下载
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = getFileName(filePath);
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch (error) {
    console.error('文件下载失败:', error);
    alert(`文件下载失败: ${error.message}`);
  }
};

// --- 逻辑处理 ---
const selectMenu = (menu) => {
  activeMenu.value = menu;
  selectedEquipment.value = null;
  selectedProcessExample.value = null;

  if (menu === 'process') {
    selectedCategory.value = null;
    userInput.value = '';
  }
};

const toggleCategory = (category) => {
  if (selectedCategory.value === category) {
    selectedCategory.value = null;
    selectedEquipment.value = null;
  } else {
    selectedCategory.value = category;
    selectedEquipment.value = null;
    userInput.value = '';
  }
};

const applyPrompt = (id) => {
  selectedEquipment.value = id;
  selectedProcessExample.value = null;
  userInput.value = equipmentPrompts[id] || `我想配置一个 ${id} 设备。`;
};

const applyProcessPrompt = (exampleId) => {
  selectedProcessExample.value = exampleId;
  selectedEquipment.value = null;
  userInput.value = processExamples[exampleId] || '';
};

const clearSelection = () => {
  selectedEquipment.value = null;
  selectedProcessExample.value = null;
  userInput.value = '';
};

// 获取输入框placeholder
const getPlaceholder = () => {
  if (activeMenu.value === 'process') {
    return '描述您的化工流程需求，或使用上方的流程示例...';
  } else if (selectedEquipment.value) {
    return '已选择设备示例，您可以直接使用或修改下方内容...';
  } else if (selectedCategory.value) {
    return `请选择${categoryNames[selectedCategory.value]}的具体设备...`;
  } else {
    return '请先选择单元类型...';
  }
};

const initWebSocket = () => {
  socket = new WebSocket('ws://localhost:8000/ws/chat');

  socket.onopen = () => {
    wsConnected.value = true;
    console.log("WebSocket 连接成功");
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      if (data.type === 'done') {
        loading.value = false;
        scrollToBottom();
        return;
      }

      // 处理 file_download 消息
      if (data.type === 'file_download' && data.file_paths) {
        // 创建文件下载消息
        const fileMsg = {
          id: `file_${Date.now()}_${messageIdCounter++}`,
          type: 'file_download',
          file_paths: data.file_paths
        };
        messages.value.push(fileMsg);
        scrollToBottom();
        return;  // 直接返回，不继续处理其他逻辑
      }

      // 处理思维链 - 创建独立的思维链消息
      if (data.thought && data.thought.trim()) {
        const thoughtMsg = createThoughtMessage(data.thought);
        messages.value.push(thoughtMsg);
      }

      // 处理工具调用请求 - 为每个工具调用创建独立消息
      if (data.status === 'tool_calling' && data.tool_calls && data.tool_calls.length > 0) {
        data.tool_calls.forEach(toolCall => {
          const toolMsg = createToolRequestMessage(toolCall);
          messages.value.push(toolMsg);
        });
      }

      // 处理工具执行结果 - 更新对应的工具调用消息
      if (data.status === 'tool_executed' && data.tool_results && data.tool_results.length > 0) {
        data.tool_results.forEach(toolResult => {
          // 找到对应的工具调用消息，更新其结果
          const toolMsg = messages.value.find(m =>
            m.type === 'tool_request' && m.call_id === toolResult.call_id
          );
          if (toolMsg) {
            toolMsg.result = toolResult.result;
            toolMsg.is_error = toolResult.is_error || false;
            // 如果有文件路径，添加到消息中
            if (toolResult.file_paths && Array.isArray(toolResult.file_paths)) {
              toolMsg.file_paths = toolResult.file_paths;
            }
          }
        });
      }

      // 处理助手最终回复 - 创建独立的助手消息
      if (data.content && data.content.trim()) {
        const assistantMsg = createAssistantMessage(data.content);
        messages.value.push(assistantMsg);
      }

      // 滚动到底部
      scrollToBottom();
    } catch (error) {
      console.error('解析WebSocket消息失败:', error, event.data);
    }
  };

  socket.onclose = () => {
    wsConnected.value = false;
    console.log("WebSocket 连接关闭，3秒后尝试重连...");
    setTimeout(initWebSocket, 3000);
  };

  socket.onerror = (error) => {
    console.error("WebSocket 错误:", error);
    wsConnected.value = false;
  };
};

const sendMessage = () => {
  if (!userInput.value || loading.value) return;

  const content = userInput.value;
  const userMsg = createUserMessage(content);
  messages.value.push(userMsg);

  socket.send(JSON.stringify({ message: content }));

  userInput.value = '';
  loading.value = true;
  scrollToBottom();
};

const renderMarkdown = (text) => {
  try {
    return DOMPurify.sanitize(marked.parse(text));
  } catch (error) {
    console.error('Markdown解析失败:', error);
    return text;
  }
};

const scrollToBottom = async () => {
  await nextTick();
  if (chatBox.value) {
    chatBox.value.scrollTop = chatBox.value.scrollHeight;
  }
};

onMounted(initWebSocket);
</script>

<style>
/* 自定义滚动条 */
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* 深色滚动条用于左侧菜单栏 */
aside .custom-scrollbar::-webkit-scrollbar-track { background: #1e293b; }
aside .custom-scrollbar::-webkit-scrollbar-thumb { background: #475569; }
aside .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #64748b; }

/* 动画效果 */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.animate-fadeIn {
  animation: fadeIn 0.2s ease-out;
}

/* 用户选择文本时禁止拖拽 */
* {
  user-select: none;
}

textarea, pre, .prose * {
  user-select: text;
}

/* Markdown 样式 - 使用更小的字体 */
.prose {
  font-size: 0.875rem; /* text-sm */
  line-height: 1.5;
}

.prose-sm {
  font-size: 0.75rem; /* text-xs */
  line-height: 1.4;
}

.prose table { @apply w-full border-collapse my-2 text-xs; }
.prose th { @apply bg-slate-100 border border-slate-300 p-1.5 text-left text-blue-600 text-xs; }
.prose td { @apply border border-slate-300 p-1.5 text-xs; }
.prose pre {
  @apply bg-slate-900 text-slate-100 p-2 rounded border border-slate-700 overflow-x-auto text-xs;
}
.prose code { @apply bg-blue-50 text-blue-700 px-1 py-0.5 rounded text-xs; }
.prose h1, .prose h2, .prose h3 { @apply text-gray-800 font-bold text-sm; }
.prose p { @apply text-gray-700 text-sm; }

/* 新增折叠动画 */
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
  max-height: 1000px;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}

/* 工具调用结果最大高度 */
pre.max-h-60 {
  max-height: 240px;
}

/* 文件下载按钮样式 */
.bg-indigo-50:hover {
  background-color: #e0e7ff !important;
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>