<template>
  <div class="create-journal">
    <el-card class="create-card">
      <template #header>
        <div class="card-header">
          <h3>创建新期刊</h3>
          <el-button @click="$router.back()">返回</el-button>
        </div>
      </template>

      <el-form 
        :model="form" 
        :rules="rules" 
        ref="formRef" 
        label-width="120px"
        style="max-width: 600px;"
      >
        <el-form-item label="期刊号" prop="issue">
          <el-input v-model="form.issue" placeholder="请输入期刊号，如：2025，42（3）" />
        </el-form-item>

        <el-form-item label="期刊名称" prop="title">
          <el-input v-model="form.title" placeholder="请输入期刊名称" />
        </el-form-item>

        <el-form-item label="出版日期" prop="publishDate">
          <el-date-picker
            v-model="form.publishDate"
            type="date"
            placeholder="选择出版日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>

        <el-form-item label="期刊状态" prop="status">
          <el-select v-model="form.status" placeholder="请选择期刊状态">
            <el-option label="草稿" value="draft" />
            <el-option label="已发布" value="published" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </el-form-item>

        <el-form-item label="期刊描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入期刊描述"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="loading">
            创建期刊
          </el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  issue: '',
  title: '',
  publishDate: '',
  status: 'draft',
  description: ''
})

const rules: FormRules = {
  issue: [
    { required: true, message: '请输入期刊号', trigger: 'blur' }
  ],
  title: [
    { required: true, message: '请输入期刊名称', trigger: 'blur' }
  ],
  publishDate: [
    { required: true, message: '请选择出版日期', trigger: 'change' }
  ],
  status: [
    { required: true, message: '请选择期刊状态', trigger: 'change' }
  ]
}

const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    loading.value = true

    // 调用后端API创建期刊
    const response = await axios.post('http://localhost:5000/api/journals/create', {
      issue: form.issue,
      title: form.title,
      publish_date: form.publishDate,
      status: form.status,
      description: form.description
    })

    if (response.data.success) {
      ElMessage.success('期刊创建成功！')
      router.push('/journal-management')
    } else {
      ElMessage.error(response.data.message || '期刊创建失败')
    }
  } catch (error: any) {
    console.error('创建期刊失败:', error)
    if (error.response?.status === 400) {
      ElMessage.error(`创建失败: ${error.response.data.message}`)
    } else if (error.code === 'ERR_NETWORK') {
      ElMessage.error('无法连接到后端服务，请确保后端服务已启动')
    } else {
      ElMessage.error(`创建期刊失败: ${error.response?.data?.message || error.message}`)
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.create-journal {
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

.create-card {
  max-width: 800px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  color: #333;
}
</style>
