import axios from 'axios'
import { ElMessage } from 'element-plus'

// 创建axios实例
const apiClient = axios.create({
  // baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000',
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 100000,
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true  // 允许发送和接收cookies
})

// 请求拦截器 - 添加认证信息
apiClient.interceptors.request.use(
  (config) => {
    // 检查用户是否已登录，添加必要的认证信息
    const userStr = localStorage.getItem('user')
    if (userStr) {
      try {
        const user = JSON.parse(userStr)
        // 对于session认证，确保withCredentials为true
        config.withCredentials = true
      } catch {
        // 忽略解析错误
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    // 直接返回数据，而不是整个response对象
    return response.data
  },
  (error) => {
    console.error('API请求错误:', error)

    // 处理网络错误
    if (error.code === 'ERR_NETWORK') {
      ElMessage.error('无法连接到服务器，请检查网络连接')
      throw new Error('网络连接错误')
    }

    // 处理HTTP错误
    if (error.response) {
      const status = error.response.status
      const message = error.response.data?.message || '请求失败'

      switch (status) {
        case 401:
          // 清除本地存储的token
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          ElMessage.error('登录已过期，请重新登录')
          window.location.href = '/login'
          throw new Error('登录已过期')
        // case 403:
        //   ElMessage.error('权限不足')
        //   throw new Error('权限不足')
        case 404:
          ElMessage.error('请求的资源不存在')
          throw new Error('资源不存在')
        case 500:
          ElMessage.error('服务器内部错误')
          throw new Error('服务器错误')
        case 400:
          // 对于400错误，抛出包含完整响应数据的错误
          const error400 = new Error(message) as any
          error400.response = error.response || {}
          error400.response.data = error.response.data || {}
          error400.response.data.message = message
          error400.response.data.duplicate = error.response.data?.duplicate
          error400.response.data.papers_count = error.response.data?.papers_count
          error400.response.data.existing_paper = error.response.data?.existing_paper
          error400.response.data.requires_confirmation = error.response.data?.requires_confirmation
          throw error400
        default:
          ElMessage.error(message)
          throw new Error(message)
      }
    }

    // ElMessage.error('未知错误')
    // throw new Error('未知错误')
  }
)

export default apiClient
