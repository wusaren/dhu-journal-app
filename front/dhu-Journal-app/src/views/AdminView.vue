<template>
  <div class="admin-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>用户中心</h1>
      <p>用户和角色管理面板</p>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon user-icon">
              <i class="el-icon-user"></i>
            </div>
            <div class="stat-info">
              <div class="stat-number">{{ stats.total_users || 0 }}</div>
              <div class="stat-label">总用户数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon active-icon">
              <i class="el-icon-success"></i>
            </div>
            <div class="stat-info">
              <div class="stat-number">{{ stats.active_users || 0 }}</div>
              <div class="stat-label">活跃用户</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon role-icon">
              <i class="el-icon-s-custom"></i>
            </div>
            <div class="stat-info">
              <div class="stat-number">{{ stats.total_roles || 0 }}</div>
              <div class="stat-label">角色数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon admin-icon">
              <i class="el-icon-s-tools"></i>
            </div>
            <div class="stat-info">
              <div class="stat-number">{{ adminCount || 0 }}</div>
              <div class="stat-label">管理员</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 标签页 -->
    <el-tabs v-model="activeTab" type="card" class="admin-tabs">
      <!-- 用户管理标签页 -->
      <el-tab-pane label="用户管理" name="users">
        <div class="tab-content">
          <!-- 用户列表 -->
          <el-card class="content-card">
            <template #header>
              <div class="card-header">
                <h3>用户列表</h3>
                <div class="header-actions">
                  <el-button type="primary" size="small" @click="refreshUsers">
                    <i class="el-icon-refresh"></i>
                    刷新
                  </el-button>
                </div>
              </div>
            </template>

            <!-- 用户表格 -->
            <el-table 
              :data="users" 
              v-loading="loadingUsers"
              style="width: 100%"
            >
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="username" label="用户名" width="120" />
              <el-table-column prop="email" label="邮箱" width="200" />
              <el-table-column prop="roles" label="角色" width="150">
                <template #default="scope">
                  <el-tag 
                    v-for="role in scope.row.roles" 
                    :key="role"
                    :type="getRoleTagType(role)"
                    size="small"
                    class="role-tag"
                  >
                    {{ role }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="active" label="状态" width="100">
                <template #default="scope">
                  <el-tag 
                    :type="scope.row.active ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ scope.row.active ? '启用' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="创建时间" width="180" />
              <el-table-column label="操作" width="200">
                <template #default="scope">
                  <el-button 
                    size="small" 
                    type="primary" 
                    @click="showRoleDialog(scope.row)"
                  >
                    管理角色
                  </el-button>
                  <el-button 
                    size="small" 
                    :type="scope.row.active ? 'warning' : 'success'"
                    @click="toggleUserActive(scope.row)"
                  >
                    {{ scope.row.active ? '禁用' : '启用' }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- 分页 -->
            <div class="pagination">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :page-sizes="[10, 20, 50, 100]"
                :small="true"
                :background="true"
                layout="total, sizes, prev, pager, next, jumper"
                :total="totalUsers"
                @size-change="handleSizeChange"
                @current-change="handleCurrentChange"
              />
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- 角色管理标签页 -->
      <el-tab-pane label="角色管理" name="roles">
        <div class="tab-content">
          <!-- 角色列表 -->
          <el-card class="content-card">
            <template #header>
              <div class="card-header">
                <h3>角色列表</h3>
                <div class="header-actions">
                  <el-button type="primary" size="small" @click="showCreateRoleDialog">
                    <i class="el-icon-plus"></i>
                    创建角色
                  </el-button>
                  <el-button type="default" size="small" @click="refreshRoles">
                    <i class="el-icon-refresh"></i>
                    刷新
                  </el-button>
                </div>
              </div>
            </template>

            <!-- 角色表格 -->
            <el-table 
              :data="roles" 
              v-loading="loadingRoles"
              style="width: 100%"
            >
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="角色名" width="120" />
              <el-table-column prop="description" label="描述" />
              <el-table-column prop="user_count" label="用户数" width="100">
                <template #default="scope">
                  <el-tag size="small">
                    {{ scope.row.user_count }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="scope">
                  <el-button 
                    size="small" 
                    type="danger" 
                    @click="deleteRole(scope.row)"
                    :disabled="scope.row.user_count > 0"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 角色管理对话框 -->
    <el-dialog
      v-model="roleDialogVisible"
      :title="`管理用户角色 - ${selectedUser?.username}`"
      width="500px"
    >
      <div class="role-dialog-content">
        <p>当前角色：</p>
        <div class="current-roles">
          <el-tag 
            v-for="role in selectedUser?.roles || []" 
            :key="role"
            :type="getRoleTagType(role)"
            closable
            @close="removeRole(role)"
            class="role-tag"
          >
            {{ role }}
          </el-tag>
        </div>
        
        <el-divider />
        
        <p>添加角色：</p>
        <div class="add-role-section">
          <el-select 
            v-model="newRole" 
            placeholder="选择角色"
            style="width: 200px; margin-right: 10px;"
          >
            <el-option
              v-for="role in availableRoles"
              :key="role.name"
              :label="role.name"
              :value="role.name"
            />
          </el-select>
          <el-button 
            type="primary" 
            @click="addRole"
            :disabled="!newRole"
          >
            添加
          </el-button>
        </div>
      </div>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="roleDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="roleDialogVisible = false">
            完成
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 创建角色对话框 -->
    <el-dialog
      v-model="createRoleDialogVisible"
      title="创建新角色"
      width="400px"
    >
      <el-form :model="newRoleForm" label-width="80px">
        <el-form-item label="角色名">
          <el-input v-model="newRoleForm.name" placeholder="输入角色名" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input 
            v-model="newRoleForm.description" 
            type="textarea" 
            :rows="3"
            placeholder="输入角色描述"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="createRoleDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="createRole">
            创建
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import apiClient from '../api/axios'

// 响应式数据
const activeTab = ref('users')
const loadingUsers = ref(false)
const loadingRoles = ref(false)
const users = ref([])
const roles = ref([])
const stats = ref({})
const currentPage = ref(1)
const pageSize = ref(10)
const totalUsers = ref(0)

// 对话框相关
const roleDialogVisible = ref(false)
const createRoleDialogVisible = ref(false)
const selectedUser = ref(null)
const newRole = ref('')
const newRoleForm = ref({
  name: '',
  description: ''
})

// 计算属性
const availableRoles = computed(() => {
  return roles.value.map(role => ({
    name: role.name,
    description: role.description
  }))
})

const adminCount = computed(() => {
  return users.value.filter(user => user.roles.includes('admin')).length
})

// 方法
const getRoleTagType = (role: string) => {
  const typeMap: Record<string, string> = {
    'admin': 'danger',
    'editor': 'warning',
    'viewer': 'success'
  }
  return typeMap[role] || 'info'
}

const loadStats = async () => {
  try {
    const response = await apiClient.get('/admin/stats')
    stats.value = response
  } catch (error) {
    console.error('加载统计信息失败:', error)
  }
}

const loadUsers = async () => {
  loadingUsers.value = true
  try {
    const response = await apiClient.get('/admin/users', {
      params: {
        page: currentPage.value,
        per_page: pageSize.value
      }
    })
    users.value = response.users
    totalUsers.value = response.total
  } catch (error) {
    console.error('加载用户列表失败:', error)
    ElMessage.error('加载用户列表失败')
  } finally {
    loadingUsers.value = false
  }
}

const loadRoles = async () => {
  loadingRoles.value = true
  try {
    const response = await apiClient.get('/admin/roles')
    roles.value = response.roles
  } catch (error) {
    console.error('加载角色列表失败:', error)
    ElMessage.error('加载角色列表失败')
  } finally {
    loadingRoles.value = false
  }
}

const refreshUsers = () => {
  loadUsers()
  loadStats()
}

const refreshRoles = () => {
  loadRoles()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  loadUsers()
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
  loadUsers()
}

const showRoleDialog = (user: any) => {
  selectedUser.value = user
  newRole.value = ''
  roleDialogVisible.value = true
}

const addRole = async () => {
  if (!selectedUser.value || !newRole.value) return
  
  try {
    await apiClient.post(`/admin/users/${selectedUser.value.id}/roles`, {
      role_name: newRole.value
    })
    ElMessage.success('角色添加成功')
    newRole.value = ''
    loadUsers()
  } catch (error) {
    console.error('添加角色失败:', error)
    ElMessage.error('添加角色失败')
  }
}

const removeRole = async (roleName: string) => {
  if (!selectedUser.value) return
  
  try {
    await apiClient.delete(`/admin/users/${selectedUser.value.id}/roles`, {
      data: { role_name: roleName }
    })
    ElMessage.success('角色移除成功')
    loadUsers()
  } catch (error) {
    console.error('移除角色失败:', error)
    ElMessage.error('移除角色失败')
  }
}

const toggleUserActive = async (user: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要${user.active ? '禁用' : '启用'}用户 "${user.username}" 吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await apiClient.put(`/admin/users/${user.id}/activate`)
    ElMessage.success(`用户${user.active ? '禁用' : '启用'}成功`)
    loadUsers()
    loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('操作用户状态失败:', error)
      ElMessage.error('操作失败')
    }
  }
}

const showCreateRoleDialog = () => {
  newRoleForm.value = { name: '', description: '' }
  createRoleDialogVisible.value = true
}

const createRole = async () => {
  if (!newRoleForm.value.name.trim()) {
    ElMessage.warning('请输入角色名')
    return
  }
  
  try {
    await apiClient.post('/admin/roles', newRoleForm.value)
    ElMessage.success('角色创建成功')
    createRoleDialogVisible.value = false
    loadRoles()
    loadStats()
  } catch (error) {
    console.error('创建角色失败:', error)
    ElMessage.error('创建角色失败')
  }
}

const deleteRole = async (role: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除角色 "${role.name}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await apiClient.delete(`/admin/roles/${role.id}`)
    ElMessage.success('角色删除成功')
    loadRoles()
    loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除角色失败:', error)
      ElMessage.error('删除角色失败')
    }
  }
}

// 生命周期
onMounted(() => {
  loadStats()
  loadUsers()
  loadRoles()
})
</script>

<style scoped>
.admin-container {
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

.page-header {
  margin-bottom: 30px;
}

.page-header h1 {
  color: #333;
  margin-bottom: 8px;
  font-size: 28px;
}

.page-header p {
  color: #666;
  margin: 0;
  font-size: 16px;
}

.stats-row {
  margin-bottom: 30px;
}

.stat-card {
  height: 120px;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20px;
  font-size: 24px;
  color: white;
}

.user-icon {
  background-color: #409EFF;
}

.active-icon {
  background-color: #67C23A;
}

.role-icon {
  background-color: #E6A23C;
}

.admin-icon {
  background-color: #F56C6C;
}

.stat-info {
  flex: 1;
}

.stat-number {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.admin-tabs {
  margin-top: 20px;
}

.tab-content {
  padding: 0;
}

.content-card {
  margin-bottom: 20px;
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

.header-actions {
  display: flex;
  gap: 10px;
}

.role-tag {
  margin-right: 5px;
  margin-bottom: 5px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.role-dialog-content {
  padding: 10px 0;
}

.current-roles {
  margin: 10px 0;
  min-height: 40px;
}

.add-role-section {
  display: flex;
  align-items: center;
  margin-top: 10px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 翻页组件当前页码自定义颜色 */
:deep(.el-pagination.is-background .el-pager li.is-active) {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

:deep(.el-pagination.is-background .el-pager li.is-active:hover) {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
  color: white !important;
}

/* 标签页激活状态 */
:deep(.el-tabs__item.is-active) {
  color: #b62020ff !important;
}

:deep(.el-tabs__active-bar) {
  background-color: #b62020ff !important;
}

/* 按钮样式 */
:deep(.el-button--primary) {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
}

:deep(.el-button--primary:hover) {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}
</style>