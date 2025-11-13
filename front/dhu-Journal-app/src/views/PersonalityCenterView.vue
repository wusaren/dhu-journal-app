<template>
  <div class="personality-center">

    <!-- 用户模板配置 -->
    <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <h3>用户模板配置</h3>
          <span class="total-count">个性化导出模板设置</span>
        </div>
      </template>
      
      <div class="config-body">
        <el-form label-position="top">
          <el-form-item label="选择配置类型">
            <el-select 
              v-model="selectedConfigType" 
              placeholder="请选择配置类型"
              @change="handleConfigTypeChange"
              style="width: 100%"
            >
              <el-option label="统计表模板配置" value="stats" />
              <el-option label="推文模板配置" value="tuiwen" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
    </el-card>

    <!-- 格式操作栏 - 根据选择显示 -->
    <div v-if="showConfigPanel">
      <el-row :gutter="20">
        <!-- 统计表格式配置 -->
        <el-col :span="12" v-if="selectedConfigType === 'stats'">
          <el-card class="upload-card">
            <template #header>
              <div class="card-header">
                <h3>统计表格式配置</h3>
                <span class="total-count">上传并确认格式</span>
              </div>
            </template>

            <div class="upload-body">
              <p class="hint">支持格式：.xlsx .xls .csv。请确保第一行为表头，包含作者、标题、页码等字段。</p>

              <div class="file-row">
                <input ref="statsFileInput" type="file" accept=".xlsx,.xls,.csv" @change="onStatsFileChange" hidden />
                <!-- 合并按钮：上传格式文件（红色主题） -->
                <el-button class="upload-btn" type="primary" size="mid" @click="triggerStatsFile" :loading="uploadingStats">上传格式文件</el-button>
                <span class="file-name" v-if="statsFileName">{{ statsFileName }}</span>
                <span class="file-empty" v-else>尚未选择文件</span>
              </div>

              <div class="actions">
                <!-- 保留确认格式按钮 -->
                <el-button :disabled="!statsFile" size="small" @click="checkStatsFormat">确认格式</el-button>
              </div>

              <div class="result" v-if="statsResult">
                <p :class="{'ok': statsResult.ok, 'warn': !statsResult.ok}">{{ statsResult.message }}</p>
                <ul v-if="statsResult.errors && statsResult.errors.length">
                  <li v-for="(e, idx) in statsResult.errors" :key="idx">{{ e }}</li>
                </ul>
              </div>
            </div>
          </el-card>

          <!-- 用户统计表模板配置 -->
          <el-card class="template-card">
            <template #header>
              <div class="card-header">
                <h3>用户统计表模板配置</h3>
                <span class="total-count">个性化导出设置</span>
              </div>
            </template>

            <div class="template-body">
              <div v-if="loadingUserConfig" class="loading">
                <p>加载用户配置中...</p>
              </div>
              <div v-else>
                <div v-if="userStatsTemplate" class="config-info">
                  <p><strong>当前配置状态：</strong>已配置</p>
                  <p><strong>列映射数量：</strong>{{ userStatsTemplate.column_mapping.length }}</p>
                  <div class="template-actions">
                    <el-button type="primary" @click="saveUserStatsTemplate">保存配置</el-button>
                  </div>
                </div>
                <div v-else class="config-info">
                  <p><strong>当前配置状态：</strong>未配置</p>
                  <p>您还没有设置用户级别的统计表模板配置。</p>
                  <div class="template-actions">
                    <el-button type="primary" @click="createDefaultStatsTemplate">创建默认配置</el-button>
                  </div>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 推文格式配置 -->
        <el-col :span="12" v-if="selectedConfigType === 'tuiwen'">
          <el-card class="upload-card">
            <template #header>
              <div class="card-header">
                <h3>推文格式配置</h3>
                <span class="total-count">上传并确认格式</span>
              </div>
            </template>

            <div class="upload-body">
              <p class="hint">支持格式：.txt .docx .doc。请确保包含推文正文与可选的摘要信息。</p>

              <div class="file-row">
                <input ref="tuiwenFileInput" type="file" accept=".txt,.md" @change="ontuiwenFileChange" hidden />
                <!-- 合并按钮：上传格式文件（红色主题） -->
                <el-button class="upload-btn" type="primary" size="mid" @click="triggertuiwenFile" :loading="uploadingtuiwen">上传格式文件</el-button>
                <span class="file-name" v-if="tuiwenFileName">{{ tuiwenFileName }}</span>
                <span class="file-empty" v-else>尚未选择文件</span>
              </div>

              <div class="actions">
                <!-- 保留确认格式按钮 -->
                <el-button :disabled="!tuiwenFile" size="small" @click="checktuiwenFormat">确认格式</el-button>
              </div>

              <div class="result" v-if="tuiwenResult">
                <p :class="{'ok': tuiwenResult.ok, 'warn': !tuiwenResult.ok}">{{ tuiwenResult.message }}</p>
                <ul v-if="tuiwenResult.errors && tuiwenResult.errors.length">
                  <li v-for="(e, idx) in tuiwenResult.errors" :key="idx">{{ e }}</li>
                </ul>
              </div>
            </div>
          </el-card>

          <!-- 用户推文模板配置 -->
          <el-card class="template-card">
            <template #header>
              <div class="card-header">
                <h3>用户推文模板配置</h3>
                <span class="total-count">个性化导出设置</span>
              </div>
            </template>

            <div class="template-body">
              <div v-if="loadingUserConfig" class="loading">
                <p>加载用户配置中...</p>
              </div>
              <div v-else>
                <div v-if="userTuiwenTemplate" class="config-info">
                  <p><strong>当前配置状态：</strong>已配置</p>
                  <p><strong>字段数量：</strong>{{ userTuiwenTemplate.fields.length }}</p>
                  <div class="template-actions">
                    <el-button type="primary" @click="saveUserTuiwenTemplate">保存配置</el-button>
                  </div>
                </div>
                <div v-else class="config-info">
                  <p><strong>当前配置状态：</strong>未配置</p>
                  <p>您还没有设置用户级别的推文模板配置。</p>
                  <div class="template-actions">
                    <el-button type="primary" @click="createDefaultTuiwenTemplate">创建默认配置</el-button>
                  </div>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { formatService, type UserTemplateConfig, type UserTuiwenTemplateConfig } from '../api/formatService'

// 配置类型状态
const selectedConfigType = ref<string>('')
const showConfigPanel = computed(() => selectedConfigType.value !== '')

// 文件与状态
const statsFile = ref<File | null>(null)
const tuiwenFile = ref<File | null>(null)
const statsFileName = ref('')
const tuiwenFileName = ref('')

const uploadingStats = ref(false)
const uploadingtuiwen = ref(false)

const statsResult = ref<{ ok: boolean; message: string; errors?: string[] } | null>(null)
const tuiwenResult = ref<{ ok: boolean; message: string; errors?: string[] } | null>(null)

const statsFileInput = ref<HTMLInputElement | null>(null)
const tuiwenFileInput = ref<HTMLInputElement | null>(null)

const triggerStatsFile = () => statsFileInput.value?.click()
const triggertuiwenFile = () => tuiwenFileInput.value?.click()

// 用户模板配置状态
const userStatsTemplate = ref<UserTemplateConfig | null>(null)
const userTuiwenTemplate = ref<UserTuiwenTemplateConfig | null>(null)
const loadingUserConfig = ref(false)

// 配置类型变更处理
const handleConfigTypeChange = async (value: string) => {
  selectedConfigType.value = value
  // 重置文件状态
  if (value === 'stats') {
    tuiwenFile.value = null
    tuiwenFileName.value = ''
    tuiwenResult.value = null
    await loadUserStatsTemplate()
  } else if (value === 'tuiwen') {
    statsFile.value = null
    statsFileName.value = ''
    statsResult.value = null
    await loadUserTuiwenTemplate()
  }
}

// 加载用户统计表模板配置
const loadUserStatsTemplate = async () => {
  loadingUserConfig.value = true
  try {
    const result = await formatService.getUserTemplate()
    if (result.success && result.has_template) {
      userStatsTemplate.value = {
        template_file_path: result.template_file_path,
        column_mapping: result.column_mapping || []
      }
    } else {
      userStatsTemplate.value = null
    }
  } catch (err: any) {
    console.error('加载用户统计表模板配置失败:', err)
    userStatsTemplate.value = null
  } finally {
    loadingUserConfig.value = false
  }
}

// 加载用户推文模板配置
const loadUserTuiwenTemplate = async () => {
  loadingUserConfig.value = true
  try {
    const result = await formatService.getUserTuiwenTemplate()
    if (result.success && result.has_template) {
      userTuiwenTemplate.value = {
        fields: result.fields || []
      }
    } else {
      userTuiwenTemplate.value = null
    }
  } catch (err: any) {
    console.error('加载用户推文模板配置失败:', err)
    userTuiwenTemplate.value = null
  } finally {
    loadingUserConfig.value = false
  }
}

// 保存用户统计表模板配置
const saveUserStatsTemplate = async () => {
  if (!userStatsTemplate.value) return
  
  try {
    const result = await formatService.saveUserTemplate(userStatsTemplate.value)
    if (result.success) {
      ElMessage.success('用户统计表模板配置保存成功')
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } catch (err: any) {
    console.error('保存用户统计表模板配置失败:', err)
    ElMessage.error(err?.response?.data?.message || '保存失败')
  }
}

// 保存用户推文模板配置
const saveUserTuiwenTemplate = async () => {
  if (!userTuiwenTemplate.value) return
  
  try {
    const result = await formatService.saveUserTuiwenTemplate(userTuiwenTemplate.value)
    if (result.success) {
      ElMessage.success('用户推文模板配置保存成功')
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } catch (err: any) {
    console.error('保存用户推文模板配置失败:', err)
    ElMessage.error(err?.response?.data?.message || '保存失败')
  }
}

// 创建默认统计表模板配置
const createDefaultStatsTemplate = () => {
  userStatsTemplate.value = {
    column_mapping: [
      { system_field: 'manuscript_id', template_header: '稿件号', order: 1 },
      { system_field: 'title', template_header: '标题', order: 2 },
      { system_field: 'authors', template_header: '作者', order: 3 },
      { system_field: 'first_author', template_header: '一作', order: 4 },
      { system_field: 'corresponding', template_header: '通讯', order: 5 }
    ]
  }
  ElMessage.success('已创建默认统计表模板配置')
}

// 创建默认推文模板配置
const createDefaultTuiwenTemplate = () => {
  userTuiwenTemplate.value = {
    fields: [
      { field: 'title', label: '标题', required: true },
      { field: 'authors', label: '作者', required: true },
      { field: 'abstract', label: '摘要', required: false },
      { field: 'doi', label: 'DOI', required: false }
    ]
  }
  ElMessage.success('已创建默认推文模板配置')
}

// 选择文件后立即上传
const onStatsFileChange = async (e: Event) => {
  const t = e.target as HTMLInputElement
  const f = t.files?.[0] || null
  statsFile.value = f
  statsFileName.value = f ? f.name : ''
  statsResult.value = null
  if (f) {
    await uploadStats()
  }
}

const ontuiwenFileChange = async (e: Event) => {
  const t = e.target as HTMLInputElement
  const f = t.files?.[0] || null
  tuiwenFile.value = f
  tuiwenFileName.value = f ? f.name : ''
  tuiwenResult.value = null
  if (f) {
    await uploadtuiwen()
  }
}

// 上传函数 - 使用封装的API服务
const uploadStats = async () => {
  if (!statsFile.value) return
  uploadingStats.value = true
  try {
    const result = await formatService.uploadStatsFormat(statsFile.value)
    ElMessage.success(result.message || '上传成功')
  } catch (err: any) {
    console.error(err)
    ElMessage.error(err?.response?.data?.message || '上传失败')
  } finally {
    uploadingStats.value = false
  }
}

const uploadtuiwen = async () => {
  if (!tuiwenFile.value) return
  uploadingtuiwen.value = true
  try {
    const result = await formatService.uploadWeiboFormat(tuiwenFile.value)
    ElMessage.success(result.message || '上传成功')
  } catch (err: any) {
    console.error(err)
    ElMessage.error(err?.response?.data?.message || '上传失败')
  } finally {
    uploadingtuiwen.value = false
  }
}

// 格式确认 - 使用封装的API服务
const checkStatsFormat = async () => {
  if (!statsFile.value) return
  const ext = statsFile.value.name.split('.').pop()?.toLowerCase()
  const allowed = ['xlsx', 'xls']
  if (!ext || !allowed.includes(ext)) {
    statsResult.value = { ok: false, message: '不支持的文件格式', errors: ['请上传 xlsx / xls 文件'] }
    return
  }
}

const checktuiwenFormat = async () => {
  if (!tuiwenFile.value) return
  const ext = tuiwenFile.value.name.split('.').pop()?.toLowerCase()
  const allowed = ['docx', 'doc']
  if (!ext || !allowed.includes(ext)) {
    tuiwenResult.value = { ok: false, message: '不支持的文件格式', errors: ['请上传 docx 或 doc 文件'] }
    return
  }
}

// 初始化加载用户配置
onMounted(async () => {
  await loadUserStatsTemplate()
  await loadUserTuiwenTemplate()
})
</script>

<style scoped>
.personality-center {
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  color: #333;
  margin-bottom: 8px;
  font-size: 24px;
  font-weight: 600;
}

.page-header p {
  color: #666;
  margin: 0;
  font-size: 14px;
}

/* 配置卡片样式 */
.config-card {
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.config-body {
  padding: 16px 0;
}

.config-card .card-header {
  background-color: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
  padding: 16px 20px;
}

.config-card .card-header h3 {
  color: #333;
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

/* 上传卡片样式 */
.upload-card {
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.upload-card:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.upload-card .card-header {
  background-color: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
  padding: 16px 20px;
}

.upload-card .card-header h3 {
  color: #333;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.total-count {
  color: #666;
  font-size: 13px;
}

.upload-body {
  padding: 20px;
}

.hint {
  color: #909399;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.5;
}

.file-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 6px;
  border: 1px dashed #dcdfe6;
}

.file-name {
  color: #303133;
  font-size: 14px;
  font-weight: 500;
}

.file-empty {
  color: #909399;
  font-size: 13px;
  font-style: italic;
}

.actions {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.result {
  margin-top: 16px;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

.result p {
  margin: 0 0 8px 0;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
}

.result p.ok {
  background: #f0f9eb;
  color: #67c23a;
  border: 1px solid #e1f3d8;
}

.result p.warn {
  background: #fff6f6;
  color: #f56c6c;
  border: 1px solid #fde2e2;
}

.result ul {
  margin: 8px 0 0 16px;
  padding: 0;
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}

.result li {
  margin-bottom: 4px;
}

/* 按钮风格保持与 JournalManagement 相近 */
.upload-btn {
  background-color: #9c0e0e;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.3s ease;
}
.upload-btn:hover {
  background-color: #7a0b0b;
  color: white;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.upload-btn:active {
  transform: translateY(0);
}

/* 确认格式按钮样式 */
.actions .el-button {
  border-radius: 6px;
  font-weight: 500;
}

/* 下拉框样式优化 */
:deep(.el-select) {
  width: 100%;
}

:deep(.el-select .el-input__inner) {
  border-radius: 6px;
  border: 1px solid #dcdfe6;
}

:deep(.el-select .el-input__inner:focus) {
  border-color: #9c0e0e;
  box-shadow: 0 0 0 2px rgba(156, 14, 14, 0.1);
}

/* 响应式处理 */
@media (max-width: 768px) {
  .personality-center {
    padding: 16px;
  }
  
  .file-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .actions {
    flex-direction: column;
    gap: 8px;
  }
  
  .upload-card .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .upload-card .card-header h3 {
    font-size: 15px;
  }
  
  .total-count {
    font-size: 12px;
  }
}

/* 模板卡片样式 */
.template-card {
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.template-card:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.template-card .card-header {
  background-color: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
  padding: 16px 20px;
}

.template-card .card-header h3 {
  color: #333;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.template-body {
  padding: 20px;
}

.journal-selection {
  margin-bottom: 20px;
}

.template-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.template-actions .el-button {
  background-color: #9c0e0e;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.template-actions .el-button:hover {
  background-color: #7a0b0b;
  color: white;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.template-actions .el-button:active {
  transform: translateY(0);
}

/* 动画效果 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
