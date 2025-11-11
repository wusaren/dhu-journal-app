<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>用户登录</h1>
      </div>
      
      <el-form :model="form" class="login-form">
        <el-form-item>
          <el-input 
            v-model="form.username" 
            placeholder="请输入用户名"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item>
          <el-input 
            v-model="form.password" 
            type="password" 
            placeholder="请输入密码"
            size="large"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button 
            type="primary" 
            @click="handleLogin" 
            :loading="loading"
            class="login-btn"
            size="large"
          >
            {{ loading ? '登录中...' : '登录' }}
          </el-button>
        </el-form-item>
      </el-form>
      
      
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { authService } from '@/api/authService'

const router = useRouter()
const form = ref({
  username: '',
  password: ''
})

const loading = ref(false)

const handleLogin = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.error('请输入用户名和密码')
    return
  }

  loading.value = true
  
  try {
    console.log('开始登录...', form.value.username)
    
    const response = await authService.login({
      username: form.value.username,
      password: form.value.password
    })

    console.log('登录响应:', response)

    if (response.message === '登录成功' && response.user) {
      // 保存用户信息到localStorage
      localStorage.setItem('user', JSON.stringify(response.user))
      
      console.log('用户信息已保存:', response.user.username)
      
      // 触发自定义事件，通知App.vue更新登录状态
      window.dispatchEvent(new CustomEvent('user-login'))
      
      ElMessage.success('登录成功！')
      router.push('/')
    } else {
      ElMessage.error('登录失败：' + (response.message || '未知错误'))
    }
  } catch (error: any) {
    console.error('登录失败:', error)
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #ffffffff 0%, #ffffffff 100%);
  padding: 1rem;
}

.login-card {
  background: white;
  border-radius: 16px;
  padding: 2.5rem;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 420px;
  text-align: center;
}

.login-header {
  margin-bottom: 2rem;
}

.login-header h1 {
  color: #9c0e0e;
  font-size: 2rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
}

.login-header p {
  color: #666;
  font-size: 1rem;
  margin: 0;
}

.login-form {
  margin-bottom: 1.5rem;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 1.5rem;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 2px 8px rgba(156, 14, 14, 0.2);
}

.login-btn {
  width: 100%;
  background: linear-gradient(135deg, #9c0e0e 0%, #7a0b0b 100%);
  border: none;
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(156, 14, 14, 0.3);
}

.login-footer {
  border-top: 1px solid #f0f0f0;
  padding-top: 1.5rem;
}

.register-link {
  color: #9c0e0e;
  font-weight: 500;
  transition: color 0.3s ease;
}

.register-link:hover {
  color: #7a0b0b;
}

/* 响应式设计 */
@media (max-width: 480px) {
  .login-container {
    padding: 1rem;
  }
  
  .login-card {
    padding: 2rem;
  }
  
  .login-header h1 {
    font-size: 1.75rem;
  }
}
</style>
