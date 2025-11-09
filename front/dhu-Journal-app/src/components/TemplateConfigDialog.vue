<template>
  <el-dialog
    v-model="dialogVisible"
    title="配置统计表模板"
    width="1000px"
    @close="handleClose"
  >
    <!-- 上传模板区域 -->
    <div v-if="!hasTemplate" class="upload-section">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :on-change="handleFileChange"
        :file-list="fileList"
        accept=".xlsx,.xls"
        drag
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将Excel模板文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            只支持Excel文件（.xlsx, .xls），请确保第一行包含表头
          </div>
        </template>
      </el-upload>
      
      <div class="upload-actions" v-if="fileList.length > 0">
        <el-button type="primary" @click="handleUpload">上传并识别</el-button>
        <el-button @click="handleCancelUpload">取消</el-button>
      </div>
    </div>

    <!-- 表头配置区域 -->
    <div v-if="hasTemplate && headers.length > 0" class="config-section">
      <div class="section-header">
        <h3>识别到的表头</h3>
        <div class="header-actions">
          <el-button size="small" @click="handleAddField">添加字段</el-button>
          <el-button size="small" type="danger" @click="handleDeleteTemplate">删除模板</el-button>
        </div>
      </div>

      <!-- 表头列表 -->
      <div class="headers-list">
        <div
          v-for="(header, index) in headers"
          :key="index"
          class="header-item"
          :class="{ 'matched': header.matched, 'custom': header.is_custom }"
        >
          <div class="header-order">{{ index + 1 }}</div>
          <div class="header-content">
            <div class="header-name">{{ header.template_header }}</div>
            <div class="header-mapping" v-if="header.matched">
              <el-tag size="small" type="success">已匹配: {{ header.system_label }}</el-tag>
            </div>
            <div class="header-mapping" v-else-if="header.is_custom">
              <el-tag size="small" type="info">自定义字段</el-tag>
            </div>
            <div class="header-mapping" v-else>
              <el-tag size="small" type="warning">未匹配</el-tag>
              <el-select
                v-model="header.system_key"
                size="small"
                placeholder="选择系统字段"
                style="width: 200px; margin-left: 10px"
                @change="handleMappingChange(header, $event)"
              >
                <el-option
                  v-for="field in getAvailableFieldsForHeader(header)"
                  :key="field.key"
                  :label="field.label"
                  :value="field.key"
                />
              </el-select>
            </div>
          </div>
          <div class="header-actions">
            <el-button
              size="small"
              text
              type="danger"
              @click="handleRemoveHeader(index)"
            >
              删除
            </el-button>
            <div class="drag-handle">☰</div>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="config-actions">
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" @click="handleSave">保存配置</el-button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-overlay">
      <el-icon class="is-loading"><loading /></el-icon>
      <span>处理中...</span>
    </div>
  </el-dialog>

  <!-- 添加字段对话框 -->
  <el-dialog
    v-model="showAddFieldDialog"
    title="添加系统字段"
    width="500px"
  >
    <el-select
      v-model="selectedFieldKey"
      placeholder="选择要添加的字段"
      style="width: 100%"
    >
      <el-option
        v-for="field in filteredAvailableFields"
        :key="field.key"
        :label="field.label"
        :value="field.key"
      />
    </el-select>
    <template #footer>
      <el-button @click="showAddFieldDialog = false">取消</el-button>
      <el-button type="primary" @click="handleConfirmAddField">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Loading } from '@element-plus/icons-vue'
import { journalService } from '@/api/journalService'
import type { Journal } from '@/api/journalService'

interface HeaderMapping {
  template_header: string
  system_key: string | null
  system_label: string | null
  order: number
  is_custom: boolean
  matched: boolean
}

interface SystemField {
  key: string
  label: string
  keywords: string[]
}

const props = defineProps<{
  modelValue: boolean
  journal: Journal | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'saved': []
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const hasTemplate = ref(false)
const headers = ref<HeaderMapping[]>([])
const fileList = ref<any[]>([])
const uploadRef = ref()
const loading = ref(false)
const showAddFieldDialog = ref(false)
const selectedFieldKey = ref('')
const availableFields = ref<SystemField[]>([])

// 过滤后的可用字段列表（排除已经添加的字段）
const filteredAvailableFields = computed(() => {
  // 获取已经使用的系统字段key列表
  const usedKeys = new Set(
    headers.value
      .filter(h => h.system_key !== null)
      .map(h => h.system_key!)
  )
  
  // 过滤掉已经使用的字段
  return availableFields.value.filter(field => !usedKeys.has(field.key))
})

// 加载可用系统字段
const loadAvailableFields = async () => {
  try {
    const response = await journalService.getSystemFields()
    if (response.success) {
      availableFields.value = response.fields
    }
  } catch (error: any) {
    console.error('加载系统字段失败:', error)
  }
}

// 加载模板配置
const loadTemplate = async () => {
  if (!props.journal) return
  
  try {
    loading.value = true
    const response = await journalService.getTemplateHeaders(props.journal.id)
    
    if (response.success && response.has_template) {
      hasTemplate.value = true
      headers.value = response.headers || []
    } else {
      hasTemplate.value = false
      headers.value = []
    }
  } catch (error: any) {
    console.error('加载模板失败:', error)
    hasTemplate.value = false
    headers.value = []
  } finally {
    loading.value = false
  }
}

// 文件选择变化
const handleFileChange = (file: any) => {
  fileList.value = [file]
}

// 取消上传
const handleCancelUpload = () => {
  fileList.value = []
}

// 上传模板
const handleUpload = async () => {
  if (!props.journal || fileList.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }

  try {
    loading.value = true
    const formData = new FormData()
    formData.append('file', fileList.value[0].raw)

    const response = await journalService.uploadTemplate(props.journal.id, formData)
    
    if (response.success) {
      ElMessage.success('模板上传成功，已识别表头')
      headers.value = response.headers || []
      hasTemplate.value = true
      fileList.value = []
    } else {
      ElMessage.error(response.message || '上传失败')
    }
  } catch (error: any) {
    console.error('上传模板失败:', error)
    ElMessage.error(error.message || '上传失败')
  } finally {
    loading.value = false
  }
}

// 映射变化
const handleMappingChange = (header: HeaderMapping, systemKey: string) => {
  const field = availableFields.value.find(f => f.key === systemKey)
  if (field) {
    header.system_key = systemKey
    header.system_label = field.label
    header.matched = true
    header.is_custom = false
  }
}

// 获取某个表头可以选择的系统字段列表（排除已使用的字段，但包括当前表头已选择的字段）
const getAvailableFieldsForHeader = (currentHeader: HeaderMapping) => {
  // 获取已经使用的系统字段key列表（排除当前表头）
  const usedKeys = new Set(
    headers.value
      .filter(h => h.system_key !== null && h !== currentHeader)
      .map(h => h.system_key!)
  )
  
  // 过滤掉已经使用的字段（但保留当前表头已选择的字段）
  return availableFields.value.filter(field => 
    !usedKeys.has(field.key) || field.key === currentHeader.system_key
  )
}

// 删除表头
const handleRemoveHeader = (index: number) => {
  headers.value.splice(index, 1)
  // 更新order
  headers.value.forEach((h, i) => {
    h.order = i + 1
  })
}

// 添加字段
const handleAddField = () => {
  showAddFieldDialog.value = true
  selectedFieldKey.value = ''
}

// 确认添加字段
const handleConfirmAddField = () => {
  if (!selectedFieldKey.value) {
    ElMessage.warning('请选择要添加的字段')
    return
  }

  const field = availableFields.value.find(f => f.key === selectedFieldKey.value)
  if (field) {
    const newHeader: HeaderMapping = {
      template_header: field.label,
      system_key: field.key,
      system_label: field.label,
      order: headers.value.length + 1,
      is_custom: false,
      matched: true
    }
    headers.value.push(newHeader)
    showAddFieldDialog.value = false
    selectedFieldKey.value = ''
  }
}

// 删除模板
const handleDeleteTemplate = async () => {
  if (!props.journal) return
  
  try {
    await ElMessageBox.confirm(
      '确定要删除模板吗？删除后需要重新上传模板才能生成统计表。',
      '删除模板',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    loading.value = true
    const response = await journalService.deleteTemplate(props.journal.id)
    
    if (response.success) {
      ElMessage.success('模板删除成功')
      // 重置状态
      hasTemplate.value = false
      headers.value = []
      fileList.value = []
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error: any) {
    if (error.message === 'cancel' || error === 'cancel') {
      // 用户取消，不做任何操作
      return
    }
    console.error('删除模板失败:', error)
    ElMessage.error(error.message || '删除失败')
  } finally {
    loading.value = false
  }
}

// 保存配置
const handleSave = async () => {
  if (!props.journal) return

  try {
    loading.value = true
    const response = await journalService.saveTemplateMapping(props.journal.id, headers.value)
    
    if (response.success) {
      ElMessage.success('配置保存成功')
      emit('saved')
      dialogVisible.value = false
    } else {
      ElMessage.error(response.message || '保存失败')
    }
  } catch (error: any) {
    console.error('保存配置失败:', error)
    ElMessage.error(error.message || '保存失败')
  } finally {
    loading.value = false
  }
}

// 取消
const handleCancel = () => {
  dialogVisible.value = false
}

// 关闭对话框
const handleClose = () => {
  fileList.value = []
  hasTemplate.value = false
  headers.value = []
}

// 监听对话框打开
watch(() => props.modelValue, (newVal) => {
  if (newVal && props.journal) {
    loadAvailableFields()
    loadTemplate()
  }
})
</script>

<style scoped>
.upload-section {
  padding: 20px;
}

.upload-actions {
  margin-top: 20px;
  text-align: right;
}

.config-section {
  padding: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.headers-list {
  max-height: 500px;
  overflow-y: auto;
}

.header-item {
  display: flex;
  align-items: center;
  padding: 12px;
  margin-bottom: 10px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
}

.header-item.matched {
  border-color: #67c23a;
  background: #f0f9ff;
}

.header-item.custom {
  border-color: #909399;
  background: #f5f7fa;
}

.header-order {
  width: 30px;
  text-align: center;
  font-weight: bold;
  color: #909399;
}

.header-content {
  flex: 1;
  margin-left: 15px;
}

.header-name {
  font-weight: 500;
  margin-bottom: 5px;
}

.header-mapping {
  display: flex;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.drag-handle {
  cursor: move;
  color: #909399;
}

.config-actions {
  margin-top: 20px;
  text-align: right;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
</style>

