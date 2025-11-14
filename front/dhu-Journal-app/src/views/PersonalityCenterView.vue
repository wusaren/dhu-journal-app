<template>
  <div class="personality-center">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>个人中心</h1>
      <p>管理您的个性化设置和账户信息</p>
    </div>

    <!-- 用户信息卡片 -->
    <el-card class="user-info-card" v-if="userInfo">
      <div class="user-info-content">
        <div class="user-avatar">
          <div class="avatar-icon">👤</div>
        </div>
        <div class="user-details">
          <h3 class="username">{{ userInfo.username }}</h3>
          <p class="email">{{ userInfo.email }}</p>
        </div>
      </div>
    </el-card>

    <!-- 功能卡片区域 -->
    <div class="cards-container">
      <!-- 模板配置卡片 -->
      <el-card class="function-card" @click="openTemplateConfig">
        <div class="card-content">
          <div class="card-icon">📊</div>
          <div class="card-info">
            <h3>模板配置</h3>
            <p>配置统计表和推文的导出模板格式</p>
          </div>
          <div class="card-arrow">→</div>
        </div>
      </el-card>

      <!-- 密码设置卡片 -->
      <el-card class="function-card" @click="openPasswordSettings">
        <div class="card-content">
          <div class="card-icon">🔒</div>
          <div class="card-info">
            <h3>密码设置</h3>
            <p>修改您的登录密码</p>
          </div>
          <div class="card-arrow">→</div>
        </div>
      </el-card>
    </div>

    <!-- 模板配置对话框 -->
    <TemplateConfigDialog 
      v-model="showTemplateDialog"
      @saved="handleTemplateSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import TemplateConfigDialog from '../components/TemplateConfigDialog.vue'
import { authService, type UserDetail } from '../api/authService'

// 用户信息
const userInfo = ref<UserDetail | null>(null)

// 模板配置对话框状态
const showTemplateDialog = ref(false)

// 加载用户信息
const loadUserInfo = async () => {
  try {
    userInfo.value = await authService.getCurrentUserDetail()
  } catch (error: any) {
    ElMessage.error(error.message || '获取用户信息失败')
  }
}

// 打开模板配置对话框
const openTemplateConfig = () => {
  showTemplateDialog.value = true
}

// 打开密码设置
const openPasswordSettings = () => {
  ElMessage.info('密码设置功能开发中...')
}

// 模板配置保存后的处理
const handleTemplateSaved = () => {
  ElMessage.success('模板配置已保存')
}

// 组件挂载时加载用户信息
onMounted(() => {
  loadUserInfo()
})
</script>

<style scoped>
.personality-center {
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

.page-header {
  margin-bottom: 40px;
  text-align: center;
}

.page-header h1 {
  color: #333;
  margin-bottom: 8px;
  font-size: 28px;
  font-weight: 600;
}

.page-header p {
  color: #666;
  margin: 0;
  font-size: 16px;
}

/* 用户信息卡片样式 */
.user-info-card {
  max-width: 600px;
  margin: 0 auto 40px auto;
  border-radius: 12px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.user-info-content {
  display: flex;
  align-items: center;
  padding: 24px;
}

.user-avatar {
  margin-right: 20px;
  flex-shrink: 0;
}

.avatar-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background-color: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #666;
}

.user-details {
  flex: 1;
}

.username {
  color: #333;
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
}

.email {
  color: #666;
  margin: 0;
  font-size: 16px;
}

/* 功能卡片容器 */
.cards-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
  max-width: 800px;
  margin: 0 auto;
}

/* 功能卡片样式 */
.function-card {
  cursor: pointer;
  border-radius: 12px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
  height: 120px;
}

.function-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  border-color: #9c0e0e;
}

.card-content {
  display: flex;
  align-items: center;
  padding: 24px;
  height: 100%;
}

.card-icon {
  font-size: 36px;
  margin-right: 20px;
  flex-shrink: 0;
}

.card-info {
  flex: 1;
}

.card-info h3 {
  color: #333;
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
}

.card-info p {
  color: #666;
  margin: 0;
  font-size: 14px;
  line-height: 1.4;
}

.card-arrow {
  color: #9c0e0e;
  font-size: 20px;
  font-weight: bold;
  margin-left: 16px;
  transition: transform 0.3s ease;
}

.function-card:hover .card-arrow {
  transform: translateX(4px);
}

/* 响应式处理 */
@media (max-width: 768px) {
  .personality-center {
    padding: 16px;
  }
  
  .user-info-card {
    margin-bottom: 32px;
  }
  
  .user-info-content {
    padding: 20px;
  }
  
  .avatar-icon {
    width: 50px;
    height: 50px;
    font-size: 24px;
  }
  
  .username {
    font-size: 18px;
  }
  
  .email {
    font-size: 14px;
  }
  
  .cards-container {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .page-header h1 {
    font-size: 24px;
  }
  
  .page-header p {
    font-size: 14px;
  }
  
  .function-card {
    height: 100px;
  }
  
  .card-content {
    padding: 20px;
  }
  
  .card-icon {
    font-size: 28px;
    margin-right: 16px;
  }
  
  .card-info h3 {
    font-size: 16px;
  }
  
  .card-info p {
    font-size: 13px;
  }
}
</style>
