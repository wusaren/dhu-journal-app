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
        <el-form-item label="期刊号" required>
          <div class="issue-inputs">
            <el-form-item prop="year" class="inline-form-item">
              <el-input 
                v-model="form.year" 
                placeholder="年" 
                maxlength="4"
                @input="validateYear"
                @blur="formatIssue"
              />
            </el-form-item>
            <span class="separator">,</span>
            <el-form-item prop="volume" class="inline-form-item">
              <el-input 
                v-model="form.volume" 
                placeholder="卷" 
                maxlength="3"
                @input="validateVolume"
                @blur="formatIssue"
              />
            </el-form-item>
            <span class="separator">(</span>
            <el-form-item prop="issueNum" class="inline-form-item">
              <el-input 
                v-model="form.issueNum" 
                placeholder="期" 
                maxlength="2"
                @input="validateIssueNum"
                @blur="formatIssue"
              />
            </el-form-item>
            <span class="separator">)</span>
          </div>
          <div class="issue-preview" v-if="form.year || form.volume || form.issueNum">
            预览: {{ getIssuePreview() }}
          </div>
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
import { journalService } from '@/api/journalService'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  year: '',
  volume: '',
  issueNum: '',
  title: '',
  publishDate: '',
  status: 'draft',
  description: ''
})

// 年份验证规则
const validateYearRule = (rule: any, value: string, callback: any) => {
  if (!value) {
    callback(new Error('请输入年份'))
  } else if (!/^\d{4}$/.test(value)) {
    callback(new Error('年份必须是4位数字'))
  } else {
    callback()
  }
}

// 数字验证规则
const validateNumberRule = (rule: any, value: string, callback: any) => {
  if (!value) {
    callback(new Error('请输入数字'))
  } else if (!/^\d+$/.test(value)) {
    callback(new Error('只能输入阿拉伯数字'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  year: [
    { required: true, message: '请输入年份', trigger: 'blur' },
    { validator: validateYearRule, trigger: 'blur' }
  ],
  volume: [
    { required: true, message: '请输入卷号', trigger: 'blur' },
    { validator: validateNumberRule, trigger: 'blur' }
  ],
  issueNum: [
    { required: true, message: '请输入期号', trigger: 'blur' },
    { validator: validateNumberRule, trigger: 'blur' }
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

// 实时年份验证
const validateYear = () => {
  form.year = form.year.replace(/[^\d]/g, '')
  if (form.year.length > 4) {
    form.year = form.year.slice(0, 4)
  }
}

// 分别处理卷号和期号的实时验证
const validateVolume = () => {
  form.volume = form.volume.replace(/[^\d]/g, '')
  if (form.volume.length > 3) {
    form.volume = form.volume.slice(0, 3)
  }
}

const validateIssueNum = () => {
  form.issueNum = form.issueNum.replace(/[^\d]/g, '')
  if (form.issueNum.length > 2) {
    form.issueNum = form.issueNum.slice(0, 2)
  }
}

// 格式化期刊号
const formatIssue = () => {
  // 这个函数会在blur时调用，用于最终格式化
}

// 获取期刊号预览
const getIssuePreview = () => {
  const year = form.year || '____'
  const volume = form.volume || '__'
  const issueNum = form.issueNum || '_'
  return `${year}, ${volume}(${issueNum})`
}

// 生成最终的期刊号格式
const generateIssueFormat = () => {
  return `${form.year}, ${form.volume}(${form.issueNum})`
}

const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    loading.value = true
    // 生成期刊号格式
    const issue = generateIssueFormat()

    // 使用服务类创建期刊
    const response = await journalService.createJournal({
      issue: issue,
      title: form.title,
      publish_date: form.publishDate,
      status: form.status,
      description: form.description
    })

    if (response.success) {
      ElMessage.success('期刊创建成功！')
      router.push('/journal-management')
    } else {
      // 检查是否有duplicate字段，如果有则显示警告而不是错误
      if (response.duplicate) {
        ElMessage.warning(response.message || '期刊创建失败')
      } else {
        ElMessage.error(response.message || '期刊创建失败')
      }
    }
  } catch (error: any) {
    console.error('创建期刊失败:', error)
    // 检查是否有duplicate字段
    if (error.response?.data?.duplicate) {
      ElMessage.warning(error.response.data.message || error.message)
    } else if (error.message && error.message.includes('已存在')) {
      ElMessage.warning(error.message)
    } else {
      ElMessage.error(error.message)
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

/* 期刊号输入框布局 */
.issue-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.inline-form-item {
  margin-bottom: 0;
}

.inline-form-item :deep(.el-form-item__content) {
  margin-left: 0 !important;
}

.inline-form-item :deep(.el-input) {
  width: 80px;
}

.separator {
  color: #666;
  font-weight: bold;
  font-size: 16px;
  user-select: none;
}

.issue-preview {
  margin-top: 8px;
  font-size: 14px;
  color: #666;
  font-style: italic;
}

/* 创建期刊按钮自定义样式 */
:deep(.el-button--primary) {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

:deep(.el-button--primary:hover) {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}
</style>
