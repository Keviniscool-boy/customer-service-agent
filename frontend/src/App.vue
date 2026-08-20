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
const agents = ref([])
const activeAgentId = ref(localStorage.getItem('xiaojie_agent_id') || 'ecom-default')
const activeSessionId = ref(null)
const chatMessages = ref([])
const draft = ref('')
const sessionsLoading = ref(false)
const messagesLoading = ref(false)
const sending = ref(false)
const workspaceError = ref('')
const messagesEl = ref(null)
const showAgentManager = ref(false)
const agentManagerMode = ref('create')
const agentManagerLoading = ref(false)
const agentManagerError = ref('')
const agentFile = ref(null)
const agentKnowledge = ref(null)
const agentForm = ref(createEmptyAgentForm())

const isLogin = computed(() => mode.value === 'login')
const isLoggedIn = computed(() => authenticated.value && Boolean(user.value))
const isAdmin = computed(() => isLoggedIn.value && user.value.role === 'admin')
const activeSession = computed(() => sessions.value.find((session) => session.id === activeSessionId.value))
const activeAgent = computed(() => agents.value.find((agent) => agent.agent_id === activeAgentId.value) || {
  agent_id: 'ecom-default',
  name: '小极',
  role: '极客商城智能客服',
  welcome_message: '您好，我是极客商城智能客服小极，很高兴为您服务！',
  is_public: true,
})

const ownedAgents = computed(() => agents.value.filter((agent) => !agent.is_public))

function createEmptyAgentForm() {
  return {
    agent_id: '',
    name: '',
    role: '',
    welcome_message: '',
    tone: '友好、清晰、简洁',
    service_scope: '',
    model_name: '',
    temperature: '',
  }
}

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
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

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
      await loadAgents()
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
    sessions.value = (data.sessions || []).filter(
      (session) => session.agent_id === activeAgentId.value,
    )
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

async function loadAgents() {
  try {
    const data = await apiRequest('/agents')
    agents.value = data.agents || []
    if (!agents.value.some((agent) => agent.agent_id === activeAgentId.value)) {
      activeAgentId.value = agents.value[0]?.agent_id || 'ecom-default'
    }
    localStorage.setItem('xiaojie_agent_id', activeAgentId.value)
    await loadSessions()
  } catch (error) {
    workspaceError.value = error.message
  }
}

function openAgentManager() {
  showAgentManager.value = true
  agentManagerMode.value = 'create'
  agentManagerError.value = ''
  agentForm.value = createEmptyAgentForm()
  agentKnowledge.value = null
  agentFile.value = null
}

function closeAgentManager() {
  showAgentManager.value = false
  agentManagerError.value = ''
  agentFile.value = null
}

async function editOwnedAgent(agentId) {
  agentManagerLoading.value = true
  agentManagerError.value = ''
  try {
    const data = await apiRequest(`/agents/${agentId}`)
    const config = data.agent
    agentManagerMode.value = 'edit'
    agentForm.value = {
      agent_id: config.agent_id,
      name: config.name,
      role: config.role,
      welcome_message: config.welcome_message,
      tone: config.tone,
      service_scope: (config.service_scope || []).join('\n'),
      model_name: config.model_name || '',
      temperature: config.temperature ?? '',
    }
    await loadAgentKnowledge()
  } catch (error) {
    agentManagerError.value = error.message
  } finally {
    agentManagerLoading.value = false
  }
}

async function loadAgentKnowledge() {
  if (agentManagerMode.value !== 'edit' || !agentForm.value.agent_id) return
  try {
    agentKnowledge.value = await apiRequest(
      `/agents/${agentForm.value.agent_id}/knowledge`,
    )
  } catch (error) {
    agentManagerError.value = error.message
  }
}

async function saveUserAgent() {
  const form = agentForm.value
  if (!form.agent_id.trim() || !form.name.trim() || !form.role.trim()) {
    agentManagerError.value = '请填写 Agent ID、名称和角色。'
    return
  }

  agentManagerLoading.value = true
  agentManagerError.value = ''
  try {
    const payload = {
      agent_id: form.agent_id.trim(),
      name: form.name.trim(),
      role: form.role.trim(),
      welcome_message: form.welcome_message.trim(),
      tone: form.tone.trim(),
      service_scope: form.service_scope.split(/[\n,]/).map((item) => item.trim()).filter(Boolean),
      enabled_tools: ['search_knowledge'],
      model_name: form.model_name.trim() || null,
      temperature: form.temperature === '' ? null : Number(form.temperature),
    }
    const path = agentManagerMode.value === 'edit'
      ? `/agents/${form.agent_id}`
      : '/agents'
    const data = await apiRequest(path, {
      method: agentManagerMode.value === 'edit' ? 'PUT' : 'POST',
      body: JSON.stringify(payload),
    })
    activeAgentId.value = data.agent.agent_id
    localStorage.setItem('xiaojie_agent_id', activeAgentId.value)
    closeAgentManager()
    await loadAgents()
  } catch (error) {
    agentManagerError.value = error.message
  } finally {
    agentManagerLoading.value = false
  }
}

async function deleteUserAgent() {
  if (!formHasAgent()) return
  const agentId = agentForm.value.agent_id
  if (!window.confirm(`确定删除 Agent「${agentForm.value.name}」及其个人知识库吗？`)) return

  agentManagerLoading.value = true
  agentManagerError.value = ''
  try {
    await apiRequest(`/agents/${agentId}`, { method: 'DELETE' })
    if (activeAgentId.value === agentId) {
      activeAgentId.value = 'ecom-default'
      localStorage.setItem('xiaojie_agent_id', activeAgentId.value)
    }
    closeAgentManager()
    await loadAgents()
  } catch (error) {
    agentManagerError.value = error.message
  } finally {
    agentManagerLoading.value = false
  }
}

function selectAgentFile(event) {
  agentFile.value = event.target.files?.[0] || null
}

async function uploadAgentKnowledge() {
  if (!agentFile.value || !agentForm.value.agent_id) return
  agentManagerLoading.value = true
  agentManagerError.value = ''
  try {
    const formData = new FormData()
    formData.append('file', agentFile.value)
    await apiRequest(`/agents/${agentForm.value.agent_id}/knowledge`, {
      method: 'POST',
      body: formData,
    })
    agentFile.value = null
    await loadAgentKnowledge()
  } catch (error) {
    agentManagerError.value = error.message
  } finally {
    agentManagerLoading.value = false
  }
}

async function rebuildAgentKnowledge() {
  if (!agentForm.value.agent_id) return
  agentManagerLoading.value = true
  agentManagerError.value = ''
  try {
    await apiRequest(`/agents/${agentForm.value.agent_id}/knowledge/rebuild`, {
      method: 'POST',
    })
    await loadAgentKnowledge()
  } catch (error) {
    agentManagerError.value = error.message
  } finally {
    agentManagerLoading.value = false
  }
}

async function deleteAgentKnowledge(filename) {
  if (!formHasAgent()) return
  if (!window.confirm(`确定删除 ${filename} 吗？`)) return
  agentManagerLoading.value = true
  agentManagerError.value = ''
  try {
    await apiRequest(
      `/agents/${agentForm.value.agent_id}/knowledge/${encodeURIComponent(filename)}`,
      { method: 'DELETE' },
    )
    await loadAgentKnowledge()
  } catch (error) {
    agentManagerError.value = error.message
  } finally {
    agentManagerLoading.value = false
  }
}

function formHasAgent() {
  return agentManagerMode.value === 'edit' && Boolean(agentForm.value.agent_id)
}

async function changeAgent() {
  activeSessionId.value = null
  chatMessages.value = []
  localStorage.setItem('xiaojie_agent_id', activeAgentId.value)
  await loadSessions()
}

async function createSession() {
  try {
    const data = await apiRequest('/sessions', {
      method: 'POST',
      body: JSON.stringify({ title: '新对话', agent_id: activeAgentId.value }),
    })
    const newSession = {
      id: data.session_id,
      title: data.title || '新对话',
      agent_id: activeAgentId.value,
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
      body: JSON.stringify({
        message: content,
        session_id: activeSessionId.value,
        agent_id: activeAgentId.value,
      }),
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
  agents.value = []
  activeSessionId.value = null
  chatMessages.value = []
  username.value = ''
  password.value = ''
  mode.value = 'login'
  setMessage('已退出登录。', 'success')
}

onMounted(() => {
  if (isLoggedIn.value) loadAgents()
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

      <label class="agent-picker">
        <span>当前 Agent</span>
        <select v-model="activeAgentId" :disabled="sessionsLoading" @change="changeAgent">
          <option v-for="agent in agents" :key="agent.agent_id" :value="agent.agent_id">
            {{ agent.name }}
          </option>
        </select>
      </label>

      <button class="sidebar-action" type="button" @click="openAgentManager">
        管理我的 Agent
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
          <h1>{{ activeSession?.title || activeAgent.name }}</h1>
        </div>
        <span class="online-status"><i></i> 在线</span>
      </header>

      <div ref="messagesEl" class="messages-area">
        <div v-if="messagesLoading" class="loading-state">正在读取会话...</div>
        <template v-else>
          <div v-if="!chatMessages.length" class="welcome-state">
            <div class="welcome-mark">{{ activeAgent.name.slice(0, 1) }}</div>
            <h2>你好，{{ user.username }}</h2>
            <p>{{ activeAgent.welcome_message }}</p>
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
            <div v-if="item.role !== 'user'" class="message-avatar">{{ activeAgent.name.slice(0, 1) }}</div>
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

    <div v-if="showAgentManager" class="agent-manager-overlay" @click.self="closeAgentManager">
      <section class="agent-manager-panel" aria-labelledby="agent-manager-title">
        <header class="agent-manager-heading">
          <div>
            <p class="eyebrow">MY AGENTS</p>
            <h2 id="agent-manager-title">{{ agentManagerMode === 'edit' ? '编辑 Agent' : '创建 Agent' }}</h2>
          </div>
          <button class="icon-close-button" type="button" title="关闭" @click="closeAgentManager">×</button>
        </header>

        <div class="agent-manager-layout">
          <aside class="owned-agent-list">
            <button class="agent-create-link" type="button" @click="openAgentManager">+ 新建 Agent</button>
            <button
              v-for="agent in ownedAgents"
              :key="agent.agent_id"
              class="owned-agent-item"
              :class="{ active: agentManagerMode === 'edit' && agent.agent_id === agentForm.agent_id }"
              type="button"
              @click="editOwnedAgent(agent.agent_id)"
            >
              <strong>{{ agent.name }}</strong>
              <span>{{ agent.agent_id }}</span>
            </button>
            <p v-if="!ownedAgents.length" class="manager-empty">还没有自己的 Agent</p>
          </aside>

          <form class="agent-form" @submit.prevent="saveUserAgent">
            <label>Agent ID<input v-model="agentForm.agent_id" :disabled="agentManagerMode === 'edit'" placeholder="例如：我的知识库助手" /></label>
            <label>名称<input v-model="agentForm.name" placeholder="例如：学习助手" /></label>
            <label>角色<input v-model="agentForm.role" placeholder="这个 Agent 负责什么" /></label>
            <label>欢迎语<input v-model="agentForm.welcome_message" placeholder="用户打开对话时看到的内容" /></label>
            <label>语气<input v-model="agentForm.tone" placeholder="例如：友好、简洁" /></label>
            <label>模型名称<input v-model="agentForm.model_name" placeholder="留空使用全局模型" /></label>
            <label>温度<input v-model="agentForm.temperature" type="number" min="0" max="2" step="0.1" placeholder="留空使用全局温度" /></label>
            <label class="wide-field">服务范围<textarea v-model="agentForm.service_scope" rows="3" placeholder="每行一个服务范围"></textarea></label>
            <p class="agent-tool-note">当前个人 Agent 自动启用知识库搜索，不开放订单和退款工具。</p>
            <p v-if="agentManagerError" class="manager-error">{{ agentManagerError }}</p>
            <div class="agent-form-actions">
              <button class="primary-button" type="submit" :disabled="agentManagerLoading">{{ agentManagerLoading ? '处理中...' : '保存 Agent' }}</button>
              <button v-if="agentManagerMode === 'edit'" class="danger-button" type="button" :disabled="agentManagerLoading" @click="deleteUserAgent">删除 Agent</button>
            </div>

            <template v-if="agentManagerMode === 'edit'">
              <div class="knowledge-manager">
                <div class="knowledge-manager-heading">
                  <div><h3>个人知识库</h3><p>上传 Markdown 后会自动建立索引。</p></div>
                  <span>{{ agentKnowledge?.index_ready ? '已就绪' : '未就绪' }}</span>
                </div>
                <div class="knowledge-upload-row">
                  <label class="file-picker">
                    <span>{{ agentFile?.name || '选择 .md 文件' }}</span>
                    <input type="file" accept=".md,text/markdown" @change="selectAgentFile" />
                  </label>
                  <button class="refresh-button" type="button" :disabled="agentManagerLoading || !agentFile" @click="uploadAgentKnowledge">上传</button>
                  <button class="refresh-button" type="button" :disabled="agentManagerLoading" @click="rebuildAgentKnowledge">重建</button>
                </div>
                <div v-if="agentKnowledge?.files?.length" class="owned-knowledge-list">
                  <div v-for="filename in agentKnowledge.files" :key="filename" class="owned-knowledge-item">
                    <span>{{ filename }}</span>
                    <button type="button" :disabled="agentManagerLoading" @click="deleteAgentKnowledge(filename)">删除</button>
                  </div>
                </div>
                <p v-else class="manager-empty">还没有上传 Markdown 文件</p>
              </div>
            </template>
          </form>
        </div>
      </section>
    </div>
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
