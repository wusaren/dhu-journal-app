<template>
  <div class="app-container">
    <!-- 顶部导航栏 -->
    <header class="top-header">
      <div class="header-content">
        <div class="header-left">
          <h1>东华学报编辑社工作系统</h1>
        </div>
        <div class="header-right">
          <el-button v-if="!isLoggedIn" class="login-btn" @click="handleLogin">
            登录
          </el-button>
          <el-dropdown v-else>
            <span class="user-info">
              <el-icon><user /></el-icon>
              {{ currentUser?.username || '用户' }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">
                  <el-icon><switch-button /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </header>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 左侧工作栏 -->
      <aside class="sidebar">
        
        <el-menu
          :default-active="currentRoute"
          class="work-menu"
          @select="handleMenuSelect"
          router
        >
          <el-menu-item index="/">
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/preliminary-review">
            <span>初审系统</span>
          </el-menu-item>
          <el-menu-item index="/paper-management">
            <span>论文管理</span>
          </el-menu-item>
          <el-menu-item index="/journal-management">
            <span>期刊管理</span>
          </el-menu-item>
          <el-menu-item index="/personality-center">
            <span>个人中心</span>
          </el-menu-item>
          <el-menu-item v-if="isAdmin" index="/admin">
            <span>用户管理</span>
          </el-menu-item>
        </el-menu>
      </aside>

      <!-- 右侧内容区域 -->
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { computed, ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, SwitchButton } from '@element-plus/icons-vue'
import { authService } from '@/api/authService'

const route = useRoute()
const router = useRouter()

const isLoggedIn = ref(false)
const currentUser = ref<any>(null)
const currentRoute = computed(() => route.path)

// 检查是否为管理员
const isAdmin = computed(() => {
  return currentUser.value?.role === 'admin' || currentUser.value?.roles?.includes('admin')
})

// 检查登录状态
const checkLoginStatus = () => {
  const user = authService.getCurrentUserFromStorage()
  if (user) {
    isLoggedIn.value = true
    currentUser.value = user
  } else {
    isLoggedIn.value = false
    currentUser.value = null
  }
}

const handleMenuSelect = (index: string) => {
  router.push(index)
}

const handleLogin = () => {
  router.push('/login')
}

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    
    // 调用后端登出接口
    try {
      await authService.logout()
    } catch (error) {
      console.log('后端登出失败，继续清除前端状态')
    }
    
    // 清除前端状态
    authService.clearUserInfo()
    isLoggedIn.value = false
    currentUser.value = null
    
    ElMessage.success('退出登录成功')
    router.push('/')
  } catch {
    ElMessage.info('取消退出登录')
  }
}

// 监听路由变化，检查登录状态
onMounted(() => {
  checkLoginStatus()
})

// 监听路由变化，实时更新登录状态
watch(() => route.path, () => {
  checkLoginStatus()
})

// 监听storage变化，实时更新登录状态
window.addEventListener('storage', checkLoginStatus)

// 自定义事件监听，用于登录成功后的状态更新
window.addEventListener('user-login', checkLoginStatus)
window.addEventListener('user-logout', checkLoginStatus)
</script>

<style>
.app-container {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.top-header {
  background: linear-gradient(135deg, #9c0e0eff 0%, #9c0e0eff 100%);
  color: white;
  padding: 0 2rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}


.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 60px;
}

.header-left h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 400;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 4px;
  transition: background-color 0.3s;
  color: white;
}

.user-info:hover {
  background-color: rgb(104, 4, 4);
}

.login-btn {
  background-color: #9c0e0e !important;
  color: white !important;
  border: 2px solid white !important;
}

.login-btn:hover {
  background-color: #7a0b0b !important;
  border-color: white !important;
}

.main-content {
  flex: 1;
  display: flex;
}

.sidebar {
  width: 250px;
  background: linear-gradient(135deg, #faafc2ff 100%, #f06170ff 100%);
  border-right: 1px solid #e9ecef;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 1.5rem 1rem;
  background: linear-gradient(135deg, #faafc2ff 0%, #f06170ff 100%);
  color: white;
  text-align: center;
}

.sidebar-header h2 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
}

.work-menu {
  border-right: none;
  flex: 1;
}

.work-menu :deep(.el-menu-item) {
  height: 60px;
  line-height: 60px;
  font-size: 16px;
  border-left: 4px solid transparent;
  transition: all 0.3s ease;
}

.work-menu :deep(.el-menu-item.is-active) {
  background-color: #e6f7ff;
  border-left-color: #1890ff;
  color: #1890ff;
  font-weight: 600;
}

.work-menu :deep(.el-menu-item:not(.is-active):hover) {
  background-color: #f0f0f0;
  border-left-color: #ccc;
}

.content {
  flex: 1;
  padding: 0;
  background-color: #fff;
  overflow-y: auto;
  width: 100%;
  box-sizing: border-box;
}
</style>
