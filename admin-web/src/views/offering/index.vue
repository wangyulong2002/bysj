<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">教学班管理</div>
        <div class="page-desc">教学班（课程×学期×班级×教师，唯一约束 5.3.4）</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增教学班</el-button>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索课程/班级名称" clearable @keyup.enter="load" @clear="load" />
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="course_name" label="课程" min-width="140" />
          <el-table-column prop="term_name" label="学期" min-width="170" />
          <el-table-column prop="class_name" label="班级" min-width="120" />
          <el-table-column prop="teacher_name" label="任课教师" min-width="110" />
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑教学班' : '新增教学班'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="课程" prop="course_id">
          <el-select v-model="form.course_id" placeholder="选择课程" filterable style="width: 100%">
            <el-option v-for="c in courseOptions" :key="c.id" :label="c.course_name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期" prop="term_id">
          <el-select v-model="form.term_id" placeholder="选择学期" filterable style="width: 100%">
            <el-option v-for="t in termOptions" :key="t.id" :label="t.term_name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="班级" prop="class_id">
          <el-select v-model="form.class_id" placeholder="选择班级" filterable style="width: 100%">
            <el-option v-for="c in classOptions" :key="c.id" :label="c.class_name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任课教师" prop="teacher_id">
          <el-select v-model="form.teacher_id" placeholder="选择教师" filterable style="width: 100%">
            <el-option v-for="u in teacherOptions" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
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
import { offeringApi, courseApi, termApi, classApi } from '../../api/modules'
import request from '../../utils/request'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })
const courseOptions = ref([])
const termOptions = ref([])
const classOptions = ref([])
const teacherOptions = ref([])

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ id: null, course_id: null, term_id: null, class_id: null, teacher_id: null })
const rules = {
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
  term_id: [{ required: true, message: '请选择学期', trigger: 'change' }],
  class_id: [{ required: true, message: '请选择班级', trigger: 'change' }],
  teacher_id: [{ required: true, message: '请选择教师', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    const data = await offeringApi.list({
      page: query.page,
      page_size: query.page_size,
      search: query.keyword || undefined
    })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [courses, terms, classes, teachers] = await Promise.all([
    courseApi.list({ page_size: 200 }),
    termApi.list({ page_size: 50 }),
    classApi.list({ page_size: 200 }),
    request.get('/users/options', { params: { role: 'teacher' } })
  ])
  courseOptions.value = courses.results || []
  termOptions.value = terms.results || []
  classOptions.value = classes.results || []
  teacherOptions.value = teachers || []
}

function openDialog(row) {
  Object.assign(form, row
    ? {
        id: row.id, course_id: row.course_id, term_id: row.term_id,
        class_id: row.class_id, teacher_id: row.teacher_id
      }
    : { id: null, course_id: null, term_id: null, class_id: null, teacher_id: null })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (form.id) {
      await offeringApi.update(form.id, form)
      ElMessage.success('教学班已更新')
    } else {
      await offeringApi.create(form)
      ElMessage.success('教学班已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    // request 已 toast（含 4091 唯一约束）
  } finally {
    saving.value = false
  }
}

function onRemove(row) {
  ElMessageBox.confirm(`确定删除教学班「${row.course_name} - ${row.class_name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      await offeringApi.remove(row.id)
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
</style>
