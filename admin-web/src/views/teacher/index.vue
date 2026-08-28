<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">教师管理</div>
        <div class="page-desc">教师档案与登录账号联动（5.3.8）；可兼任辅导员（ADR-010，最多 2 个班级）</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增教师</el-button>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索工号/姓名/院系" clearable @keyup.enter="load" @clear="load" />
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="teacher_no" label="工号" min-width="110" />
          <el-table-column prop="nick_name" label="姓名" min-width="90" />
          <el-table-column prop="username" label="登录账号" min-width="110" />
          <el-table-column prop="title" label="职称" min-width="90" />
          <el-table-column prop="department_name" label="所属院系" min-width="120" />
          <el-table-column label="兼任班级" min-width="140">
            <template #default="{ row }">
              <template v-if="(row.counselor_class_names || []).length">
                <el-tag v-for="n in row.counselor_class_names" :key="n" size="small" class="tag-dept" effect="plain" style="margin-right: 6px">
                  {{ n }}
                </el-tag>
              </template>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="create_time" label="创建时间" min-width="150" />
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑教师' : '新增教师'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="工号" prop="teacher_no">
          <el-input v-model="form.teacher_no" placeholder="留空自动生成（同时作为登录账号）" :disabled="!!form.id" />
        </el-form-item>
        <el-form-item label="姓名" prop="nick_name">
          <el-input v-model="form.nick_name" placeholder="教师姓名" />
        </el-form-item>
        <el-form-item label="职称" prop="title">
          <el-input v-model="form.title" placeholder="如：讲师 / 副教授" />
        </el-form-item>
        <el-form-item label="所属院系" prop="department_id">
          <el-select v-model="form.department_id" placeholder="选择院系" clearable filterable style="width: 100%">
            <el-option v-for="d in deptOptions" :key="d.id" :label="d.dept_name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="兼任辅导员">
          <el-switch v-model="form.is_counselor" active-text="是" inactive-text="否" />
        </el-form-item>
        <el-form-item v-if="form.is_counselor" label="兼任班级" prop="counselor_class_ids">
          <el-select
            v-model="form.counselor_class_ids"
            multiple
            :multiple-limit="2"
            filterable
            placeholder="选择 1~2 个无辅导员班级（最多 2 个）"
            style="width: 100%"
          >
            <el-option v-for="c in freeClassOptions" :key="c.id" :label="c.class_name" :value="c.id" />
          </el-select>
          <div class="form-tip">仅显示暂无辅导员的班级；每名教师最多兼任 2 个班</div>
        </el-form-item>
        <el-form-item v-if="!form.id" label="初始密码" prop="password">
          <el-input v-model="form.password" placeholder="留空默认 123456" show-password />
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
import { teacherApi, departmentApi } from '../../api/modules'
import request from '../../utils/request'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })
const deptOptions = ref([])
const freeClassOptions = ref([])

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, teacher_no: '', nick_name: '', title: '', department_id: null, password: '',
  is_counselor: false, counselor_class_ids: []
})
const rules = {
  nick_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  counselor_class_ids: [{
    validator: (_r, _v, cb) => {
      if (form.is_counselor && !form.counselor_class_ids.length) {
        cb(new Error('兼任辅导员需选择班级'))
      } else if (form.counselor_class_ids.length > 2) {
        cb(new Error('最多兼任 2 个班级'))
      } else {
        cb()
      }
    },
    trigger: 'change'
  }]
}

async function load() {
  loading.value = true
  try {
    const data = await teacherApi.list({
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
  const [depts, freeClasses] = await Promise.all([
    departmentApi.list({ page_size: 100 }),
    request.get('/classes/options', { params: { without_counselor: '1' } })
  ])
  deptOptions.value = depts.results || []
  freeClassOptions.value = freeClasses || []
}

function openDialog(row) {
  // 编辑回显：兼任班级 = 后端返回的 counselor_class_id_list（当前兼任班级）
  const curIds = row && row.counselor_class_id_list ? row.counselor_class_id_list : []
  Object.assign(form, row
    ? {
        id: row.id, teacher_no: row.teacher_no, nick_name: row.nick_name,
        title: row.title, department_id: row.department_id, password: '',
        is_counselor: curIds.length > 0, counselor_class_ids: [...curIds]
      }
    : { id: null, teacher_no: '', nick_name: '', title: '', department_id: null, password: '', is_counselor: false, counselor_class_ids: [] })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      teacher_no: form.teacher_no, nick_name: form.nick_name,
      title: form.title, department_id: form.department_id,
      is_counselor: form.is_counselor,
      counselor_class_ids: form.is_counselor ? form.counselor_class_ids : []
    }
    if (form.id) {
      await teacherApi.update(form.id, payload)
      ElMessage.success('教师已更新')
    } else {
      await teacherApi.create({ ...payload, password: form.password || undefined })
      ElMessage.success('教师已创建（登录账号已自动开通）')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    // request 已 toast
  } finally {
    saving.value = false
  }
}

function onRemove(row) {
  ElMessageBox.confirm(`确定删除教师「${row.nick_name}（${row.teacher_no}）」吗？其登录账号将同时停用。`, '提示', { type: 'warning' })
    .then(async () => {
      await teacherApi.remove(row.id)
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

.text-muted {
  color: $ink-2;
}

.form-tip {
  margin-top: 6px;
  font-size: 12px;
  color: $ink-2;
}

.tag-dept {
  color: $brand-deep;
  border-color: rgba(14, 116, 144, 0.3);
  background: $brand-soft;
}
</style>
