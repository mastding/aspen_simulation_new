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
            <div v-for="(msg, index) in messages" :key="index"
                 :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">

              <!-- 用户消息 - 字体调小 -->
              <div v-if="msg.role === 'user'"
                   class="max-w-[70%] bg-blue-600 text-white p-3 rounded-2xl rounded-tr-none shadow-lg text-sm">
                {{ msg.content }}
              </div>

              <div v-else class="max-w-[90%] w-full space-y-4">
                <!-- 思考过程 - 字体调小 -->
                <div v-if="msg.thought"
                     class="ml-4 pl-4 border-l-2 border-amber-500/40 italic text-gray-600 text-xs bg-amber-50 p-2 rounded-r">
                  <span class="text-amber-700 font-bold not-italic text-[10px] block mb-1">
                    🤔 思考过程 (THOUGHT)
                  </span>
                  <div class="text-xs">{{ msg.thought }}</div>
                </div>

                <!-- 工具调用 - 字体调小 -->
                <div v-for="(tool, tIdx) in msg.tool_calls" :key="tIdx"
                     class="bg-gray-50 border border-gray-300 rounded-xl overflow-hidden shadow-sm">
                  <div class="bg-gray-100 px-3 py-2 flex justify-between items-center border-b border-gray-300">
                    <span class="text-[10px] font-mono text-emerald-600 font-bold">
                      🛠️ 工具调用: {{ tool.function_name }}
                    </span>
                  </div>
                  <div class="p-3 text-[10px] font-mono space-y-2">
                    <div class="text-blue-600">
                      >> 输入参数:
                      <pre class="whitespace-pre-wrap mt-1 text-gray-700 bg-gray-100 p-2 rounded text-[10px]">{{ JSON.stringify(tool.args, null, 2) }}</pre>
                    </div>
                    <div v-if="tool.result" class="text-gray-600 pt-2 border-t border-gray-300">
                      >> 执行结果:
                      <pre class="whitespace-pre-wrap mt-1 text-gray-800 bg-gray-50 p-2 rounded text-[10px]">{{ tool.result }}</pre>
                    </div>
                  </div>
                </div>

                <!-- AI回复内容 - 字体调小 -->
                <div v-if="msg.content"
                     class="bg-gradient-to-r from-blue-50 to-white p-4 rounded-2xl rounded-tl-none border border-blue-200 shadow-sm">
                  <div v-html="renderMarkdown(msg.content)" class="text-gray-800 text-sm prose-sm"></div>
                </div>
              </div>
            </div>

            <!-- 加载状态 - 字体调小 -->
            <div v-if="loading" class="flex items-center gap-2 p-4 text-gray-600 text-xs">
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
              <div class="p-2 bg-emerald-50 rounded-lg border border-emerald-200">
                <div class="flex items-center justify-between mb-1">
                  <h3 class="text-xs font-medium text-emerald-700">
                    流程模拟示例
                  </h3>
                  <div class="text-[10px] text-emerald-600">
                    点击使用示例
                  </div>
                </div>

                <button
                  @click="applyProcessPrompt"
                  class="w-full px-3 py-2 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white rounded text-xs font-medium shadow transition-all active:scale-95 flex items-center justify-center gap-1"
                >
                  <span>⚡</span>
                  <span>乙苯催化脱氢制苯乙烯</span>
                </button>
              </div>
            </div>

            <!-- 当前选择提示 -->
            <div v-if="selectedEquipment || (activeMenu === 'process' && userInput.includes('乙苯'))"
                 class="mb-3 p-1.5 bg-blue-50 rounded border border-blue-200">
              <div class="flex items-center justify-between">
                <div class="text-[10px] text-blue-700">
                  <span v-if="selectedEquipment">
                    <span class="font-semibold">已选择设备:</span>
                    {{ equipmentData[selectedCategory]?.find(e => e.id === selectedEquipment)?.name || selectedEquipment }}
                  </span>
                  <span v-else class="font-semibold text-emerald-700">
                    已选择流程模拟示例
                  </span>
                </div>
                <button
                  v-if="selectedEquipment"
                  @click="selectedEquipment = null"
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

  'radfrac': `用20°C, 101.325kPa 的水吸收空气中的丙酮。已知进料空气温度 20C，压力 101.325kPa，流量 14kmol/h，含丙酮 0.026(摩尔分数) ，氮气0.769, 氧气 0.205，吸收塔常压操作，理论板数 10。
要求净化后的空气中丙酮浓度为 0.005，求所需水的用量。物性方法采用 NRTL。`,

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

const processPrompt = `生成乙苯催化脱氢制苯乙烯的工艺流程。进料中纯乙苯，流量4815kg/h，温度为25℃，压力为0.1MPa；纯水，流量327kg/h，温度为25℃，压力为0.1MPa。要求产品苯乙烯纯度0.972。优先使用RStoic反应器。`;

// --- 状态变量 ---
const userInput = ref('');
const messages = ref([]);
const loading = ref(false);
const wsConnected = ref(false);
const chatBox = ref(null);
const activeMenu = ref('unit'); // 'unit' 或 'process'
const selectedCategory = ref(null);
const selectedEquipment = ref(null);

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

// --- 逻辑处理 ---
const selectMenu = (menu) => {
  activeMenu.value = menu;
  selectedEquipment.value = null;

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
  userInput.value = equipmentPrompts[id] || `我想配置一个 ${id} 设备。`;
};

const applyProcessPrompt = () => {
  userInput.value = processPrompt;
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
    const data = JSON.parse(event.data);

    if (data.type === 'done') {
      loading.value = false;
      return;
    }

    // 处理流式更新逻辑
    let lastMsg = messages.value[messages.value.length - 1];
    if (!lastMsg || lastMsg.role === 'user') {
      lastMsg = { role: 'assistant', content: '', thought: '', tool_calls: [] };
      messages.value.push(lastMsg);
    }

    if (data.thought) lastMsg.thought += data.thought;
    if (data.content) lastMsg.content += data.content;

    // 如果是工具调用
    if (data.status === 'tool_calling') {
      lastMsg.tool_calls.push(...data.tool_calls);
    }

    // 如果工具返回结果
    if (data.status === 'tool_executed') {
      data.tool_results.forEach(res => {
        const tool = lastMsg.tool_calls.find(t => t.id === res.call_id);
        if (tool) tool.result = res.result;
      });
    }

    scrollToBottom();
  };

  socket.onclose = () => {
    wsConnected.value = false;
    setTimeout(initWebSocket, 3000);
  };
};

const sendMessage = () => {
  if (!userInput.value || loading.value) return;

  const content = userInput.value;
  messages.value.push({ role: 'user', content });

  socket.send(JSON.stringify({ message: content }));

  userInput.value = '';
  loading.value = true;
  scrollToBottom();
};

const renderMarkdown = (text) => {
  return DOMPurify.sanitize(marked.parse(text));
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
</style>