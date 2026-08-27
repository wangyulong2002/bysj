<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">排课管理</div>
        <div class="page-desc">基于教学班排课（4.1：班级/教师冲突校验）</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增排课</el-button>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索课程/班级名称" clearable @keyup.enter="load" @clear="load" />
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="课程" min-width="130">
            <template #default="{ row }">
              {{ row.offering.course_name }}
            </template>
          </el-table-column>
          <el-table-column label="班级" min-width="110">
            <template #default="{ row }">
              {{ row.offering.class_name }}
            </template>
          </el-table-column>
          <el-table-column label="星期" width="80">
            <template #default="{ row }">{{ WEEK_NAMES[row.day_of_week] }}</template>
          </el-table-column>
          <el-table-column prop="period_start" label="开始节" width="80" />
          <el-table-column prop="period_end" label="结束节" width="80" />
          <el-table-column prop="week_start" label="起始周" width="80" />
          <el-table-column prop="week_end" label="结束周" width="80" />
          <el-table-column prop="location" label="地点" min-width="100" />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="onRemove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          class="pager"
          layout="total, prev, pager, next, sizes"
          :total="total"
          :page-size="query.page_size"
          :current-page="query.page"
          :page-sizes="[10, 20, 50]"
          @current-change="(p) => { query.page = p; load() }"
          @size-change="(s) => { query.page_size = s; query.page = 1; load() }"
        />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑排课' : '新增排课'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="教学班" prop="offering_id">
          <el-select v-model="form.offering_id" placeholder="选择教学班" filterable style="width: 100%">
            <el-option v-for="o in offeringOptions" :key="o.id" :label="`${o.course_name} · ${o.class_name}（${o.teacher_name}）`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="星期" prop="day_of_week">
          <el-select v-model="form.day_of_week" placeholder="选择星期" style="width: 100%">
            <el-option v-for="(n, i) in WEEK_NAMES.slice(1)" :key="i + 1" :label="n" :value="i + 1" />
          </el-select>
        </el-form-item>
        <el-form-item label="节次" prop="period_start">
          <div class="period-row">
            <el-input-number v-model="form.period_start" :min="1" :max="12" />
            <span class="period-sep">至</span>
            <el-input-number v-model="form.period_end" :min="1" :max="12" />
          </div>
        </el-form-item>
        <el-form-item label="周次" prop="week_start">
          <div class="period-row">
            <el-input-number v-model="form.week_start" :min="1" :max="30" />
            <span class="period-sep">至</span>
            <el-input-number v-model="form.week_end" :min="1" :max="30" />
          </div>
        </el-form-item>
        <el-form-item label="地点" prop="location">
          <el-input v-model="form.location" placeholder="如：教1-101" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { scheduleApi, offeringApi } from '../../api/modules'

const WEEK_NAMES = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日']

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })
const offeringOptions = ref([])

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, offering_id: null, day_of_week: 1,
  period_start: 1, period_end: 1, week_start: 1, week_end: 20, location: ''
})
const rules = {
  offering_id: [{ required: true, message: '请选择教学班', trigger: 'change' }],
  day_of_week: [{ required: true, message: '请选择星期', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    const data = await scheduleApi.list({
      page: query.page,
      page_size: query.page_size,
      search: query.keyword || undefined
    })
    rows.value = (data.results || []).map((r) => ({ ...r, offering: r.offering || {} }))
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const data = await offeringApi.list({ page_size: 200 })
  offeringOptions.value = data.results || []
}

function openDialog(row) {
  Object.assign(form, row
    ? {
        id: row.id, offering_id: row.offering_id, day_of_week: row.day_of_week,
        period_start: row.period_start, period_end: row.period_end,
        week_start: row.week_start, week_end: row.week_end, location: row.location
      }
    : { id: null, offering_id: null, day_of_week: 1, period_start: 1, period_end: 1, week_start: 1, week_end: 20, location: '' })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (form.id) {
      await scheduleApi.update(form.id, form)
      ElMessage.success('排课已更新')
    } else {
      await scheduleApi.create(form)
      ElMessage.success('排课已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    // request 已 toast（含 4091 冲突）
  } finally {
    saving.value = false
  }
}

function onRemove(row) {
  ElMessageBox.confirm('确定删除这条排课记录吗？', '提示', { type: 'warning' })
    .then(async () => {
      await scheduleApi.remove(row.id)
      ElMessage.success('已删除')
      load()
    })
    .catch(() => {})
}

onMounted(() => {
  load()
  loadOptions()
})
</script>

<style lang="scss" scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.period-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.period-sep {
  color: #475569;
  font-size: 13px;
}
</style>
