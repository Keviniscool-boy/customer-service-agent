<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import AdminDashboard from './components/AdminDashboard.vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8765'
const mode = ref('login')
const username = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const message = ref('')
const messageType = ref('')
const storedUser = localStorage.getItem('xiaojie_user')
const user = ref(storedUser ? JSON.parse(storedUser) : null)
const authenticated = ref(Boolean(localStorage.getItem('xiaojie_token') && user.value))

const sessions = ref([])
const activeSessionId = ref(null)
const chatMessages = ref([])
const draft = ref('')
const sessionsLoading = ref(false)
const messagesLoading = ref(false)
const sending = ref(false)
const workspaceError = ref('')
const messagesEl = ref(null)

const isLogin = computed(() => mode.value === 'login')
const isLoggedIn = computed(() => authenticated.value && Boolean(user.value))
const isAdmin = computed(() => isLoggedIn.value && user.value.role === 'admin')
const activeSession = computed(() => sessions.value.find((session) => session.id === activeSessionId.value))

function visibleReply(payload) {
  let value = typeof payload === 'string' ? payload : payload?.reply
  if (typeof value !== 'string') return ''

  value = value.trim()
  try {
    const parsed = JSON.parse(value)
    if (parsed && typeof parsed.reply === 'string') {
      value = parsed.reply.trim()
      if (typeof parsed.follow_up_question === 'string' && parsed.follow_up_question.trim() && !value.includes(parsed.follow_up_question)) {
        value += `\n${parsed.follow_up_question.trim()}`
      }
    }
  } catch {
    // 普通文本不需要解析。
  }
  return value
}

function setMessage(text, type = 'error') {
  message.value = text
  messageType.value = type
}

function switchMode(nextMode) {
  mode.value = nextMode
  message.value = ''
  messageType.value = ''
}

async function apiRequest(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  const token = localStorage.getItem('xiaojie_token')
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body) headers['Content-Type'] = 'application/json'

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json')
    ? await response.json()
    : await response.text()
  if (!response.ok) {
    if (response.status === 401) logout()
    throw new Error(data?.error?.message || '请求失败，请稍后重试。')
  }
  return data
}

async function submitForm() {
  if (!username.value.trim() || !password.value) {
    setMessage('请输入用户名和密码。')
    return
  }

  loading.value = true
  message.value = ''

  try {
    const data = await apiRequest(`/${isLogin.value ? 'login' : 'register'}`, {
      method: 'POST',
      body: JSON.stringify({ username: username.value.trim(), password: password.value }),
    })

    if (isLogin.value) {
      localStorage.setItem('xiaojie_token', data.access_token)
      localStorage.setItem('xiaojie_user', JSON.stringify(data.user))
      user.value = data.user
      authenticated.value = true
      setMessage('登录成功。', 'success')
      // 登录成功先进入聊天页，会话历史在页面内继续加载。
      loadSessions()
    } else {
      setMessage('注册成功，请使用新账号登录。', 'success')
      mode.value = 'login'
      password.value = ''
    }
  } catch (error) {
    setMessage(error.message || '无法连接服务器，请确认 FastAPI 已启动。')
  } finally {
    loading.value = false
  }
}

async function loadSessions() {
  sessionsLoading.value = true
  workspaceError.value = ''
  try {
    const data = await apiRequest('/sessions')
    sessions.value = data.sessions || []
    if (!sessions.value.length) {
      await createSession()
    } else {
      const selected = sessions.value.find((session) => session.id === activeSessionId.value)
      await selectSession(selected || sessions.value[0])
    }
  } catch (error) {
    workspaceError.value = error.message
  } finally {
    sessionsLoading.value = false
  }
}

async function createSession() {
  try {
    const data = await apiRequest('/sessions', {
      method: 'POST',
      body: JSON.stringify({ title: '新对话' }),
    })
    const newSession = {
      id: data.session_id,
      title: data.title || '新对话',
      summary: null,
    }
    sessions.value = [newSession, ...sessions.value]
    await selectSession(newSession)
  } catch (error) {
    workspaceError.value = error.message
  }
}

async function selectSession(session) {
  if (!session) return
  activeSessionId.value = session.id
  chatMessages.value = []
  messagesLoading.value = true
  try {
    const data = await apiRequest(`/sessions/${session.id}/messages`)
    chatMessages.value = (data.messages || []).map((message) => ({
      ...message,
      content: message.role === 'assistant' ? visibleReply(message.content) : message.content,
    }))
    await scrollToBottom()
  } catch (error) {
    workspaceError.value = error.message
  } finally {
    messagesLoading.value = false
  }
}

async function sendMessage() {
  const content = draft.value.trim()
  if (!content || !activeSessionId.value || sending.value) return

  draft.value = ''
  chatMessages.value.push({ role: 'user', content })
  await scrollToBottom()
  sending.value = true
  workspaceError.value = ''

  try {
    const data = await apiRequest('/chat', {
      method: 'POST',
      body: JSON.stringify({ message: content, session_id: activeSessionId.value }),
    })
    const reply = visibleReply(data)
    chatMessages.value.push({ role: 'assistant', content: reply || '暂时没有收到回复。' })
    await loadSessions()
  } catch (error) {
    workspaceError.value = error.message
    chatMessages.value.push({ role: 'assistant', content: '请求失败，请检查服务是否正常运行。' })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

function handleComposerKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

function logout() {
  localStorage.removeItem('xiaojie_token')
  localStorage.removeItem('xiaojie_user')
  user.value = null
  authenticated.value = false
  sessions.value = []
  activeSessionId.value = null
  chatMessages.value = []
  username.value = ''
  password.value = ''
  mode.value = 'login'
  setMessage('已退出登录。', 'success')
}

onMounted(() => {
  if (isLoggedIn.value) loadSessions()
})
</script>

<template>
  <AdminDashboard v-if="isAdmin" :user="user" @logout="logout" />

  <main v-else-if="isLoggedIn" class="workspace-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="small-mark">极</div>
        <div>
          <strong>小极客服</strong>
          <span>服务工作台</span>
        </div>
      </div>

      <button class="new-chat-button" type="button" :disabled="sessionsLoading" @click="createSession">
        <span aria-hidden="true">+</span> 新建会话
      </button>

      <div class="session-heading">
        <span>最近会话</span>
        <span>{{ sessions.length }}</span>
      </div>
      <div class="session-list">
        <button
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === activeSessionId }"
          type="button"
          @click="selectSession(session)"
        >
          <span class="session-dot" aria-hidden="true"></span>
          <span class="session-title">{{ session.title || '新对话' }}</span>
        </button>
        <p v-if="!sessions.length && !sessionsLoading" class="empty-note">还没有会话</p>
      </div>

      <div class="user-area">
        <div class="user-avatar">{{ user.username.slice(0, 1).toUpperCase() }}</div>
        <div class="user-info">
          <strong>{{ user.username }}</strong>
          <span>已登录</span>
        </div>
        <button class="logout-button" type="button" title="退出登录" @click="logout">退出</button>
      </div>
    </aside>

    <section class="chat-panel">
      <header class="chat-header">
        <div>
          <p class="eyebrow">CUSTOMER SERVICE AGENT</p>
          <h1>{{ activeSession?.title || '新对话' }}</h1>
        </div>
        <span class="online-status"><i></i> 在线</span>
      </header>

      <div ref="messagesEl" class="messages-area">
        <div v-if="messagesLoading" class="loading-state">正在读取会话...</div>
        <template v-else>
          <div v-if="!chatMessages.length" class="welcome-state">
            <div class="welcome-mark">极</div>
            <h2>你好，{{ user.username }}</h2>
            <p>我是小极，可以帮你查询订单、物流、商品和售后问题。</p>
            <div class="suggestion-list">
              <button type="button" @click="draft = '查询我的订单'">查询我的订单</button>
              <button type="button" @click="draft = '我的订单到哪里了？'">查询物流</button>
              <button type="button" @click="draft = '7天无理由退货怎么计算？'">退货政策</button>
            </div>
          </div>

          <div
            v-for="(item, index) in chatMessages"
            :key="`${item.role}-${index}`"
            class="message-row"
            :class="item.role === 'user' ? 'from-user' : 'from-agent'"
          >
            <div v-if="item.role !== 'user'" class="message-avatar">极</div>
            <div class="message-bubble">{{ item.content }}</div>
            <div v-if="item.role === 'user'" class="message-avatar user-message-avatar">{{ user.username.slice(0, 1).toUpperCase() }}</div>
          </div>
        </template>
      </div>

      <form class="composer" @submit.prevent="sendMessage">
        <textarea
          v-model="draft"
          rows="1"
          placeholder="输入你的问题..."
          :disabled="sending"
          @keydown="handleComposerKeydown"
        ></textarea>
        <button class="send-button" type="submit" :disabled="sending || !draft.trim()" title="发送消息">
          {{ sending ? '...' : '发送' }}
        </button>
        <p>Enter 发送 · Shift + Enter 换行</p>
      </form>
      <p v-if="workspaceError" class="workspace-error">{{ workspaceError }}</p>
    </section>
  </main>

  <main v-else class="auth-shell">
    <section class="brand-panel">
      <div class="brand-mark" aria-hidden="true">极</div>
      <p class="eyebrow">E-COMMERCE SERVICE AGENT</p>
      <h1>小极客服</h1>
      <p class="brand-copy">订单、物流、商品和售后问题，交给一个懂业务的客服 Agent。</p>
      <div class="feature-list">
        <span>01</span><p>对话记忆，接着聊</p>
        <span>02</span><p>订单信息，快速查</p>
        <span>03</span><p>复杂问题，转人工</p>
      </div>
    </section>

    <section class="auth-panel">
      <form class="auth-form" @submit.prevent="submitForm">
        <div class="form-heading">
          <p class="eyebrow">CUSTOMER SERVICE CONSOLE</p>
          <h2>{{ isLogin ? '欢迎回来' : '创建账号' }}</h2>
          <p class="muted">{{ isLogin ? '登录后开始使用小极客服。' : '注册一个账号，保存你的会话记录。' }}</p>
        </div>

        <div class="mode-tabs" role="tablist" aria-label="登录或注册">
          <button :class="{ active: isLogin }" type="button" @click="switchMode('login')">登录</button>
          <button :class="{ active: !isLogin }" type="button" @click="switchMode('register')">注册</button>
        </div>

        <label>用户名<input v-model="username" name="username" autocomplete="username" placeholder="请输入用户名" /></label>
        <label>
          密码
          <input v-model="password" name="password" :type="showPassword ? 'text' : 'password'" :autocomplete="isLogin ? 'current-password' : 'new-password'" placeholder="请输入密码" />
        </label>
        <label class="password-toggle"><input v-model="showPassword" type="checkbox" /> 显示密码</label>
        <p v-if="message" :class="['form-message', messageType]" role="status">{{ message }}</p>
        <button class="primary-button" type="submit" :disabled="loading">{{ loading ? '处理中...' : isLogin ? '登录小极客服' : '创建账号' }}</button>
      </form>
    </section>
  </main>
</template>
