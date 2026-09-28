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
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div v-if="stats.类别份数.length" class="summary-bar">
      <span class="summary-chip">餐食类别合计：</span>
      <span v-for="item in stats.类别份数" :key="item.餐食类别" class="summary-chip">
        {{ item.餐食类别 }} {{ item.餐食份数 }} 份
      </span>
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
          <td v-for="column in columns" :key="column">{{ row[column] === '' || row[column] == null ? '—' : row[column] }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="!canRun(action, row)"
              :title="canRun(action, row) ? action : `当前「${row['配餐状态']}」状态不允许${action}`"
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
      <span v-if="noticeMessage" class="success-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="signDialogVisible" class="modal-mask" @click.self="closeSignDialog">
      <form class="modal" @submit.prevent="confirmSign">
        <h3>确认签收 · {{ signTarget?.['配餐单号'] }}</h3>
        <div class="form-line">
          <label>接收人员（必填）</label>
          <input v-model="signForm.receiver" placeholder="请填写实际接收人姓名" />
        </div>
        <div class="form-line">
          <label>签收份数（留空按登记份数 {{ signTarget?.['餐食份数'] }} 份签收）</label>
          <input v-model="signForm.portions" inputmode="numeric" placeholder="实际签收份数" />
        </div>
        <p v-if="signError" class="error-text">{{ signError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeSignDialog">取消</button>
          <button class="btn primary" type="submit">确认签收</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type StatsData = {
  待配送配餐: number
  配餐份数合计: number
  取消单数: number
  类别份数: { 餐食类别: string; 餐食份数: number }[]
}

const ENDPOINT = '/api/catering'
const columns = ["配餐单号", "关联航班", "餐食份数", "餐食类别", "配餐车辆", "送达时刻", "接收人员", "配餐状态"]
const actions = ["安排配送", "确认签收", "取消配送"]
// 状态机：只有处于允许前置状态的动作可点，已签收的单子无法重复签收
const ACTIONS_BY_STATUS: Record<string, string[]> = {
  "待配送": ["安排配送", "取消配送"],
  "配送中": ["确认签收", "取消配送"],
  "已签收": [],
  "已取消": [],
}

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref<StatsData>({ 待配送配餐: 0, 配餐份数合计: 0, 取消单数: 0, 类别份数: [] })
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const statCards = computed(() => [
  { label: "待配送配餐", value: stats.value.待配送配餐 },
  { label: "本月配餐份数", value: stats.value.配餐份数合计 },
  { label: "取消单数", value: stats.value.取消单数 },
])

const signDialogVisible = ref(false)
const signTarget = ref<Row | null>(null)
const signError = ref('')
const signForm = reactive({ receiver: '', portions: '' })

function canRun(action: string, row: Row): boolean {
  return ACTIONS_BY_STATUS[String(row['配餐状态'] ?? '')]?.includes(action) ?? false
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

function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  if (!canRun(action, row)) {
    return
  }
  if (action === '确认签收') {
    openSignDialog(row)
    return
  }
  void submitAction(action, row, {})
}

function openSignDialog(row: Row) {
  signTarget.value = row
  signForm.receiver = ''
  signForm.portions = String(row['餐食份数'] ?? '')
  signError.value = ''
  signDialogVisible.value = true
}

function closeSignDialog() {
  signDialogVisible.value = false
  signTarget.value = null
  signError.value = ''
}

async function confirmSign() {
  const row = signTarget.value
  if (!row) {
    return
  }
  const receiver = signForm.receiver.trim()
  if (!receiver) {
    signError.value = '接收人员不能为空，请填写实际接收人后再签收'
    return
  }
  const extra: Record<string, string | number> = { 接收人员: receiver }
  const portionsText = signForm.portions.trim()
  if (portionsText) {
    if (!/^\d+$/.test(portionsText) || Number(portionsText) <= 0) {
      signError.value = '签收份数必须是不小于 1 的整数，请重新填写'
      return
    }
    const portions = Number(portionsText)
    const registered = Number(row['餐食份数'])
    if (Number.isFinite(registered) && portions > registered) {
      signError.value = `签收份数 ${portions} 超出登记份数 ${registered}，请按实际送达数量核对`
      return
    }
    extra['签收份数'] = portions
  }
  await submitAction('确认签收', row, extra)
  if (!errorMessage.value) {
    closeSignDialog()
  }
}

async function submitAction(action: string, row: Row, extra: Record<string, string | number>) {
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, ...extra } }),
    })
    if (!response.ok) {
      let detail = '航空配餐动作未生效，请稍后重试'
      try {
        const payload = await response.json()
        detail = payload?.detail ?? detail
      } catch {
        // 非 JSON 错误体时保留兜底说明
      }
      throw new Error(detail)
    }
    const result = await response.json()
    if (!result.ok) {
      errorMessage.value = result.message || '航空配餐动作未生效'
      return
    }
    noticeMessage.value = result.message || '操作已生效'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '航空配餐操作失败'
  }
}

async function reloadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (response.ok) {
      stats.value = await response.json()
    }
  } catch {
    // 合计读取失败不阻塞列表，保留上一次的数字
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
    void reloadStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '航空配餐列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.success-text { color: #067647; }
.summary-bar { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; }
.summary-chip {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 12px;
  color: var(--muted);
}
.link:disabled { color: #9aa6b2; cursor: not-allowed; }
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(16, 24, 40, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  width: 380px;
  background: #fff;
  border-radius: 8px;
  padding: 18px 20px;
}
.modal h3 { margin: 0 0 14px; font-size: 15px; }
.form-line { margin-bottom: 12px; }
.form-line label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-line input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
</style>
