<script setup>
import { computed, onMounted, ref } from 'vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8765'

const props = defineProps({
  user: { type: Object, required: true },
})
const emit = defineEmits(['logout'])

const activeTab = ref('overview')
const loading = ref(false)
const error = ref('')
const summary = ref({ users: 0, orders: 0, refunds: 0, sessions: 0 })
const users = ref([])
const orders = ref([])
const refunds = ref([])
const sessions = ref([])
const agents = ref([])
const selectedAgentId = ref(null)
const agentConfig = ref(null)
const agentForm = ref(null)
const knowledgeStatus = ref(null)
const agentVersions = ref([])
const knowledgeFile = ref(null)
const knowledgeLoading = ref(false)
const selectedSession = ref(null)
const conversationMessages = ref([])
const conversationLoading = ref(false)

const pageTitle = computed(() => ({
  overview: '数据概览',
  users: '用户管理',
  orders: '订单管理',
  refunds: '退款记录',
  agents: 'Agent 与知识库',
  conversations: '对话记录',
}[activeTab.value]))

async function getAdminData(path) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${localStorage.getItem('xiaojie_token')}`,
    },
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data?.error?.message || '后台数据读取失败')
  return data
}

async function sendAdminData(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${localStorage.getItem('xiaojie_token')}`,
      ...(options.headers || {}),
    },
  })
  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) throw new Error(data?.error?.message || '操作失败')
  return data
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [summaryData, usersData, ordersData, refundsData, sessionsData, agentsData] = await Promise.all([
      getAdminData('/admin/summary'),
      getAdminData('/admin/users'),
      getAdminData('/admin/orders'),
      getAdminData('/admin/refunds'),
      getAdminData('/admin/sessions'),
      getAdminData('/agents'),
    ])
    summary.value = summaryData.summary
    users.value = usersData.users
    orders.value = ordersData.orders
    refunds.value = refundsData.refunds
    sessions.value = sessionsData.sessions
    agents.value = agentsData.agents || []
    if (!agents.value.some((agent) => agent.agent_id === selectedAgentId.value)) {
      selectedAgentId.value = agents.value[0]?.agent_id || null
    }
    if (selectedAgentId.value) await loadKnowledgeStatus()
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    loading.value = false
  }
}

async function loadKnowledgeStatus() {
  if (!selectedAgentId.value) return
  try {
    const [statusData, configData, versionsData] = await Promise.all([
      getAdminData(`/admin/agents/${selectedAgentId.value}/knowledge`),
      getAdminData(`/admin/agents/${selectedAgentId.value}`),
      getAdminData(`/admin/agents/${selectedAgentId.value}/versions`),
    ])
    knowledgeStatus.value = statusData
    agentVersions.value = versionsData.versions || []
    agentConfig.value = configData.agent
    agentForm.value = {
      name: agentConfig.value.name,
      role: agentConfig.value.role,
      welcome_message: agentConfig.value.welcome_message,
      tone: agentConfig.value.tone,
      service_scope: agentConfig.value.service_scope.join('\n'),
      custom_prompt: agentConfig.value.custom_prompt || '',
      behavior_rules: (agentConfig.value.behavior_rules || []).join('\n'),
      forbidden_topics: (agentConfig.value.forbidden_topics || []).join('\n'),
      knowledge_provider: agentConfig.value.knowledge_provider || 'weknora',
      knowledge_base_id: agentConfig.value.knowledge_base_id || '',
      knowledge_base_path: agentConfig.value.knowledge_base_path,
      enabled_tools: agentConfig.value.enabled_tools.join(', '),
      model_name: agentConfig.value.model_name || '',
      temperature: agentConfig.value.temperature ?? '',
    }
  } catch (requestError) {
    error.value = requestError.message
  }
}

async function restoreAgentVersion(version) {
  if (!selectedAgentId.value) return
  if (!window.confirm(`确定恢复到配置版本 v${version} 吗？当前配置会保留为新版本。`)) return
  knowledgeLoading.value = true
  error.value = ''
  try {
    await sendAdminData(
      `/admin/agents/${selectedAgentId.value}/versions/${version}/restore`,
      { method: 'POST' },
    )
    await loadKnowledgeStatus()
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    knowledgeLoading.value = false
  }
}

async function waitForKnowledgeReady(filename) {
  if (!selectedAgentId.value || !filename) return
  for (let attempt = 0; attempt < 15; attempt += 1) {
    await loadKnowledgeStatus()
    const status = knowledgeStatus.value
    if (status?.provider !== 'weknora') return
    const document = (status.documents || []).find(
      (item) => (item.file_name || item.title) === filename,
    )
    if (document?.parse_status === 'completed' || document?.parse_status === 'failed') return
    await new Promise((resolve) => window.setTimeout(resolve, 2000))
  }
}

async function saveAgentConfig() {
  if (!selectedAgentId.value || !agentForm.value || !agentConfig.value) return
  knowledgeLoading.value = true
  error.value = ''
  try {
    await sendAdminData(`/admin/agents/${selectedAgentId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...agentConfig.value,
        ...agentForm.value,
        service_scope: agentForm.value.service_scope.split(/[,\n]/).map((item) => item.trim()).filter(Boolean),
        custom_prompt: agentForm.value.custom_prompt.trim(),
        behavior_rules: agentForm.value.behavior_rules.split(/[,\n]/).map((item) => item.trim()).filter(Boolean),
        forbidden_topics: agentForm.value.forbidden_topics.split(/[,\n]/).map((item) => item.trim()).filter(Boolean),
        enabled_tools: agentForm.value.enabled_tools.split(',').map((item) => item.trim()).filter(Boolean),
        model_name: agentForm.value.model_name.trim() || null,
        temperature: agentForm.value.temperature === '' ? null : Number(agentForm.value.temperature),
      }),
    })
    await refresh()
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    knowledgeLoading.value = false
  }
}

function selectKnowledgeFile(event) {
  knowledgeFile.value = event.target.files?.[0] || null
}

async function uploadKnowledge() {
  if (!knowledgeFile.value || !selectedAgentId.value) return
  knowledgeLoading.value = true
  error.value = ''
  try {
    const formData = new FormData()
    formData.append('file', knowledgeFile.value)
    const data = await sendAdminData(`/admin/agents/${selectedAgentId.value}/knowledge`, {
      method: 'POST',
      body: formData,
    })
    knowledgeFile.value = null
    await waitForKnowledgeReady(data.filename)
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    knowledgeLoading.value = false
  }
}

async function rebuildKnowledge() {
  if (!selectedAgentId.value) return
  knowledgeLoading.value = true
  try {
    await sendAdminData(`/admin/agents/${selectedAgentId.value}/knowledge/rebuild`, { method: 'POST' })
    await loadKnowledgeStatus()
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    knowledgeLoading.value = false
  }
}

async function deleteKnowledge(filename) {
  if (!selectedAgentId.value) return
  knowledgeLoading.value = true
  try {
    await sendAdminData(`/admin/agents/${selectedAgentId.value}/knowledge/${encodeURIComponent(filename)}`, { method: 'DELETE' })
    await loadKnowledgeStatus()
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    knowledgeLoading.value = false
  }
}

async function openConversation(session) {
  selectedSession.value = session
  conversationMessages.value = []
  conversationLoading.value = true
  error.value = ''
  try {
    const data = await getAdminData(`/admin/sessions/${session.id}/messages`)
    conversationMessages.value = data.messages || []
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    conversationLoading.value = false
  }
}

function formatAmount(amount) {
  return `¥${Number(amount || 0).toFixed(2)}`
}

function displayAgentName(agentId) {
  return agents.value.find((agent) => agent.agent_id === agentId)?.name || agentId || 'Agent'
}

onMounted(refresh)
</script>

<template>
  <main class="admin-shell">
    <aside class="admin-sidebar">
      <div class="sidebar-brand">
        <div class="small-mark">极</div>
        <div>
          <strong>Agent 管理后台</strong>
          <span>运营管理中心</span>
        </div>
      </div>
      <nav class="admin-nav" aria-label="管理员导航">
        <button :class="{ active: activeTab === 'overview' }" type="button" @click="activeTab = 'overview'">数据概览</button>
        <button :class="{ active: activeTab === 'users' }" type="button" @click="activeTab = 'users'">用户管理</button>
        <button :class="{ active: activeTab === 'orders' }" type="button" @click="activeTab = 'orders'">订单管理</button>
        <button :class="{ active: activeTab === 'refunds' }" type="button" @click="activeTab = 'refunds'">退款记录</button>
        <button :class="{ active: activeTab === 'agents' }" type="button" @click="activeTab = 'agents'">Agent 与知识库</button>
        <button :class="{ active: activeTab === 'conversations' }" type="button" @click="activeTab = 'conversations'">对话记录</button>
      </nav>
      <div class="admin-user">
        <strong>{{ props.user.username }}</strong>
        <span>管理员</span>
        <button type="button" @click="emit('logout')">退出登录</button>
      </div>
    </aside>

    <section class="admin-content">
      <header class="admin-header">
        <div>
          <p class="eyebrow">ADMIN CONSOLE</p>
          <h1>{{ pageTitle }}</h1>
        </div>
        <button class="refresh-button" type="button" :disabled="loading" @click="refresh">{{ loading ? '刷新中...' : '刷新数据' }}</button>
      </header>

      <p v-if="error" class="admin-error">{{ error }}</p>

      <template v-if="activeTab === 'overview'">
        <div class="metric-grid">
          <div class="metric-item"><span>用户总数</span><strong>{{ summary.users }}</strong></div>
          <div class="metric-item"><span>订单总数</span><strong>{{ summary.orders }}</strong></div>
          <div class="metric-item"><span>退款记录</span><strong>{{ summary.refunds }}</strong></div>
          <div class="metric-item"><span>会话总数</span><strong>{{ summary.sessions }}</strong></div>
        </div>
        <section class="admin-section">
          <div class="section-heading"><h2>最近订单</h2><button type="button" @click="activeTab = 'orders'">查看全部</button></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>订单号</th><th>用户</th><th>商品</th><th>状态</th><th>金额</th></tr></thead>
              <tbody>
                <tr v-for="order in orders.slice(0, 5)" :key="order.order_id"><td>{{ order.order_id }}</td><td>{{ order.username || '公共示例' }}</td><td>{{ order.product_name }}</td><td>{{ order.status }}</td><td>{{ formatAmount(order.amount) }}</td></tr>
                <tr v-if="!orders.length"><td colspan="5" class="empty-cell">暂无订单</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <section v-else-if="activeTab === 'agents'" class="admin-section knowledge-admin">
        <div class="section-heading">
          <div>
            <h2>Agent 知识库</h2>
            <p class="section-hint">上传 Markdown 后由 WeKnora 自动解析和检索。</p>
          </div>
          <select v-model="selectedAgentId" class="admin-select" @change="loadKnowledgeStatus">
            <option v-for="agent in agents" :key="agent.agent_id" :value="agent.agent_id">{{ agent.name }}</option>
          </select>
        </div>
        <div v-if="agentForm" class="agent-config-form">
          <label>名称<input v-model="agentForm.name" /></label>
          <label>角色<input v-model="agentForm.role" /></label>
          <label>欢迎语<input v-model="agentForm.welcome_message" /></label>
          <label>语气<input v-model="agentForm.tone" /></label>
          <label>知识库服务
            <select v-model="agentForm.knowledge_provider">
              <option value="weknora">WeKnora</option>
              <option value="local">本地 RAG（备用）</option>
            </select>
          </label>
          <label>WeKnora 知识库 ID<input v-model="agentForm.knowledge_base_id" placeholder="留空后首次上传时自动创建" /></label>
          <label>知识库目录<input v-model="agentForm.knowledge_base_path" /></label>
          <label>模型名称<input v-model="agentForm.model_name" placeholder="留空使用全局模型" /></label>
          <label>温度<input v-model="agentForm.temperature" type="number" min="0" max="2" step="0.1" placeholder="留空使用全局温度" /></label>
          <label class="wide-field">服务范围<textarea v-model="agentForm.service_scope" rows="3" placeholder="每行一个服务范围"></textarea></label>
          <label class="wide-field">自定义 Prompt<textarea v-model="agentForm.custom_prompt" rows="5" placeholder="定义这个 Agent 的工作方式"></textarea></label>
          <label class="wide-field">行为规则<textarea v-model="agentForm.behavior_rules" rows="3" placeholder="每行一条规则"></textarea></label>
          <label class="wide-field">禁止主题<textarea v-model="agentForm.forbidden_topics" rows="3" placeholder="每行一个不处理的主题"></textarea></label>
          <label class="wide-field">启用工具<textarea v-model="agentForm.enabled_tools" rows="2" placeholder="多个工具用英文逗号分隔"></textarea></label>
          <div class="wide-field form-actions"><button class="refresh-button" type="button" :disabled="knowledgeLoading" @click="saveAgentConfig">保存 Agent 配置</button></div>
        </div>
        <div v-if="knowledgeStatus" class="knowledge-toolbar">
          <label class="file-picker">
            <span>{{ knowledgeFile?.name || '选择 .md 文件' }}</span>
            <input type="file" accept=".md,text/markdown" @change="selectKnowledgeFile" />
          </label>
          <button class="refresh-button" type="button" :disabled="knowledgeLoading || !knowledgeFile" @click="uploadKnowledge">{{ knowledgeLoading ? '处理中...' : '上传并索引' }}</button>
          <button class="refresh-button" type="button" :disabled="knowledgeLoading" @click="rebuildKnowledge">重建索引</button>
          <span class="index-state">{{ knowledgeStatus.index_ready ? '索引已就绪' : knowledgeStatus.provider === 'weknora' ? 'WeKnora 解析中' : '索引未就绪' }}</span>
        </div>
        <div v-if="knowledgeStatus?.files?.length" class="knowledge-files">
          <div v-for="filename in knowledgeStatus.files" :key="filename" class="knowledge-file">
            <span>{{ filename }}</span>
            <button type="button" :disabled="knowledgeLoading" @click="deleteKnowledge(filename)">删除</button>
          </div>
        </div>
        <div class="agent-versions">
          <div class="knowledge-manager-heading">
            <div><h3>配置版本</h3><p>每次保存都会保留快照，最多保留最近 20 个版本。</p></div>
          </div>
          <div v-if="agentVersions.length" class="agent-version-list">
            <div v-for="item in agentVersions" :key="item.version" class="agent-version-item">
              <span>v{{ item.version }} · {{ item.created_at }}</span>
              <button class="refresh-button" type="button" :disabled="knowledgeLoading" @click="restoreAgentVersion(item.version)">恢复</button>
            </div>
          </div>
          <p v-else class="empty-cell">还没有配置版本。</p>
        </div>
        <p v-if="!knowledgeStatus?.files?.length" class="empty-cell">当前 Agent 还没有 Markdown 知识库文件。</p>
      </section>

      <section v-else-if="activeTab === 'conversations'" class="conversation-layout">
        <div class="conversation-list-panel">
          <div class="conversation-panel-heading">
            <h2>用户会话</h2>
            <span>{{ sessions.length }}</span>
          </div>
          <button
            v-for="session in sessions"
            :key="session.id"
            class="conversation-item"
            :class="{ active: selectedSession?.id === session.id }"
            type="button"
            @click="openConversation(session)"
          >
            <strong>{{ session.title || '新对话' }}</strong>
            <span>{{ session.username || '未知用户' }} · {{ session.message_count }} 条消息</span>
            <small>{{ session.updated_at }}</small>
          </button>
          <p v-if="!sessions.length" class="empty-cell">暂无会话</p>
        </div>
        <div class="conversation-detail-panel">
          <div v-if="!selectedSession" class="conversation-empty">选择一个会话查看聊天内容</div>
          <template v-else>
            <div class="conversation-detail-heading">
              <div><h2>{{ selectedSession.title || '新对话' }}</h2><span>{{ selectedSession.username || '未知用户' }}</span></div>
              <span>{{ selectedSession.message_count }} 条消息</span>
            </div>
            <div v-if="conversationLoading" class="conversation-empty">正在读取聊天记录...</div>
            <div v-else class="conversation-messages">
              <div v-for="(message, index) in conversationMessages" :key="`${message.role}-${index}`" class="admin-message" :class="message.role === 'user' ? 'admin-message-user' : 'admin-message-agent'">
                <span class="admin-message-role">{{ message.role === 'user' ? '用户' : displayAgentName(selectedSession.agent_id) }}</span>
                <p>{{ message.content }}</p>
                <small>{{ message.created_at }}</small>
              </div>
              <p v-if="!conversationMessages.length" class="conversation-empty">暂无可显示的聊天消息</p>
            </div>
          </template>
        </div>
      </section>

      <section v-else class="admin-section full-section">
        <div v-if="activeTab === 'users'" class="table-wrap">
          <table><thead><tr><th>用户名</th><th>角色</th><th>创建时间</th></tr></thead><tbody><tr v-for="item in users" :key="item.id"><td>{{ item.username }}</td><td>{{ item.role === 'admin' ? '管理员' : '普通用户' }}</td><td>{{ item.created_at }}</td></tr><tr v-if="!users.length"><td colspan="3" class="empty-cell">暂无用户</td></tr></tbody></table>
        </div>
        <div v-else-if="activeTab === 'orders'" class="table-wrap">
          <table><thead><tr><th>订单号</th><th>用户</th><th>商品</th><th>状态</th><th>金额</th><th>物流单号</th></tr></thead><tbody><tr v-for="item in orders" :key="item.order_id"><td>{{ item.order_id }}</td><td>{{ item.username || '公共示例' }}</td><td>{{ item.product_name }}</td><td>{{ item.status }}</td><td>{{ formatAmount(item.amount) }}</td><td>{{ item.tracking_number || '-' }}</td></tr><tr v-if="!orders.length"><td colspan="6" class="empty-cell">暂无订单</td></tr></tbody></table>
        </div>
        <div v-else class="table-wrap">
          <table><thead><tr><th>退款单号</th><th>订单号</th><th>用户</th><th>原因</th><th>状态</th><th>金额</th></tr></thead><tbody><tr v-for="item in refunds" :key="item.refund_id"><td>{{ item.refund_id }}</td><td>{{ item.order_id }}</td><td>{{ item.username || '-' }}</td><td>{{ item.reason }}</td><td>{{ item.status }}</td><td>{{ formatAmount(item.amount) }}</td></tr><tr v-if="!refunds.length"><td colspan="6" class="empty-cell">暂无退款记录</td></tr></tbody></table>
        </div>
      </section>
    </section>
  </main>
</template>
