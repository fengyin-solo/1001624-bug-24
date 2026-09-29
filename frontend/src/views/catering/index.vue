<template>
  <section class="page" data-module="catering">
    <header class="page-head">
      <div>
        <h2>航空配餐管理</h2>
        <p class="page-desc">维护配餐单，围绕配餐单号、关联航班、餐食份数、餐食类别做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记配餐单</button>
        <button class="btn" type="button" @click="exportRows">导出航空配餐清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ displayCell(row, column) }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无航空配餐数据，可先登记配餐单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条航空配餐记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="signTarget" class="modal-mask" @click.self="closeSign">
      <form class="modal-card" @submit.prevent="submitSign">
        <h3 class="modal-title">确认签收 · {{ signTarget['配餐单号'] }}</h3>
        <p class="modal-desc">关联航班 {{ signTarget['关联航班'] }}，登记餐食份数 {{ signTarget['餐食份数'] }}（{{ signTarget['餐食类别'] }}）</p>
        <label class="form-item">
          <span>接收人员 <em>*</em></span>
          <input v-model="signForm.receiver" placeholder="请填写实际接收人" />
        </label>
        <label class="form-item">
          <span>签收份数 <em>*</em></span>
          <input v-model="signForm.portions" type="number" min="1" :max="Number(signTarget['餐食份数'])" placeholder="不得超过登记份数" />
        </label>
        <label class="form-item">
          <span>送达时刻</span>
          <input v-model="signForm.deliveredAt" placeholder="留空则取当前时刻" />
        </label>
        <p v-if="signError" class="error-text">{{ signError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" :disabled="submitting" @click="closeSign">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">{{ submitting ? '提交中…' : '确认签收' }}</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onActivated, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/catering'
const columns = ["配餐单号", "关联航班", "餐食份数", "餐食类别", "配餐车辆", "送达时刻", "接收人员", "配餐状态"]
const actions = ["安排配送", "确认签收", "取消配送"]
const statuses = ["待配送", "配送中", "已签收", "已取消"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

// 合计与列表数据同源：列表刷新后自动重算，签收/取消后调用 reload 即可同步
const stats = computed(() => {
  const list = rows.value
  const portions = list.reduce((sum, row) => {
    const value = Number(row['餐食份数'])
    return Number.isFinite(value) ? sum + value : sum
  }, 0)
  const categories = new Set(
    list.map((row) => String(row['餐食类别'] ?? '').trim()).filter((value) => value && value !== '—'),
  )
  return [
    { label: '待配送配餐', value: list.filter((row) => row['配餐状态'] === '待配送').length },
    { label: '配餐份数合计', value: portions },
    { label: '餐食类别合计', value: categories.size },
    { label: '取消单数', value: list.filter((row) => row['配餐状态'] === '已取消').length },
  ]
})

function displayCell(row: Row, column: string) {
  // 配餐状态以接口回填的真实状态为准，其余列空值统一占位，避免相邻列串位
  const value = column === '配餐状态' ? row['配餐状态'] ?? row.status : row[column]
  return value === null || value === undefined || value === '' ? '—' : value
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '配餐单登记入口尚未接入审批流'
}

// ---- 确认签收弹窗：接收人员、签收份数必填，送达时刻可留空由后端回填 ----
const signTarget = ref<Row | null>(null)
const signForm = reactive({ receiver: '', portions: '', deliveredAt: '' })
const signError = ref('')
const submitting = ref(false)

function runAction(action: string, row: Row) {
  errorMessage.value = ''
  if (action === '确认签收') {
    signTarget.value = row
    signForm.receiver = ''
    signForm.portions = String(row['餐食份数'] ?? '')
    signForm.deliveredAt = ''
    signError.value = ''
    return
  }
  void submitAction(action, row, {})
}

function closeSign() {
  if (submitting.value) return
  signTarget.value = null
  signError.value = ''
}

async function submitSign() {
  if (!signTarget.value) return
  const receiver = signForm.receiver.trim()
  const portionsText = signForm.portions.trim()
  const portions = Number(portionsText)
  if (!receiver) {
    signError.value = '请填写接收人员后再签收'
    return
  }
  if (!portionsText || !Number.isInteger(portions) || portions <= 0) {
    signError.value = '签收份数需为正整数'
    return
  }
  const registered = Number(signTarget.value['餐食份数'])
  if (Number.isInteger(registered) && portions > registered) {
    signError.value = `签收份数 ${portions} 超出登记份数 ${registered}，不能签收`
    return
  }
  await submitAction(
    '确认签收',
    signTarget.value,
    {
      接收人员: receiver,
      签收份数: portions,
      ...(signForm.deliveredAt.trim() ? { 送达时刻: signForm.deliveredAt.trim() } : {}),
    },
    () => {
      signTarget.value = null
    },
  )
}

async function submitAction(action: string, row: Row, extra: Record<string, unknown>, onSuccess?: () => void) {
  submitting.value = true
  signError.value = ''
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, ...extra } }),
    })
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}，操作未生效`)
    }
    const payload = await response.json()
    // HTTP 200 但业务失败（重复签收、接收人员缺失、份数超登记值等）也要按失败提示
    if (!payload.ok) {
      if (signTarget.value) signError.value = payload.message || '签收失败'
      else errorMessage.value = payload.message || '航空配餐操作失败'
      return
    }
    onSuccess?.()
    await reload()
  } catch (error) {
    const message = error instanceof Error ? error.message : '航空配餐操作失败'
    if (signTarget.value) signError.value = message
    else errorMessage.value = message
  } finally {
    submitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('配餐单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '航空配餐列表读取失败'
  }
}

// KeepAlive 缓存下保留列表数据；每次返回页面时静默刷新，保证与后端状态一致
let mountedOnce = false
onMounted(() => {
  if (!mountedOnce) {
    mountedOnce = true
    void reload()
  }
})
onActivated(() => {
  if (mountedOnce) void reload()
})
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-card {
  width: 420px;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.2);
}
.modal-title { margin: 0; font-size: 16px; }
.modal-desc { margin: 6px 0 12px; color: var(--muted); font-size: 12px; }
.form-item { display: block; margin-bottom: 10px; }
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-item em { color: #b42318; font-style: normal; }
.form-item input { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
</style>
