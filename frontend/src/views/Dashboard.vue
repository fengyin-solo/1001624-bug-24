<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onActivated, onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])

const FALLBACK_CARDS = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
const FALLBACK_MODULES = [{"name": "航班计划", "created": 0, "pending": 0, "abnormal": 0}, {"name": "机位资源", "created": 0, "pending": 0, "abnormal": 0}, {"name": "机坪巡查", "created": 0, "pending": 0, "abnormal": 0}, {"name": "廊桥对接", "created": 0, "pending": 0, "abnormal": 0}, {"name": "除冰作业", "created": 0, "pending": 0, "abnormal": 0}, {"name": "航油加注", "created": 0, "pending": 0, "abnormal": 0}, {"name": "行李装卸", "created": 0, "pending": 0, "abnormal": 0}, {"name": "货邮装载", "created": 0, "pending": 0, "abnormal": 0}, {"name": "航空配餐", "created": 0, "pending": 0, "abnormal": 0}, {"name": "摆渡接送", "created": 0, "pending": 0, "abnormal": 0}, {"name": "航空器牵引", "created": 0, "pending": 0, "abnormal": 0}, {"name": "载重平衡", "created": 0, "pending": 0, "abnormal": 0}, {"name": "通行证件", "created": 0, "pending": 0, "abnormal": 0}, {"name": "保障车辆", "created": 0, "pending": 0, "abnormal": 0}, {"name": "安全监察", "created": 0, "pending": 0, "abnormal": 0}, {"name": "保障协议", "created": 0, "pending": 0, "abnormal": 0}, {"name": "保障结算", "created": 0, "pending": 0, "abnormal": 0}, {"name": "资质培训", "created": 0, "pending": 0, "abnormal": 0}]

async function loadOverview() {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = FALLBACK_CARDS
    moduleRows.value = FALLBACK_MODULES
  }
}

onMounted(loadOverview)
// KeepAlive 缓存下，从业务页返回时重新汇总，保证与列表状态一致
onActivated(loadOverview)
</script>
