<template>
  <el-dialog
    v-model="visible"
    width="600px"
    :before-close="handleClose"
    class="password-dialog"
    :show-close="false"
  >
    <div class="dialog-content">
      <div class="dialog-header">
        <h2 class="dialog-title">修改密码</h2>
        <p class="dialog-subtitle">为了您的账户安全，请定期修改密码</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        class="password-form"
      >
        <el-form-item label="当前密码" prop="currentPassword">
          <el-input
            v-model="form.currentPassword"
            type="password"
            placeholder="请输入您当前的登录密码"
            show-password
            size="large"
            class="password-input"
          />
        </el-form-item>

        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="form.newPassword"
            type="password"
            placeholder="请输入6位以上的新密码"
            show-password
            size="large"
            class="password-input"
          />
          <div class="password-tips">密码长度至少6位，建议包含字母和数字</div>
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入新密码进行确认"
            show-password
            size="large"
            class="password-input"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button 
          class="cancel-btn"
          @click="handleClose" 
          size="large"
        >
          取消
        </el-button>
        <el-button 
          class="submit-btn"
          type="primary" 
          @click="handleSubmit" 
          :loading="loading"
          size="large"
        >
          确认修改
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

interface PasswordForm {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved'): void
}

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<Emits>()

// 响应式数据
const visible = ref(props.modelValue)
const loading = ref(false)
const formRef = ref<FormInstance>()

// 表单数据
const form = reactive<PasswordForm>({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// 表单验证规则
const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error('请再次输入新密码'))
  } else if (value !== form.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  currentPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

// 监听props变化
watch(() => props.modelValue, (newVal) => {
  visible.value = newVal
})

// 监听visible变化
watch(visible, (newVal) => {
  emit('update:modelValue', newVal)
})

// 关闭对话框
const handleClose = () => {
  visible.value = false
  resetForm()
}

// 重置表单
const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields()
  }
  Object.assign(form, {
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
}

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    loading.value = true

    // 调用修改密码的API
    const response = await fetch('/change-password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        currentPassword: form.currentPassword,
        newPassword: form.newPassword
      }),
      credentials: 'include'
    })

    // 检查响应状态
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()

    if (result.success) {
      ElMessage.success('密码修改成功')
      emit('saved')
      handleClose()
    } else {
      throw new Error(result.message || '密码修改失败')
    }
  } catch (error: any) {
    console.error('修改密码错误:', error)
    ElMessage.error(error?.message || '密码修改失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.password-dialog {
  --dialog-radius: 16px;
  --primary-color: #9c0e0e;
  --border-color: #e4e7ed;
  --text-secondary: #666;
  --bg-light: #f8f9fa;
}

.dialog-content {
  padding: 0 8px;
}

.dialog-header {
  text-align: center;
  margin-bottom: 32px;
  padding: 0 16px;
}

.dialog-title {
  color: #333;
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 8px 0;
  line-height: 1.4;
}

.dialog-subtitle {
  color: var(--text-secondary);
  font-size: 14px;
  margin: 0;
  line-height: 1.5;
}

.password-form {
  padding: 0;
}

:deep(.el-form-item) {
  margin-bottom: 24px;
}

:deep(.el-form-item__label) {
  font-weight: 600;
  color: #333;
  font-size: 14px;
  padding-right: 16px;
}

.password-input {
  border-radius: 8px;
}

:deep(.password-input .el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  padding: 12px 16px;
}

:deep(.password-input .el-input__wrapper:hover) {
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

:deep(.password-input .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(156, 14, 14, 0.1);
  border-color: var(--primary-color);
}

.password-tips {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
  line-height: 1.4;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 16px;
  padding: 8px 0;
}

.cancel-btn {
  min-width: 100px;
  border-radius: 8px;
  font-weight: 500;
  border: 1px solid var(--border-color);
  background: white;
  color: #666;
  transition: all 0.3s ease;
}

.cancel-btn:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
  background: rgba(156, 14, 14, 0.05);
}

.submit-btn {
  min-width: 120px;
  border-radius: 8px;
  font-weight: 500;
  background: rgb(138, 1, 1);
  color: #ffffff;
  border: none;
  transition: all 0.3s ease;
}

.submit-btn:hover {
  background: #8a0c0cb7;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(156, 14, 14, 0.3);
}

.submit-btn:active {
  transform: translateY(0);
}

/* 对话框整体样式 */
:deep(.el-dialog) {
  border-radius: var(--dialog-radius);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

:deep(.el-dialog__body) {
  padding: 32px 40px;
}

:deep(.el-dialog__footer) {
  padding: 24px 40px 32px;
  border-top: 1px solid var(--border-color);
}

/* 响应式设计 */
@media (max-width: 640px) {
  :deep(.el-dialog) {
    width: 90% !important;
    max-width: 400px;
    margin: 20px auto;
  }
  
  :deep(.el-dialog__body) {
    padding: 24px 20px;
  }
  
  :deep(.el-dialog__footer) {
    padding: 20px 20px 24px;
  }
  
  .dialog-header {
    margin-bottom: 24px;
  }
  
  .dialog-title {
    font-size: 20px;
  }
  
  :deep(.el-form-item__label) {
    font-size: 13px;
  }
  
  .dialog-footer {
    flex-direction: column;
    gap: 12px;
  }
  
  .cancel-btn,
  .submit-btn {
    width: 100%;
    min-width: auto;
  }
}
</style>
