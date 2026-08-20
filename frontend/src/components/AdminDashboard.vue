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
const selectedSession = ref(null)
const conversationMessages = ref([])
const conversationLoading = ref(false)

const pageTitle = computed(() => ({
  overview: '数据概览',
  users: '用户管理',
  orders: '订单管理',
  refunds: '退款记录',
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

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [summaryData, usersData, ordersData, refundsData, sessionsData] = await Promise.all([
      getAdminData('/admin/summary'),
      getAdminData('/admin/users'),
      getAdminData('/admin/orders'),
      getAdminData('/admin/refunds'),
      getAdminData('/admin/sessions'),
    ])
    summary.value = summaryData.summary
    users.value = usersData.users
    orders.value = ordersData.orders
    refunds.value = refundsData.refunds
    sessions.value = sessionsData.sessions
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    loading.value = false
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

onMounted(refresh)
</script>

<template>
  <main class="admin-shell">
    <aside class="admin-sidebar">
      <div class="sidebar-brand">
        <div class="small-mark">极</div>
        <div>
          <strong>小极后台</strong>
          <span>运营管理中心</span>
        </div>
      </div>
      <nav class="admin-nav" aria-label="管理员导航">
        <button :class="{ active: activeTab === 'overview' }" type="button" @click="activeTab = 'overview'">数据概览</button>
        <button :class="{ active: activeTab === 'users' }" type="button" @click="activeTab = 'users'">用户管理</button>
        <button :class="{ active: activeTab === 'orders' }" type="button" @click="activeTab = 'orders'">订单管理</button>
        <button :class="{ active: activeTab === 'refunds' }" type="button" @click="activeTab = 'refunds'">退款记录</button>
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
                <span class="admin-message-role">{{ message.role === 'user' ? '用户' : '小极' }}</span>
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
