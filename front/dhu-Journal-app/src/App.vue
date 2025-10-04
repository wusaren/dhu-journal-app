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
              管理员
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
          <el-menu-item index="/paper-management">
            <span>论文管理</span>
          </el-menu-item>
          <el-menu-item index="/journal-management">
            <span>期刊管理</span>
          </el-menu-item>
          <el-menu-item index="/preliminary-review">
            <span>初审系统</span>
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
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()

const isLoggedIn = ref(false) // 模拟登录状态
const currentRoute = computed(() => route.path)

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
    isLoggedIn.value = false
    ElMessage.success('退出登录成功')
    router.push('/')
  } catch {
    ElMessage.info('取消退出登录')
  }
}

// 模拟登录状态管理 - 实际项目中应该使用Pinia或Vuex
// 这里简单模拟，实际应该根据登录接口返回的状态来设置
if (localStorage.getItem('isLoggedIn') === 'true') {
  isLoggedIn.value = true
}
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
}

.user-info:hover {
  background-color: rgba(255, 255, 255, 0.1);
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
