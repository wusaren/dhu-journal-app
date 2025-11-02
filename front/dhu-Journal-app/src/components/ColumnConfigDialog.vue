<template>
  <el-dialog
    v-model="dialogVisible"
    title="配置统计表列"
    width="900px"
    @close="handleClose"
  >
    <div class="column-config-container">
      <!-- 上方：已选列（以行的形式展示，类似表格表头） -->
      <div class="selected-row-section">
        <div class="section-header">
          <h3>已选列（表头预览）</h3>
          <span class="hint-text">拖拽列可调整顺序，点击×可删除</span>
        </div>
        <div class="table-header-preview">
          <div v-if="selectedColumns.length === 0" class="empty-header">
            暂无已选列，请从下方添加
          </div>
          <div v-else class="header-row">
            <div
              v-for="(col, index) in selectedColumns"
              :key="col.key"
              class="header-cell"
              :draggable="true"
              @dragstart="handleDragStart(index, $event)"
              @dragover.prevent="handleDragOver($event)"
              @drop="handleDrop(index, $event)"
            >
              <span class="cell-number">{{ index + 1 }}</span>
              <span class="cell-label">{{ col.label }}</span>
              <el-button
                class="remove-btn"
                size="small"
                type="danger"
                text
                circle
                @click="removeColumn(index)"
              >
                ×
              </el-button>
              <div class="drag-indicator">☰</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 下方：可用列列表 -->
      <div class="available-columns-section">
        <div class="section-header">
          <h3>可用列</h3>
          <el-input
            v-model="searchText"
            placeholder="搜索列..."
            class="search-input"
            clearable
            style="width: 200px;"
          />
        </div>
        <div class="columns-list">
          <div
            v-for="col in filteredAvailableColumns"
            :key="col.key"
            class="column-item"
            :class="{ 'is-selected': isSelected(col) }"
            @click="handleColumnToggle(col)"
          >
            <el-checkbox
              :model-value="isSelected(col)"
              @change.stop="handleColumnToggle(col)"
            >
              {{ col.label }}
            </el-checkbox>
            <span class="category-tag">{{ col.category }}</span>
            <el-button
              v-if="!isSelected(col)"
              size="small"
              type="primary"
              text
              @click.stop="handleColumnToggle(col)"
            >
              添加
            </el-button>
          </div>
        </div>
      </div>
      
      <!-- 底部操作按钮 -->
      <div class="dialog-actions">
        <el-button @click="resetToDefault">恢复默认</el-button>
        <el-button type="primary" @click="handleConfirm">确定</el-button>
        <el-button @click="handleClose">取消</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { journalService, type ColumnDefinition, type ColumnConfig } from '@/api/journalService'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'confirm': [columns: ColumnConfig[]]
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const availableColumns = ref<ColumnDefinition[]>([])
const searchText = ref('')
const selectedColumns = ref<Array<{ key: string; label: string; order: number }>>([])
const dragIndex = ref<number | null>(null)

// 默认配置
const defaultColumns: ColumnConfig[] = [
  { key: 'manuscript_id', order: 1 },
  { key: 'pdf_pages', order: 2 },
  { key: 'first_author', order: 3 },
  { key: 'corresponding', order: 4 },
  { key: 'issue', order: 5 },
  { key: 'is_dhu', order: 6 },
]

// 过滤可用列
const filteredAvailableColumns = computed(() => {
  const text = searchText.value.toLowerCase()
  return availableColumns.value.filter(col => 
    col.label.toLowerCase().includes(text) ||
    col.key.toLowerCase().includes(text) ||
    col.category.includes(text)
  )
})

// 检查列是否已选中
const isSelected = (col: ColumnDefinition) => {
  return selectedColumns.value.some(sc => sc.key === col.key)
}

// 加载可用列
const loadColumns = async () => {
  try {
    const res = await journalService.getAvailableColumns()
    if (res.success) {
      availableColumns.value = res.columns
      // 如果没有已选列，初始化默认配置
      if (selectedColumns.value.length === 0) {
        resetToDefault()
      }
    }
  } catch (error) {
    console.error('加载可用列失败:', error)
    ElMessage.error('加载可用列失败')
  }
}

// 切换列选择
const handleColumnToggle = (col: ColumnDefinition) => {
  const index = selectedColumns.value.findIndex(sc => sc.key === col.key)
  
  if (index === -1) {
    // 添加到已选列
    selectedColumns.value.push({
      key: col.key,
      label: col.label,
      order: selectedColumns.value.length + 1
    })
  } else {
    // 从已选列移除
    selectedColumns.value.splice(index, 1)
    // 重新排序
    updateOrders()
  }
}

// 移除列
const removeColumn = (index: number) => {
  selectedColumns.value.splice(index, 1)
  updateOrders()
}

// 上移
const moveUp = (index: number) => {
  if (index > 0) {
    const temp = selectedColumns.value[index]
    selectedColumns.value[index] = selectedColumns.value[index - 1]
    selectedColumns.value[index - 1] = temp
    updateOrders()
  }
}

// 下移
const moveDown = (index: number) => {
  if (index < selectedColumns.value.length - 1) {
    const temp = selectedColumns.value[index]
    selectedColumns.value[index] = selectedColumns.value[index + 1]
    selectedColumns.value[index + 1] = temp
    updateOrders()
  }
}

// 更新order
const updateOrders = () => {
  selectedColumns.value.forEach((col, index) => {
    col.order = index + 1
  })
}

// 拖拽相关
const handleDragStart = (index: number, event: DragEvent) => {
  dragIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
  }
}

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const handleDrop = (dropIndex: number, event: DragEvent) => {
  event.preventDefault()
  if (dragIndex.value === null || dragIndex.value === dropIndex) {
    return
  }
  
  const draggedItem = selectedColumns.value[dragIndex.value]
  selectedColumns.value.splice(dragIndex.value, 1)
  selectedColumns.value.splice(dropIndex, 0, draggedItem)
  updateOrders()
  dragIndex.value = null
}

// 恢复默认
const resetToDefault = () => {
  selectedColumns.value = defaultColumns.map(col => {
    const colDef = availableColumns.value.find(ac => ac.key === col.key)
    return {
      key: col.key,
      label: colDef?.label || col.key,
      order: col.order
    }
  })
  updateOrders()
}

// 确认
const handleConfirm = () => {
  if (selectedColumns.value.length === 0) {
    ElMessage.warning('请至少选择一列')
    return
  }
  
  const columns: ColumnConfig[] = selectedColumns.value.map(col => ({
    key: col.key,
    order: col.order
  }))
  
  emit('confirm', columns)
  dialogVisible.value = false
}

// 关闭
const handleClose = () => {
  dialogVisible.value = false
}

// 监听对话框打开，加载数据
watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    loadColumns()
  }
})
</script>

<style scoped>
.column-config-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 500px;
}

/* 已选列区域（表头预览） */
.selected-row-section {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 15px;
  background-color: #fafafa;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.hint-text {
  font-size: 12px;
  color: #909399;
}

.table-header-preview {
  min-height: 80px;
  border: 2px dashed #dcdfe6;
  border-radius: 4px;
  padding: 10px;
  background-color: white;
}

.empty-header {
  text-align: center;
  color: #909399;
  padding: 30px 0;
  font-size: 14px;
}

.header-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.header-cell {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 4px;
  cursor: move;
  min-width: 100px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.2s;
  user-select: none;
}

.header-cell:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.header-cell[draggable="true"]:active {
  opacity: 0.7;
  transform: scale(1.05);
}

.cell-number {
  font-size: 12px;
  background: rgba(255, 255, 255, 0.3);
  padding: 2px 6px;
  border-radius: 3px;
  font-weight: bold;
}

.cell-label {
  flex: 1;
  font-weight: 500;
  font-size: 14px;
}

.remove-btn {
  color: white !important;
  padding: 0 !important;
  min-height: auto !important;
  font-size: 18px !important;
  width: 20px !important;
  height: 20px !important;
}

.remove-btn:hover {
  background-color: rgba(255, 255, 255, 0.2) !important;
}

.drag-indicator {
  opacity: 0.7;
  font-size: 12px;
  cursor: move;
}

/* 可用列区域 */
.available-columns-section {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 15px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.columns-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
  margin-top: 15px;
  max-height: 250px;
  overflow-y: auto;
  padding: 5px;
}

.column-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  background-color: white;
}

.column-item:hover {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.column-item.is-selected {
  border-color: #67c23a;
  background-color: #f0f9ff;
}

.column-item.is-selected:hover {
  border-color: #67c23a;
  background-color: #e1f3ff;
}

.category-tag {
  font-size: 11px;
  color: #909399;
  padding: 2px 6px;
  background-color: #f0f2f5;
  border-radius: 3px;
  margin-left: auto;
  margin-right: 8px;
}

/* 底部操作按钮 */
.dialog-actions {
  margin-top: 10px;
  padding-top: 15px;
  border-top: 1px solid #dcdfe6;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

/* 滚动条样式 */
.columns-list::-webkit-scrollbar {
  width: 6px;
}

.columns-list::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.columns-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.columns-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>

