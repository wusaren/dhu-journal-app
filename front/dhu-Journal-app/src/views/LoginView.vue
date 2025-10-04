<template>
  <div class="login">
    <h1>用户登录</h1>
    <el-form :model="form" label-width="80px" style="max-width: 400px; margin: 0 auto;">
      <el-form-item label="用户名">
        <el-input v-model="form.username" placeholder="请输入用户名" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" placeholder="请输入密码" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleLogin" :loading="loading">登录</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'

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
    
    const response = await axios.post('http://localhost:5000/api/auth/login', {
      username: form.value.username,
      password: form.value.password
    })

    console.log('登录响应:', response.data)

    if (response.data.access_token) {
      // 保存token到localStorage
      localStorage.setItem('token', response.data.access_token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
      
      console.log('Token已保存:', response.data.access_token.substring(0, 20) + '...')
      
      ElMessage.success('登录成功！')
      router.push('/')
    } else {
      ElMessage.error('登录失败：未收到token')
    }
  } catch (error: any) {
    console.error('登录失败:', error)
    console.error('错误详情:', error.response?.data)
    ElMessage.error(`登录失败: ${error.response?.data?.message || error.message}`)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login {
  text-align: center;
  padding: 2rem;
}
</style>