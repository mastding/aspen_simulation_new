import { createApp } from 'vue'
import App from './App.vue'

// 引入全局 CSS（包含 Tailwind）
import './style.css'

// 如果你之后想加入状态管理，可以在这里引入 Pinia
const app = createApp(App)

// 全局错误处理，防止某些 Markdown 渲染异常导致崩溃
app.config.errorHandler = (err) => {
  console.error('Vue Error:', err)
}

app.mount('#app')