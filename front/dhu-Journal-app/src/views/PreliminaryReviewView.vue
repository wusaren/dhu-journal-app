<template>
  <el-config-provider :locale="zhCn">
    <div class="preliminary-review">

    <!-- 待审核论文筛选区域 -->
    <el-card class="filter-card">
      <el-form :model="pendingSearchForm" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="提交日期">
              <el-date-picker
                v-model="pendingSearchForm.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="关键词">
              <el-input v-model="pendingSearchKeyword" placeholder="输入关键词搜索" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item>
              <el-button class="search-btn" type="primary" @click="handlePendingSearch">搜索</el-button>
              <el-button class="reset-btn" @click="resetPendingSearch">重置</el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 待审核论文列表 -->
    <el-card class="content-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <h3>待审核论文列表</h3>
            <span class="total-count">共 {{ filteredPendingList.length }} 篇论文</span>
          </div>
          <div class="header-right">
            <el-button class="add-paper-btn" type="primary" size="small" @click="showAddDialog = true">添加论文</el-button>
          </div>
        </div>
      </template>

      <el-table :data="paginatedPendingList" style="width: 100%" @selection-change="handlePendingSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="title" label="论文标题" width="300" />
        <el-table-column prop="submitDate" label="提交日期" width="120" />
        <el-table-column label="操作" width="500">
          <template #default="scope">
            <el-button class="view-btn" size="small" @click="openOriginalDoc(scope.row)">
              原文档
            </el-button>
            <el-button class="audit-btn" size="small" @click="handleReview(scope.row)">
              审核
            </el-button>
            <el-button class="term-detect-btn" size="small" @click="handleTermDetect(scope.row)">
              术语检测
            </el-button>
            <el-button
              v-if="scope.row.formatCheckResult?.success"
              class="report-btn"
              size="small"
              @click="openReportDoc(scope.row)"
            >
              检测报告
            </el-button>
            <el-button
              v-if="scope.row.formatCheckResult?.success"
              class="annotated-btn"
              size="small"
              @click="openAnnotatedDoc(scope.row)"
            >
              标记文档
            </el-button>
            <el-button class="delete-btn" size="small" @click="handleDelete(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 待审核列表分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pendingPagination.currentPage"
          v-model:page-size="pendingPagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :small="true"
          :background="true"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredPendingList.length"
          @size-change="handlePendingPageSizeChange"
          @current-change="handlePendingPageChange"
        />
      </div>
    </el-card>

    <!-- 批量审核工具栏 -->
    <div class="batch-toolbar" v-if="selectedPendingPapers.length > 0">
      <span class="selected-count">已选择 <strong>{{ selectedPendingPapers.length }}</strong> 篇论文</span>
      <el-select v-model="batchReviewStatus" placeholder="设置审核状态" style="width: 140px;">
        <el-option label="已审核" value="reviewed" />
        <el-option label="需修改" value="needs_revision" />
      </el-select>
      <el-input
        v-model="batchReviewComment"
        type="textarea"
        :rows="2"
        placeholder="统一审核意见（可选）"
        style="width: 300px;"
      />
      <el-button class="confirm-btn" type="primary" @click="handleBatchReview">批量提交审核</el-button>
      <el-button @click="selectedPendingPapers = []">取消选择</el-button>
    </div>

    <!-- 已审核论文列表 -->
    <el-card class="content-card reviewed-list-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <h3>已审核论文列表</h3>
            <span class="total-count">共 {{ filteredReviewedList.length }} 篇论文</span>
          </div>
          <div class="header-right">
            <el-button class="report-btn" type="primary" size="small" @click="openComprehensiveReport">综合报告</el-button>
          </div>
        </div>
      </template>

      <el-form :model="filterForm" inline>
        <el-form-item label="审核状态">
          <el-select v-model="filterForm.status" placeholder="全部" clearable style="width: 120px;">
            <el-option label="已审核" value="reviewed" />
            <el-option label="需修改" value="need_revision" />
          </el-select>
        </el-form-item>
        <el-form-item label="审核日期">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filterForm.keyword" placeholder="输入关键词" clearable />
        </el-form-item>
        <el-form-item>
          <el-button class="search-btn" type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="paginatedReviewedList" style="width: 100%">
        <el-table-column prop="title" label="论文标题" width="300" />
        <el-table-column prop="submitDate" label="提交日期" width="120" />
        <el-table-column prop="reviewStatus" label="审核状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.reviewStatus === 'reviewed' ? 'success' : 'warning'">
              {{ scope.row.reviewStatus === 'reviewed' ? '已审核' : '需修改' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reviewedAt" label="审核日期" width="120" />
        <el-table-column label="操作" width="400">
          <template #default="scope">
            <el-button class="view-btn" size="small" @click="openOriginalDoc(scope.row)">原文档</el-button>
            <el-button
              v-if="scope.row.formatCheckResult?.success"
              class="report-btn"
              size="small"
              @click="openReportDoc(scope.row)"
            >检测报告</el-button>
            <el-button
              v-if="scope.row.formatCheckResult?.success"
              class="annotated-btn"
              size="small"
              @click="openAnnotatedDoc(scope.row)"
            >标记文档</el-button>
            <el-button size="small" @click="handleViewComment(scope.row)">审核意见</el-button>
            <el-button class="delete-btn" size="small" @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="reviewedPagination.currentPage"
          v-model:page-size="reviewedPagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :small="true"
          :background="true"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredReviewedList.length"
          @size-change="handleReviewedPageSizeChange"
          @current-change="handleReviewedPageChange"
        />
      </div>
    </el-card>
    <el-dialog v-model="showAddDialog" title="添加论文" width="500px">
      <el-form :model="newPaper" label-width="80px">
        <el-form-item label="论文标题">
          <el-input v-model="newPaper.title" placeholder="请输入论文标题" />
        </el-form-item>
        <el-form-item label="提交日期">
          <el-date-picker
            v-model="newPaper.submitDate"
            type="date"
            placeholder="选择提交日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="上传文件">
           <el-upload
             ref="uploadRef"
             :auto-upload="false"
             :limit="1"
             accept=".doc,.docx"
             :on-change="handleFileChange"
             :on-exceed="handleFileExceed"
             :file-list="fileList"
           >
             <el-button class="upload-btn" type="primary">选择文件</el-button>
             <template #tip>
               <div class="el-upload__tip">只能上传Word文档，且不超过10MB（再次选择会覆盖）</div>
             </template>
           </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button class="confirm-btn" type="primary" @click="handleAddPaper">确定</el-button>
      </template>
    </el-dialog>

    <!-- 审核对话框 -->
    <el-dialog v-model="showReviewDialog" title="论文审核" width="900px">
      <div class="review-content">
        <p class="paper-title-display"><strong>论文标题：</strong>{{ currentPaper?.title }}</p>

         <!-- 格式检测区域 -->
         <el-card class="format-check-card" shadow="never">
           <template #header>
             <div class="card-header-format">
               <span>论文格式检测</span>
               <el-button
                 v-if="!isFormatChecking && !formatCheckResult"
                 class="check-format-btn"
                 size="small"
                 @click="showModuleSelector"
                 :disabled="!currentPaper?.tempFilePath"
               >
                 选择检测模块
               </el-button>
             </div>
           </template>

          <!-- 检测状态提示 -->
          <div v-if="!currentPaper?.tempFilePath" class="format-hint">
            <el-alert title="请先上传论文文件才能进行格式检测" type="info" :closable="false" />
          </div>

          <!-- 检测进度 -->
          <div v-if="isFormatChecking" class="format-checking">
            <el-progress :percentage="formatCheckProgress" />
            <p style="text-align: center; margin-top: 10px; color: #666;">
              正在检测论文格式，请稍候...
            </p>
          </div>

          <!-- 检测结果 -->
          <div v-if="formatCheckResult && !isFormatChecking" class="format-result">
            <div class="result-summary">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="总检测项">
                  {{ formatCheckResult.data?.summary.total_checks || 0 }}
                </el-descriptions-item>
                <el-descriptions-item label="通过项">
                  <span style="color: #67c23a;">{{ formatCheckResult.data?.summary.passed_checks || 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="失败项">
                  <span style="color: #f56c6c;">{{ formatCheckResult.data?.summary.failed_checks || 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="通过率">
                  <el-tag :type="getPassRateType(formatCheckResult.data?.summary.pass_rate || 0)">
                    {{ formatCheckResult.data?.summary.pass_rate || 0 }}%
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <!-- 详细结果折叠面板 -->
            <el-collapse v-model="activeModules" class="result-details" accordion>
              <el-collapse-item
                v-for="(moduleResult, moduleName) in formatCheckResult.data?.results"
                :key="moduleName"
                :name="moduleName"
              >
                <template #title>
                  <div class="module-title">
                    <span class="module-name">{{ moduleNamesCN[moduleName] || moduleName }}</span>
                    <el-tag
                      :type="getModuleStatusType(moduleResult)"
                      size="small"
                      style="margin-left: 10px;"
                    >
                      {{ getModuleStatus(moduleResult) }}
                    </el-tag>
                  </div>
                </template>

                <div class="module-checks">
                  <div
                    v-for="(check, checkName) in moduleResult.checks"
                    :key="checkName"
                    class="check-item-inline"
                  >
                    <div class="check-header-inline">
                      <span :class="['check-icon', check.ok ? 'success' : 'error']">
                        {{ check.ok ? '✓' : '✗' }}
                      </span>
                      <span class="check-name-text">{{ checkNamesCN[checkName] || checkName }}</span>
                    </div>
                    <div v-if="check.messages && check.messages.length > 0" class="check-messages-inline">
                      <div v-for="(message, index) in check.messages" :key="index" class="message-text">
                        • {{ message }}
                      </div>
                    </div>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>

           <div class="format-actions">
             <el-button size="small" @click="resetFormatCheck">重新检测</el-button>
             <el-button class="view-report-btn" size="small" @click="viewDetailReport">查看检测报告</el-button>
             <el-button
               v-if="formatCheckResult?.data?.annotated_saved"
               class="download-annotated-btn"
               size="small"
               @click="downloadAnnotatedDocument"
             >
               下载标记文档
             </el-button>
           </div>
         </div>
         </el-card>
       </div>

        <!-- 审核表单 -->
        <el-form :model="reviewForm" label-width="80px" style="margin-top: 20px;">
          <el-form-item label="审核结果">
            <el-radio-group v-model="reviewForm.status">
              <el-radio value="reviewed">已审核</el-radio>
              <el-radio value="needs_revision">需修改</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="审核意见">
            <el-input
              v-model="reviewForm.comment"
              type="textarea"
              :rows="4"
              placeholder="请输入审核意见（可选）"
            />
          </el-form-item>
        </el-form>
      <template #footer>
        <el-button @click="showReviewDialog = false">取消</el-button>
        <el-button class="confirm-btn" type="primary" @click="confirmReview">确定</el-button>
      </template>
    </el-dialog>

    <!-- 详细报告对话框 -->
    <el-dialog v-model="showReportDialog" title="格式检测详细报告" width="800px">
      <div class="report-content">
        <pre>{{ reportText }}</pre>
      </div>
      <template #footer>
        <el-button @click="showReportDialog = false">关闭</el-button>
        <el-button class="download-report-btn" type="primary" @click="downloadReport">下载报告</el-button>
      </template>
    </el-dialog>

    <!-- 跳过检测项选择对话框 -->
    <el-dialog v-model="showSkipChecksDialog" title="选择跳过的检测项" width="500px">
      <div class="skip-checks-content">
        <el-alert
          :title="`正在配置：${currentModuleForSkip ? availableModules.find(m => m.value === currentModuleForSkip)?.label : ''}`"
          type="info"
          :closable="false"
          style="margin-bottom: 20px;"
        />

        <el-checkbox-group v-model="currentSkipChecks">
          <div class="skip-check-option" v-for="check in availableSkipChecks" :key="check.value">
            <el-checkbox :value="check.value">
              <span class="check-label">{{ check.label }}</span>
              <span class="check-description">{{ check.description }}</span>
            </el-checkbox>
          </div>
        </el-checkbox-group>
      </div>

      <template #footer>
        <el-button @click="cancelSkipChecksSelection">取消</el-button>
        <el-button class="confirm-btn" type="primary" @click="confirmSkipChecksSelection">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 术语检测对话框 -->
    <el-dialog v-model="showTermDetectDialog" title="论文术语检测" width="900px">
      <div class="review-content">
        <p class="paper-title-display"><strong>论文标题：</strong>{{ termDetectPaper?.title }}</p>
        <el-card class="term-detect-card" shadow="never">
          <template #header>
            <div class="card-header-format">
              <span>论文术语检测</span>
              <el-button
                v-if="!isTermDetecting && !termDetectResult"
                class="check-format-btn"
                size="small"
                @click="startTermDetection"
                :disabled="!termDetectPaper?.tempFilePath"
              >
                开始术语检测
              </el-button>
            </div>
          </template>

          <!-- 检测状态提示 -->
          <div v-if="!termDetectPaper?.tempFilePath" class="format-hint">
            <el-alert title="请先上传论文文件才能进行术语检测" type="info" :closable="false" />
          </div>

          <!-- 加载历史结果 -->
          <div v-if="isLoadingTermHistory" class="format-checking">
            <el-progress :percentage="50" :indeterminate="true" />
            <p style="text-align: center; margin-top: 10px; color: #666;">
              正在加载历史检测结果...
            </p>
          </div>

          <!-- 检测进度 -->
          <div v-if="isTermDetecting && !isLoadingTermHistory" class="format-checking">
            <el-progress :percentage="termDetectProgress" />
            <p style="text-align: center; margin-top: 10px; color: #666;">
              正在检测论文术语，请稍候...
            </p>
          </div>

          <!-- 检测结果 -->
          <div v-if="termDetectResult && !isTermDetecting" class="term-result">
            <!-- 术语统计摘要 -->
            <div class="result-summary" style="margin-bottom: 20px;">
              <el-descriptions :column="3" border size="small">
                <el-descriptions-item label="检测到术语">
                  <span style="color: #409eff; font-weight: bold;">{{ termDetectResult.data?.total_terms || 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="疑似新术语">
                  <span style="color: #e6a23c; font-weight: bold;">{{ termDetectResult.data?.new_terms?.length || 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="相似术语对">
                  <span style="color: #f56c6c; font-weight: bold;">{{ termDetectResult.data?.similar_pairs?.length || 0 }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <!-- 术语检测详情 -->
            <el-tabs v-model="activeTermTab">
              <!-- Tab 1: 关键词 -->
              <el-tab-pane label="关键词" name="keywords">
                <div v-if="termDetectResult.data?.keywords?.length > 0">
                  <el-alert
                    title="从论文Keywords部分提取的关键词"
                    type="info"
                    :closable="false"
                    style="margin-bottom: 15px;"
                  />
                  <el-tag
                    v-for="keyword in termDetectResult.data.keywords"
                    :key="keyword"
                    size="large"
                    type="primary"
                    style="margin: 8px;"
                  >
                    {{ keyword }}
                  </el-tag>
                </div>
                <el-empty v-else description="未检测到关键词" />
              </el-tab-pane>

               <!-- Tab 2: SciBERT模型检测的科学术语 -->
              <el-tab-pane label="SciBERT术语" name="scibert_terms">
                <div v-if="termDetectResult.data?.scibert_terms?.length > 0">
                  <el-alert
                     title="使用SciBERT深度学习模型识别的科学术语。"
                     type="primary"
                     :closable="false"
                     description="C-Value通过结合候选术语的长度、出现频率和候选术语间的嵌套关系进行打分。分数越高，该候选术语越可能是专业术语。"
                     style="margin-bottom: 15px;"
                  />
                  <el-table :data="termDetectResult.data.scibert_terms" border stripe>
                    <el-table-column type="index" label="排名" width="80" align="center" />
                    <el-table-column prop="term" label="科学术语" min-width="220">
                      <template #default="scope">
                        <el-tag size="large" effect="plain">{{ scope.row.term }}</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="frequency" label="出现次数" width="100" align="center" />
                    <el-table-column prop="cvalue_score" label="C-value分数" width="130" align="center">
                      <template #default="scope">
                        <el-tag type="info">{{ scope.row.cvalue_score }}</el-tag>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
                <el-empty v-else description="未检测到科学术语" />
              </el-tab-pane>

              <!-- Tab 3: 智能提取的多词术语 -->
              <el-tab-pane label="多词术语" name="multi_word_terms">
                <div v-if="termDetectResult.data?.multi_word_terms?.length > 0">
                  <el-alert
                    title="使用N-gram+C-value算法提取多词术语。"
                    type="success"
                    :closable="false"
                    description="C-Value通过结合候选术语的长度、出现频率和候选术语间的嵌套关系进行打分。分数越高，该候选术语越可能是专业术语。"
                    style="margin-bottom: 15px;"
                  />
                  <el-table :data="termDetectResult.data.multi_word_terms" border stripe>
                    <el-table-column type="index" label="排名" width="80" align="center" />
                    <el-table-column prop="term" label="术语" min-width="200">
                      <template #default="scope">
                        <el-tag size="large" effect="plain">{{ scope.row.term }}</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="word_count" label="词数" width="80" align="center" />
                    <el-table-column prop="frequency" label="频率" width="80" align="center" />
                    <el-table-column prop="cvalue_score" label="C-value分数" width="120" align="center">
                      <template #default="scope">
                        <el-tag type="info">{{ scope.row.cvalue_score }}</el-tag>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
                <el-empty v-else description="未检测到多词术语" />
              </el-tab-pane>

               <!-- Tab 4: 所有候选术语 -->
              <el-tab-pane label="术语列表" name="all_terms">
                <div v-if="termDetectResult.data?.all_candidate_terms?.length > 0">
                  <el-tag
                    v-for="term in termDetectResult.data.all_candidate_terms"
                    :key="term"
                    style="margin: 5px;"
                    size="large" effect="plain"
                  >
                    {{ term }}
                  </el-tag>
                </div>
                <el-empty v-else description="未检测到术语" />
              </el-tab-pane>

               <!-- Tab 5: 疑似新术语 -->
               <el-tab-pane label="疑似新术语" name="new_terms">
                <div v-if="termDetectResult.data?.new_terms?.length > 0">
                  <div v-for="(newTerm, index) in termDetectResult.data.new_terms" :key="index" class="new-term-item">
                    <div class="new-term-header">
                      <span class="term-text">{{ newTerm.term }}</span>
                      <span class="term-trigger">触发词：{{ newTerm.trigger }}</span>
                      <el-button-group>
                        <el-button
                          size="small"
                          type="success"
                          :disabled="newTerm.confirmed === true"
                          @click="confirmNewTerm(newTerm, true)"
                        >
                          ✓ 确认
                        </el-button>
                        <el-button
                          size="small"
                          type="danger"
                          :disabled="newTerm.confirmed === false"
                          @click="confirmNewTerm(newTerm, false)"
                        >
                          ✗ 非新术语
                        </el-button>
                      </el-button-group>
                    </div>
                    <div class="term-contexts">
                      <el-collapse>
                        <el-collapse-item title="查看上下文">
                          <div v-for="(context, ctxIdx) in newTerm.contexts" :key="ctxIdx" class="context-text">
                            {{ context }}
                          </div>
                        </el-collapse-item>
                      </el-collapse>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="未检测到疑似新术语" />
              </el-tab-pane>

              <!-- Tab 6: 相似术语（规范性问题） -->
              <el-tab-pane label="相似术语" name="similar_pairs">
                <div v-if="termDetectResult.data?.similar_pairs?.length > 0">
                  <el-alert
                    title="以下术语在语义或词汇层面相似，可能存在混用情况，请检查使用规范性"
                    type="error"
                    :closable="false"
                    style="margin-bottom: 15px;"
                  />
                  <el-table :data="termDetectResult.data.similar_pairs" border stripe>
                    <el-table-column prop="term1" label="术语1" min-width="150" />
                    <el-table-column prop="term2" label="术语2" min-width="150" />
                    <el-table-column prop="final_score" label="综合相似度" width="110" align="center">
                      <template #default="scope">
                        <el-progress
                          :percentage="Math.round((scope.row.final_score || 0) * 100)"
                          :color="scope.row.final_score >= 0.9 ? '#F56C6C' : scope.row.final_score >= 0.8 ? '#E6A23C' : '#67C23A'"
                          :stroke-width="10"
                        />
                      </template>
                    </el-table-column>
                    <el-table-column prop="semantic_score" label="语义相似度" width="100" align="center">
                      <template #default="scope">
                        <span v-if="scope.row.semantic_score !== null">
                          {{ (scope.row.semantic_score * 100).toFixed(1) }}%
                        </span>
                        <span v-else style="color: #909399;">N/A</span>
                      </template>
                    </el-table-column>
                    <el-table-column prop="lexical_score" label="词汇相似度" width="100" align="center">
                      <template #default="scope">
                        {{ (scope.row.lexical_score * 100).toFixed(1) }}%
                      </template>
                    </el-table-column>
                    <el-table-column prop="severity" label="相似等级" width="90" align="center">
                      <template #default="scope">
                        <el-tag
                          :type="scope.row.severity === 'high' ? 'danger' : scope.row.severity === 'medium' ? 'warning' : 'success'"
                          size="small"
                        >
                          {{ scope.row.severity === 'high' ? '高' : scope.row.severity === 'medium' ? '中' : '低' }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="建议" min-width="180">
                      <template #default="scope">
                        <span v-if="scope.row.semantic_score !== null && scope.row.semantic_score >= 0.85">
                          <el-icon style="color: #F56C6C;"><WarningFilled /></el-icon>
                          语义高度相似，建议检查是否为同一概念的不同表达
                        </span>
                        <span v-else-if="scope.row.lexical_score >= 0.8">
                          <el-icon style="color: #E6A23C;"><Warning /></el-icon>
                          词形相近，可能存在拼写变体或混用
                        </span>
                        <span v-else>
                          建议统一使用其中一个术语
                        </span>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
                <el-empty v-else description="未检测到相似术语问题" />
              </el-tab-pane>
            </el-tabs>

            <!-- 操作按钮 -->
            <div class="format-actions" style="margin-top: 20px;">
              <el-button size="small" @click="resetTermDetection">重新检测</el-button>
            </div>
          </div>
        </el-card>

      </div>

      <template #footer>
        <el-button @click="showTermDetectDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 检测模块选择对话框 -->
    <el-dialog v-model="showModuleSelectorDialog" title="选择检测模块" width="600px">
      <div class="module-selector-content">
        <el-alert
          title="请选择需要检测的内容模块"
          type="info"
          :closable="false"
          style="margin-bottom: 20px;"
        />

        <!-- 全选选项 -->
        <div class="module-option">
          <el-checkbox
            v-model="selectAllModules"
            @change="handleSelectAll"
            :indeterminate="isIndeterminate"
          >
            <span class="module-label">全部检测</span>
          </el-checkbox>
        </div>

        <el-divider />

        <!-- 各检测模块 -->
        <el-checkbox-group v-model="selectedModules" @change="handleModuleChange">
          <div class="module-option" v-for="module in availableModules" :key="module.value">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <el-checkbox :value="module.value">
                <span class="module-label">{{ module.label }}</span>
                <span class="module-description">{{ module.description }}</span>
              </el-checkbox>
              <el-button
                v-if="selectedModules.includes(module.value) && !modulesWithoutSkipChecks.includes(module.value)"
                size="small"
                text
                type="primary"
                @click="showSkipChecksSelector(module.value)"
              >
                选择跳过项
                <span v-if="skipChecks[module.value] && skipChecks[module.value].length > 0">
                  ({{ skipChecks[module.value].length }})
                </span>
              </el-button>
            </div>
          </div>
        </el-checkbox-group>

        <!-- 图片内容检测选项 -->
        <div v-if="selectedModules.includes('Figure')" class="figure-api-option">
          <el-alert
            title="图片检测选项（使用大模型）"
            type="warning"
            :closable="false"
            style="margin-bottom: 10px;padding: 0"
          />
          <el-checkbox v-model="enableFigureApi" style="padding-bottom: 10px;">
            <span class="module-label">启用图片内容检测</span>
            <span class="module-description">*需要调用API，检测时间较长</span>
          </el-checkbox>
        </div>
      </div>

      <template #footer>
        <el-button @click="showModuleSelectorDialog = false">取消</el-button>
        <el-button
          class="confirm-btn"
          type="primary"
          @click="confirmModuleSelection"
          :disabled="selectedModules.length === 0"
        >
          开始检测
        </el-button>
      </template>
    </el-dialog>

    <!-- 审核意见查看弹窗 -->
    <el-dialog v-model="showCommentDialog" :title="isCommentEditing ? '修改审核意见' : '审核意见'" width="500px">
      <p v-if="currentPaper"><strong>论文标题：</strong>{{ currentPaper.title }}</p>
      <p v-if="currentPaper">
        <strong>审核状态：</strong>
        <el-tag :type="currentPaper.reviewStatus === 'reviewed' ? 'success' : currentPaper.reviewStatus === 'needs_revision' ? 'warning' : 'info'">
          {{ currentPaper.reviewStatus === 'reviewed' ? '已审核' : currentPaper.reviewStatus === 'needs_revision' ? '需修改' : '待审核' }}
        </el-tag>
      </p>
      <el-divider v-if="!isCommentEditing" />

      <!-- 非编辑模式：只展示审核意见 -->
      <template v-if="!isCommentEditing">
        <div v-if="currentPaper?.reviewComment" class="comment-content">
          <p>{{ currentPaper.reviewComment }}</p>
        </div>
        <el-empty v-else description="暂无审核意见" />
      </template>

      <!-- 编辑模式：显示修改表单 -->
      <template v-else>
        <el-form :model="editCommentForm" label-width="80px" style="margin-top: 20px;">
          <el-form-item label="审核结果">
            <el-radio-group v-model="editCommentForm.status">
              <el-radio value="pending">退回待审核</el-radio>
              <el-radio value="reviewed">已审核（通过）</el-radio>
              <el-radio value="needs_revision">需修改</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="审核意见">
            <el-input
              v-model="editCommentForm.comment"
              type="textarea"
              :rows="4"
              placeholder="请输入审核意见（可选）"
            />
          </el-form-item>
        </el-form>
      </template>

      <template #footer>
        <template v-if="!isCommentEditing">
          <el-button @click="showCommentDialog = false">关闭</el-button>
          <el-button type="primary" @click="startEditComment">修改审核意见</el-button>
        </template>
        <template v-else>
          <el-button @click="cancelEditComment">取消</el-button>
          <el-button type="primary" @click="submitEditComment">保存</el-button>
        </template>
      </template>
    </el-dialog>

    <!-- 综合报告弹窗 -->
    <el-dialog v-model="showComprehensiveReport" title="综合报告" width="700px">
      <div v-if="comprehensiveReport" class="comprehensive-report">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="已审核论文总数">{{ comprehensiveReport.total_papers }}</el-descriptions-item>
          <el-descriptions-item label="通过数">
            <span style="color: #67c23a;">{{ comprehensiveReport.reviewed_count }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="需修改数">
            <span style="color: #f56c6c;">{{ comprehensiveReport.needs_revision_count }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="平均通过率">
            <el-progress
              :percentage="Number(comprehensiveReport.overall_pass_rate)"
              :color="getPassRateColor(Number(comprehensiveReport.overall_pass_rate))"
            />
          </el-descriptions-item>
        </el-descriptions>

        <h4 style="margin-top: 20px;">各模块通过率</h4>
        <el-table
          :data="Object.entries(comprehensiveReport.module_pass_rates || {}).map(([module, stats]: [string, any]) => ({ module, ...stats }))"
          border
          stripe
        >
          <el-table-column prop="module" label="模块" />
          <el-table-column prop="total" label="总检测数" width="100" align="center" />
          <el-table-column prop="passed" label="通过数" width="100" align="center">
            <template #default="scope">
              <span style="color: #67c23a;">{{ scope.row.passed }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="failed" label="失败数" width="100" align="center">
            <template #default="scope">
              <span style="color: #f56c6c;">{{ scope.row.failed }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="pass_rate" label="通过率" width="200" align="center">
            <template #default="scope">
              <el-progress
                :percentage="scope.row.pass_rate"
                :color="getPassRateColor(scope.row.pass_rate)"
              />
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-empty v-else description="暂无已审核论文数据" />
    </el-dialog>
  </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Warning, WarningFilled } from '@element-plus/icons-vue'
import { paperFormatService } from '@/api/paperFormatService'
import type { ApiResponse, CheckAllResult } from '@/api/paperFormatService'
import zhCn from 'element-plus/es/locale/lang/zh-cn'


interface Paper {
  id: number
  title: string
  file?: File
  tempFilePath?: string
  fileId?: number
  submitDate?: string
  reviewDate?: string
  reviewStatus?: string
  comment?: string
  reviewComment?: string
  reviewedAt?: string
  formatCheckResult?: ApiResponse<CheckAllResult>
}

interface FilterForm {
  status: string
  dateRange: string[]
  keyword: string
}

// 数据定义
const pendingList = ref<Paper[]>([])

const reviewedList = ref<Paper[]>([])

// 筛选表单
const filterForm = ref<FilterForm>({
  status: '',
  dateRange: [],
  keyword: ''
})

// 待审核列表搜索关键词
const pendingSearchKeyword = ref('')

// 待审核列表搜索表单
const pendingSearchForm = ref({
  keyword: '',
  dateRange: []
})

// 分页配置
const pendingPagination = ref({
  currentPage: 1,
  pageSize: 10
})

const reviewedPagination = ref({
  currentPage: 1,
  pageSize: 10
})

// 对话框状态
const showAddDialog = ref(false)
const showReviewDialog = ref(false)
const showReportDialog = ref(false)
const showModuleSelectorDialog = ref(false)
const showCommentDialog = ref(false)
const isCommentEditing = ref(false)
const editCommentForm = ref({ status: '', comment: '' })
const showComprehensiveReport = ref(false)

// 表单数据
const newPaper = ref({
  title: '',
  submitDate: new Date().toISOString().split('T')[0],
  file: null as File | null
})

const reviewForm = ref({
  status: '',
  comment: ''
})

const currentPaper = ref<Paper | null>(null)

// 文件列表
const fileList = ref<any[]>([])
const uploadRef = ref()

// 格式检测相关状态
const isFormatChecking = ref(false)
const formatCheckProgress = ref(0)
const formatCheckResult = ref<ApiResponse<CheckAllResult> | null>(null)
const activeModules = ref<string>('')
const reportText = ref('')

// 模块选择相关状态
const selectedModules = ref<string[]>([])
const selectAllModules = ref(false)
const enableFigureApi = ref(false)
const enableClassificationApi = ref(false)

// 跳过检测项相关状态
const showSkipChecksDialog = ref(false)
const currentModuleForSkip = ref<string>('')
const currentSkipChecks = ref<string[]>([])
const skipChecks = ref<Record<string, string[]>>({})

// 术语检测相关状态
const showTermDetectDialog = ref(false)
const termDetectPaper = ref<Paper | null>(null)
const isTermDetecting = ref(false)
const termDetectProgress = ref(0)
const termDetectResult = ref<any>(null)
const activeTermTab = ref('keywords')
const isLoadingTermHistory = ref(false)

// 综合报告相关状态
const comprehensiveReport = ref<any>(null)

// 批量审核相关状态
const selectedPendingPapers = ref<Paper[]>([])
const batchReviewStatus = ref('')
const batchReviewComment = ref('')

// 可用的检测模块列表
const availableModules = [
  { value: 'Title', label: '标题格式检测', description: '检测标题、作者、单位格式' },
  { value: 'Abstract', label: '摘要格式检测', description: '检测摘要结构和格式' },
  { value: 'English_Abstract', label: '英文摘要格式检测', description: '检测英文摘要结构和格式' },
  { value: 'Keywords', label: '关键词格式检测', description: '检测关键词格式' },
  { value: 'Content', label: '正文格式检测', description: '检测正文格式' },
  { value: 'TOC', label: '目录/图录/表录检测', description: '检测目录/图录/表录格式检测'},
  { value: 'Formula', label: '公式格式检测', description: '检测公式编号和格式' },
  { value: 'Figure', label: '图片格式检测', description: '检测图片格式和编号' },
  { value: 'Table', label: '表格格式检测', description: '检测表格格式和编号' },
  { value: 'References', label: '参考文献格式检测', description: '检测参考文献结构和格式' },
  { value: 'Chinese_section', label: '中文部分检测', description: '检测中文标题、作者、单位、摘要和关键词格式' }
]

// 不支持跳过项功能的模块列表
const modulesWithoutSkipChecks = ['Chinese_section']

// 可跳过的检测项列表
const availableSkipChecks = [
  { value: 'font_size', label: '字体大小', description: '跳过字体大小检测' },
  { value: 'bold', label: '加粗', description: '跳过文字加粗检测' },
  { value: 'italic', label: '斜体', description: '跳过文字斜体检测' },
  { value: 'alignment', label: '对齐', description: '跳过段落对齐检测' },
  { value: 'spacing', label: '行距', description: '跳过行距检测' },
  { value: 'indent', label: '缩进', description: '跳过首行缩进检测' }
]

// 计算是否为半选状态
const isIndeterminate = computed(() => {
  const selected = selectedModules.value.length
  const total = availableModules.length
  return selected > 0 && selected < total
})

// 计算属性：筛选后的待审核列表
const filteredPendingList = computed(() => {
  let filtered = [...pendingList.value]

  if (pendingSearchKeyword.value.trim()) {
    const keyword = pendingSearchKeyword.value.toLowerCase()
    filtered = filtered.filter(paper =>
      paper.title.toLowerCase().includes(keyword)
    )
  }

  if (pendingSearchForm.value.dateRange && pendingSearchForm.value.dateRange.length === 2) {
    const [startDate, endDate] = pendingSearchForm.value.dateRange
    filtered = filtered.filter(paper => {
      if (!paper.submitDate) return false
      return paper.submitDate >= startDate && paper.submitDate <= endDate
    })
  }

  return filtered
})

// 计算属性：筛选后的已审核列表
const filteredReviewedList = computed(() => {
  let filtered = [...reviewedList.value]

  if (filterForm.value.status) {
    const statusMap: Record<string, string> = {
      'reviewed': '已审核',
      'need_revision': '需修改'
    }
    const targetStatus = statusMap[filterForm.value.status]
    if (targetStatus) {
      filtered = filtered.filter(paper => paper.reviewStatus === targetStatus)
    }
  }

  if (filterForm.value.dateRange && filterForm.value.dateRange.length === 2) {
    const [startDate, endDate] = filterForm.value.dateRange
    filtered = filtered.filter(paper => {
      if (!paper.reviewDate) return false
      return paper.reviewDate >= startDate && paper.reviewDate <= endDate
    })
  }

  if (filterForm.value.keyword.trim()) {
    const keyword = filterForm.value.keyword.toLowerCase()
    filtered = filtered.filter(paper =>
      paper.title.toLowerCase().includes(keyword)
    )
  }

  return filtered
})

// 计算属性：分页后的待审核列表
const paginatedPendingList = computed(() => {
  const start = (pendingPagination.value.currentPage - 1) * pendingPagination.value.pageSize
  const end = start + pendingPagination.value.pageSize
  return filteredPendingList.value.slice(start, end)
})

// 计算属性：分页后的已审核列表
const paginatedReviewedList = computed(() => {
  const start = (reviewedPagination.value.currentPage - 1) * reviewedPagination.value.pageSize
  const end = start + reviewedPagination.value.pageSize
  return filteredReviewedList.value.slice(start, end)
})

// 状态类型映射
const getReviewStatusType = (status: string) => {
  const statusMap: Record<string, string> = {
    '已审核': 'success',
    '需修改': 'danger'
  }
  return statusMap[status] || 'info'
}

// 文件选择处理
const handleFileChange = (file: any, fileListParam: any[]) => {
  newPaper.value.file = file.raw
  newPaper.value.title = file.name.split('.')[0]
  fileList.value = fileListParam
}

// 文件超出限制处理 - 替换文件
const handleFileExceed = (files: any[]) => {
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
    const file = files[0]
    uploadRef.value.handleStart(file)
    newPaper.value.file = file
    newPaper.value.title = file.name.split('.')[0]
    fileList.value = [file]
    ElMessage.info('已替换为新文件')
  }
}

// 从数据库加载论文列表
const loadPaperList = async () => {
  try {
    const response = await paperFormatService.getFiles()

    if (response.success && response.data) {
      const pending: Paper[] = []
      const reviewed: Paper[] = []

      response.data.forEach((file: any) => {
        const paper: Paper = {
          id: file.id,
          fileId: file.fileId,
          title: file.title,
          submitDate: file.submitDate,
          tempFilePath: file.tempFilePath,
          reviewStatus: file.reviewStatus || 'pending',
          reviewComment: file.reviewComment || '',
          reviewedAt: file.reviewedAt || '',
          formatCheckResult: file.checkStatus === 'completed' ? {
            success: true,
            data: {
              summary: {
                total_checks: file.totalChecks || 0,
                passed_checks: file.passedChecks || 0,
                failed_checks: file.failedChecks || 0,
                pass_rate: file.passRate || 0
              },
              report_saved: !!file.reportPath,
              report_filename: file.reportPath ? file.reportPath.split(/[\\/]/).pop() : undefined,
              annotated_saved: !!file.annotatedPath,
              annotated_filename: file.annotatedPath ? file.annotatedPath.split(/[\\/]/).pop() : undefined
            }
          } : undefined
        }

        if (paper.reviewStatus === 'pending') {
          pending.push(paper)
        } else {
          reviewed.push(paper)
        }
      })

      pendingList.value = pending
      reviewedList.value = reviewed
    } else {
      ElMessage.error('加载论文列表失败：' + response.message)
    }
  } catch (error) {
    console.error('加载论文列表错误:', error)
    ElMessage.error('加载论文列表失败：' + (error as Error).message)
  }
}

// 添加论文
const handleAddPaper = async () => {
  if (!newPaper.value.title.trim()) {
    ElMessage.error('请输入论文标题')
    return
  }

  if (!newPaper.value.submitDate) {
    ElMessage.error('请选择提交日期')
    return
  }

  if (!newPaper.value.file) {
    ElMessage.error('请选择文件')
    return
  }

  try {
    const duplicateResponse = await paperFormatService.checkDuplicate(newPaper.value.title)

    if (duplicateResponse.success && duplicateResponse.data.exists) {
      try {
        await ElMessageBox.confirm(
          `已存在标题为"${newPaper.value.title}"的论文（提交日期：${duplicateResponse.data.submit_date}），是否覆盖？`,
          '标题重复',
          {
            confirmButtonText: '覆盖',
            cancelButtonText: '取消',
            type: 'warning',
          }
        )

        const deleteResponse = await paperFormatService.deleteFile(duplicateResponse.data.file_id)
        if (!deleteResponse.success) {
          ElMessage.error('删除旧记录失败：' + deleteResponse.message)
          return
        }
      } catch {
        ElMessage.info('已取消添加')
        return
      }
    }
  } catch (error) {
    console.error('检查标题重复错误:', error)
    ElMessage.error('检查标题失败：' + (error as Error).message)
    return
  }

  try {
    const formData = new FormData()
    formData.append('file', newPaper.value.file)
    formData.append('title', newPaper.value.title)
    formData.append('submit_date', newPaper.value.submitDate)

    const response = await paperFormatService.saveTempFile(formData)

    if (response.success) {
      ElMessage.success('论文添加成功')

      await loadPaperList()

      newPaper.value = { title: '', submitDate: new Date().toISOString().split('T')[0], file: null }
      fileList.value = []
      if (uploadRef.value) {
        uploadRef.value.clearFiles()
      }
      showAddDialog.value = false
    } else {
      ElMessage.error('保存临时文件失败：' + response.message)
    }
  } catch (error) {
    ElMessage.error('添加论文失败：' + (error as Error).message)
  }
}

// 审核论文
const handleReview = (paper: Paper) => {
  currentPaper.value = paper
  reviewForm.value = { status: '', comment: '' }

  if (paper.formatCheckResult) {
    formatCheckResult.value = paper.formatCheckResult
    isFormatChecking.value = false
    formatCheckProgress.value = 100

    if (paper.formatCheckResult.data?.report_text) {
      reportText.value = paper.formatCheckResult.data.report_text
    } else {
      reportText.value = ''
    }
  } else {
    formatCheckResult.value = null
    isFormatChecking.value = false
    formatCheckProgress.value = 0
    reportText.value = ''
  }

  activeModules.value = ''
  showReviewDialog.value = true
}

// 确认审核
const confirmReview = async () => {
  if (!reviewForm.value.status) {
    ElMessage.error('请选择审核结果')
    return
  }

  if (!currentPaper.value) return

  try {
    const response = await paperFormatService.reviewPaper(
      [currentPaper.value.id],
      reviewForm.value.status,
      reviewForm.value.comment
    )

    if (!response.success) {
      ElMessage.error(response.message || '审核失败')
      return
    }

    const index = pendingList.value.findIndex(p => p.id === currentPaper.value!.id)
    if (index > -1) {
      pendingList.value.splice(index, 1)
    }

    const reviewDate = new Date().toISOString().split('T')[0]

    const reviewedPaper: Paper = {
      ...currentPaper.value,
      reviewDate: reviewDate,
      reviewStatus: reviewForm.value.status,
      comment: reviewForm.value.comment,
      reviewedAt: reviewDate,
      formatCheckResult: formatCheckResult.value || undefined
    }
    reviewedList.value.push(reviewedPaper)

    ElMessage.success(response.message || '审核完成')
    showReviewDialog.value = false
  } catch (error) {
    ElMessage.error('审核失败：' + (error as Error).message)
  }
}

// 批量审核
const handleBatchReview = async () => {
  if (selectedPendingPapers.value.length === 0) {
    ElMessage.warning('请先选择要审核的论文')
    return
  }
  if (!batchReviewStatus.value) {
    ElMessage.error('请选择审核状态')
    return
  }

  const fileIds = selectedPendingPapers.value.map(p => p.id)
  try {
    const response = await paperFormatService.reviewPaper(
      fileIds,
      batchReviewStatus.value,
      batchReviewComment.value
    )

    if (!response.success) {
      ElMessage.error(response.message || '批量审核失败')
      return
    }

    const reviewDate = new Date().toISOString().split('T')[0]
    selectedPendingPapers.value.forEach(paper => {
      const index = pendingList.value.findIndex(p => p.id === paper.id)
      if (index > -1) {
        pendingList.value.splice(index, 1)
        reviewedList.value.push({
          ...paper,
          reviewDate: reviewDate,
          reviewStatus: batchReviewStatus.value,
          comment: batchReviewComment.value,
          reviewedAt: reviewDate
        })
      }
    })

    selectedPendingPapers.value = []
    batchReviewStatus.value = ''
    batchReviewComment.value = ''
    ElMessage.success(response.message || '批量审核完成')
  } catch (error) {
    ElMessage.error('批量审核失败：' + (error as Error).message)
  }
}

// 查看审核意见
const handleViewComment = (paper: Paper) => {
  currentPaper.value = paper
  isCommentEditing.value = false
  showCommentDialog.value = true
}

// 开始修改审核意见
const startEditComment = () => {
  if (!currentPaper.value) return
  editCommentForm.value = {
    status: currentPaper.value.reviewStatus || 'pending',
    comment: currentPaper.value.reviewComment || ''
  }
  isCommentEditing.value = true
}

// 取消修改审核意见
const cancelEditComment = () => {
  isCommentEditing.value = false
}

// 提交修改审核意见
const submitEditComment = async () => {
  if (!currentPaper.value) return

  try {
    const response = await paperFormatService.reviewPaper(
      [currentPaper.value.id],
      editCommentForm.value.status,
      editCommentForm.value.comment
    )

    if (!response.success) {
      ElMessage.error(response.message || '修改审核意见失败')
      return
    }

    currentPaper.value.reviewStatus = editCommentForm.value.status
    currentPaper.value.reviewComment = editCommentForm.value.comment
    currentPaper.value.reviewDate = new Date().toISOString().split('T')[0]

    const index = reviewedList.value.findIndex(p => p.id === currentPaper.value!.id)
    if (index > -1) {
      reviewedList.value[index] = { ...currentPaper.value }
    }

    if (editCommentForm.value.status === 'pending') {
      const idx = reviewedList.value.findIndex(p => p.id === currentPaper.value!.id)
      if (idx > -1) {
        const paper = reviewedList.value.splice(idx, 1)[0]
        paper.reviewStatus = 'pending'
        pendingList.value.push(paper)
      }
    }

    ElMessage.success(response.message || '修改成功')
    isCommentEditing.value = false
    showCommentDialog.value = false
  } catch (error) {
    ElMessage.error('修改审核意见失败：' + (error as Error).message)
  }
}

// 打开综合报告
const openComprehensiveReport = async () => {
  showComprehensiveReport.value = true
  try {
    const response = await paperFormatService.getComprehensiveReport()
    if (response.success && response.data) {
      comprehensiveReport.value = response.data
    } else {
      comprehensiveReport.value = null
      ElMessage.info(response.message || '暂无已审核论文')
    }
  } catch (error) {
    ElMessage.error('获取综合报告失败：' + (error as Error).message)
  }
}

// 获取通过率对应的进度条颜色
const getPassRateColor = (rate: number) => {
  if (rate >= 80) return '#67c23a'
  if (rate >= 60) return '#e6a23c'
  return '#f56c6c'
}

// 模块选择相关方法
const showModuleSelector = () => {
  if (!currentPaper.value?.tempFilePath) {
    ElMessage.error('论文文件未上传到服务器')
    return
  }

  selectedModules.value = []
  selectAllModules.value = false
  enableFigureApi.value = false
  enableClassificationApi.value = false

  showModuleSelectorDialog.value = true
}

const handleSelectAll = (value: boolean) => {
  if (value) {
    selectedModules.value = availableModules.map(m => m.value)
  } else {
    selectedModules.value = []
  }
}

const handleModuleChange = (value: string[]) => {
  selectAllModules.value = value.length === availableModules.length

  if (!value.includes('Figure')) {
    enableFigureApi.value = false
  }

  if (!value.includes('Abstract')) {
    enableClassificationApi.value = false
  }

  const currentSkipModules = Object.keys(skipChecks.value)
  currentSkipModules.forEach(module => {
    if (!value.includes(module)) {
      delete skipChecks.value[module]
    }
  })
}

// 显示跳过检测项选择对话框
const showSkipChecksSelector = (moduleName: string) => {
  currentModuleForSkip.value = moduleName
  currentSkipChecks.value = skipChecks.value[moduleName] ? [...skipChecks.value[moduleName]] : []
  showSkipChecksDialog.value = true
}

// 确认跳过检测项选择
const confirmSkipChecksSelection = () => {
  if (currentModuleForSkip.value) {
    skipChecks.value[currentModuleForSkip.value] = [...currentSkipChecks.value]
  }
  showSkipChecksDialog.value = false
}

// 取消跳过检测项选择
const cancelSkipChecksSelection = () => {
  showSkipChecksDialog.value = false
  currentModuleForSkip.value = ''
  currentSkipChecks.value = []
}

const confirmModuleSelection = () => {
  if (selectedModules.value.length === 0) {
    ElMessage.warning('请至少选择一个检测模块')
    return
  }

  showModuleSelectorDialog.value = false

  startFormatCheck()
}

// 格式检测相关方法
const startFormatCheck = async () => {
  if (!currentPaper.value?.tempFilePath) {
    ElMessage.error('论文文件未上传到服务器')
    return
  }

  try {
    isFormatChecking.value = true
    formatCheckProgress.value = 0

    const progressInterval = setInterval(() => {
      if (formatCheckProgress.value < 90) {
        formatCheckProgress.value += 10
      }
    }, 500)

    const result = await paperFormatService.checkAll(
      currentPaper.value.tempFilePath,
      enableFigureApi.value,
      selectedModules.value,
      currentPaper.value.fileId,
      skipChecks.value,
      enableClassificationApi.value
    )

    clearInterval(progressInterval)
    formatCheckProgress.value = 100

    formatCheckResult.value = result

    if (result.success) {
      ElMessage.success('格式检测完成，报告已自动保存')

      if (result.data?.report_saved) {
        reportText.value = result.data.report_text
      }

      await loadPaperList()

      if (currentPaper.value) {
        const updatedPaper = pendingList.value.find(p => p.id === currentPaper.value?.id)
        if (updatedPaper) {
          currentPaper.value = updatedPaper
        }
      }
    } else {
      ElMessage.error(result.message || '格式检测失败')
    }

  } catch (error) {
    ElMessage.error('格式检测失败：' + (error as Error).message)
  } finally {
    setTimeout(() => {
      isFormatChecking.value = false
    }, 300)
  }
}

// 重新检测
const resetFormatCheck = () => {
  formatCheckResult.value = null
  formatCheckProgress.value = 0
  activeModules.value = ''
  isFormatChecking.value = false

  showModuleSelector()
}

// 术语检测相关方法
const handleTermDetect = async (paper: Paper) => {
  termDetectPaper.value = paper
  termDetectResult.value = null
  termDetectProgress.value = 0
  isTermDetecting.value = false
  showTermDetectDialog.value = true

  if (paper.fileId) {
    try {
      isLoadingTermHistory.value = true
      const response = await paperFormatService.getTermResult(paper.fileId)

      if (response.success && response.has_result && response.data) {
        termDetectResult.value = { success: true, data: response.data }
        termDetectProgress.value = 100
        ElMessage.info('已加载历史术语检测结果')
      }
    } catch (error) {
      console.error('加载历史术语检测结果失败:', error)
    } finally {
      isLoadingTermHistory.value = false
    }
  }
}

const startTermDetection = async () => {
  const paper = termDetectPaper.value
  if (!paper?.tempFilePath) {
    ElMessage.error('论文文件未上传到服务器')
    return
  }

  try {
    isTermDetecting.value = true
    termDetectProgress.value = 0

    const progressInterval = setInterval(() => {
      if (termDetectProgress.value < 90) {
        termDetectProgress.value += 10
      }
    }, 500)

    const result = await paperFormatService.detectTerms(paper.tempFilePath, paper.fileId, paper.title)

    clearInterval(progressInterval)
    termDetectProgress.value = 100

    termDetectResult.value = result

    if (result.success) {
      ElMessage.success('术语检测完成，结果已保存')
    } else {
      ElMessage.error('术语检测失败: ' + result.message)
    }

  } catch (error: any) {
    console.error('术语检测失败:', error)
    ElMessage.error('术语检测失败: ' + error.message)
  } finally {
    isTermDetecting.value = false
  }
}

const resetTermDetection = () => {
  termDetectResult.value = null
  termDetectProgress.value = 0
  activeTermTab.value = 'keywords'
  isTermDetecting.value = false
  isLoadingTermHistory.value = false
}

const confirmNewTerm = async (newTerm: any, confirmed: boolean) => {
  try {
    newTerm.confirmed = confirmed

    const result = await paperFormatService.confirmNewTerm(
      newTerm.term,
      confirmed,
      termDetectPaper.value?.fileId
    )

    if (result.success) {
      ElMessage.success(confirmed ? '已确认为新术语' : '已标记为非新术语')
    } else {
      ElMessage.error('确认失败: ' + result.message)
    }

  } catch (error: any) {
    console.error('确认新术语失败:', error)
    ElMessage.error('确认失败: ' + error.message)
  }
}

// 查看检测报告
const viewDetailReport = async () => {
  if (!formatCheckResult.value) {
    ElMessage.error('无检测结果')
    return
  }

  if (!reportText.value && currentPaper.value?.fileId) {
    try {
      ElMessage.info('正在加载报告内容...')
      const response = await paperFormatService.getReportText(currentPaper.value.fileId)

      if (response.success && response.data?.report_text) {
        reportText.value = response.data.report_text
        ElMessage.success('报告加载成功')
      } else {
        ElMessage.error('无法加载报告内容：' + response.message)
        return
      }
    } catch (error) {
      ElMessage.error('加载报告失败：' + (error as Error).message)
      return
    }
  } else if (!reportText.value) {
    ElMessage.error('无检测报告')
    return
  }

  showReportDialog.value = true
}

// 下载报告
const downloadReport = () => {
  if (!reportText.value) {
    ElMessage.error('无报告内容')
    return
  }

  const blob = new Blob([reportText.value], { type: 'text/plain;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = `论文格式检测报告_${currentPaper.value?.title || '未命名'}_${new Date().getTime()}.txt`
  document.body.appendChild(link)
  link.click()

  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)

  ElMessage.success('报告下载成功')
}

const downloadAnnotatedDocument = () => {
  if (!formatCheckResult.value?.data?.annotated_download_url) {
    ElMessage.error('标记文档不可用')
    return
  }

  try {
    const downloadUrl = formatCheckResult.value.data.annotated_download_url
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = formatCheckResult.value.data.annotated_filename || 'annotated.docx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    ElMessage.success('标记文档下载成功')
  } catch (error) {
    ElMessage.error('下载标记文档失败：' + (error as Error).message)
  }
}

const getPassRateType = (passRate: number) => {
  if (passRate >= 90) return 'success'
  if (passRate >= 70) return 'warning'
  return 'danger'
}

// 检查项 key → 中文标签映射
const checkNamesCN: Record<string, string> = {
  '[结构]': '结构',
  '[格式]': '格式',
  '[标题格式]': '标题格式',
  '[内容格式]': '内容格式',
  '[公式检测]': '公式检测',
  '[编号]': '编号',
  '[图录格式]': '图录格式',
  '[目录格式]': '目录格式',
  '[表录格式]': '表录格式',
  '[图检测]': '图检测',
  '[表格检测]': '表格检测',
  '[中文标题格式]': '中文标题格式',
  '[中文作者格式]': '中文作者格式',
  '[中文单位格式]': '中文单位格式',
  '[中文摘要格式]': '中文摘要格式',
  '[中文关键词格式]': '中文关键词格式',
}

// 模块名 → 中文标签映射
const moduleNamesCN: Record<string, string> = {
  'Title': '标题',
  'Abstract': '摘要',
  'English_Abstract': '英文摘要',
  'Keywords': '关键词',
  'Content': '正文',
  'Formula': '公式',
  'TOC': '目录/图录/表录',
  'Figure': '图',
  'Table': '表格',
  'References': '参考文献',
  'Chinese_section': '中文部分',
  'Classification': '摘要分类号',
}

const getModuleStatus = (moduleResult: any) => {
  const checks = moduleResult.checks || {}
  const checkValues = Object.values(checks)

  if (checkValues.length === 0) return '未检测'

  const allPassed = checkValues.every((check: any) => check.ok === true)
  if (allPassed) return '符合规范'

  const allFailed = checkValues.every((check: any) => check.ok === false)
  if (allFailed) return '全部失败'

  return '部分通过'
}

const getModuleStatusType = (moduleResult: any) => {
  const status = getModuleStatus(moduleResult)

  if (status === '符合规范') return 'success'
  if (status === '全部失败') return 'danger'
  if (status === '部分通过') return 'warning'
  return 'info'
}

// 删除论文
const handleDelete = async (paper: Paper) => {
  if (!paper.fileId) {
    ElMessage.warning('无法删除：论文记录不存在')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除论文"${paper.title}"吗？\n\n删除后将无法恢复。`,
      '删除论文',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    const response = await paperFormatService.deleteFile(paper.fileId)

    if (response.success) {
      ElMessage.success('论文已成功删除')

      await loadPaperList()
    } else {
      ElMessage.error('删除失败：' + response.message)
    }
  } catch (error: any) {
    if (error === 'cancel' || error.message === 'cancel') {
      ElMessage.info('已取消删除')
    } else {
      console.error('删除论文失败:', error)
      ElMessage.error('删除失败：' + (error as Error).message)
    }
  }
}

// 查看论文
const handleView = (paper: Paper) => {
  ElMessage.info('查看功能待实现')
}

// 打开原文档
const openOriginalDoc = (paper: Paper) => {
  if (!paper.fileId) {
    ElMessage.error('文件记录不存在')
    return
  }

  try {
    window.open(`/api/paper-format/open-original/${paper.fileId}`, '_blank')
  } catch (error) {
    ElMessage.error('打开文档失败：' + (error as Error).message)
  }
}

// 打开检测报告
const openReportDoc = (paper: Paper) => {
  if (!paper.fileId) {
    ElMessage.error('文件记录不存在')
    return
  }

  if (!paper.formatCheckResult?.success) {
    ElMessage.error('检测报告不存在')
    return
  }

  try {
    window.open(`/api/paper-format/open-report/${paper.fileId}`, '_blank')
  } catch (error) {
    ElMessage.error('打开报告失败：' + (error as Error).message)
  }
}

// 打开标记文档
const openAnnotatedDoc = (paper: Paper) => {
  if (!paper.fileId) {
    ElMessage.error('文件记录不存在')
    return
  }

  if (!paper.formatCheckResult?.success) {
    ElMessage.error('标记文档不存在')
    return
  }

  try {
    window.open(`/api/paper-format/open-annotated/${paper.fileId}`, '_blank')
  } catch (error) {
    ElMessage.error('打开文档失败：' + (error as Error).message)
  }
}

// 修改论文
const handleEdit = (paper: Paper) => {
  ElMessage.info('修改功能待实现')
}

// 待审核列表搜索
const handlePendingSearch = () => {
  pendingPagination.value.currentPage = 1
  ElMessage.info('搜索完成')
}

// 待审核列表选择变化
const handlePendingSelectionChange = (selection: Paper[]) => {
  selectedPendingPapers.value = selection
}

// 重置待审核列表搜索
const resetPendingSearch = () => {
  pendingSearchKeyword.value = ''
  pendingSearchForm.value.dateRange = []
  pendingPagination.value.currentPage = 1
  ElMessage.info('搜索已重置')
}

// 待审核列表分页处理
const handlePendingPageChange = (page: number) => {
  pendingPagination.value.currentPage = page
}

const handlePendingPageSizeChange = (size: number) => {
  pendingPagination.value.pageSize = size
  pendingPagination.value.currentPage = 1
}

// 已审核列表分页处理
const handleReviewedPageChange = (page: number) => {
  reviewedPagination.value.currentPage = page
}

const handleReviewedPageSizeChange = (size: number) => {
  reviewedPagination.value.pageSize = size
  reviewedPagination.value.currentPage = 1
}

// 筛选功能
const handleSearch = () => {
  reviewedPagination.value.currentPage = 1
  ElMessage.success(`筛选完成，找到 ${filteredReviewedList.value.length} 篇论文`)
}

// 重置
const resetFilter = () => {
  filterForm.value = {
    status: '',
    dateRange: [],
    keyword: ''
  }

  reviewedPagination.value.currentPage = 1

  ElMessage.info('筛选已重置')
}

// 组件挂载时加载数据
onMounted(() => {
  loadPaperList()
})

</script>

<style scoped>
.preliminary-review {
  padding: 20px;
}

.filter-card {
  margin-bottom: 20px;
}

.content-card {
  margin-bottom: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  color: #333;
  margin-bottom: 8px;
}

.page-header p {
  color: #666;
  margin: 0;
}

.review-list-card {
  margin-bottom: 20px;
}

.reviewed-list-card {
  margin-bottom: 20px;
}

.batch-toolbar {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.batch-toolbar .selected-count {
  font-size: 14px;
  color: #606266;
}

.batch-toolbar .selected-count strong {
  color: #9c0e0e;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 搜索按钮自定义样式 */
.search-btn {
  background-color: #9c0e0e !important;
  border-color: #9c0e0e !important;
  color: white !important;
}

.search-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

/* 上传按钮自定义样式 */
.upload-btn {
  background-color: #9c0e0e !important;
  border-color: #9c0e0e !important;
  color: white !important;
}

.upload-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

/* 确定按钮自定义样式 */
.confirm-btn {
  background-color: #9c0e0e !important;
  border-color: #9c0e0e !important;
  color: white !important;
}

.confirm-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-header h3 {
  margin: 0;
  color: #333;
}

.total-count {
  color: #666;
  font-size: 14px;
}

.add-paper-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.add-paper-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

/* 操作按钮统一样式 */
.view-btn, .audit-btn, .edit-btn, .delete-btn, .term-detect-btn {
  background-color: #f5f5f5 !important;
  border-color: #d9d9d9 !important;
  color: #333 !important;
}

.view-btn:hover, .audit-btn:hover, .edit-btn:hover, .delete-btn:hover, .term-detect-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #91d5ff !important;
  color: #1890ff !important;
}

/* 格式检测相关样式 */
.format-check-card {
  margin-bottom: 20px;
  border: 1px solid #ebeef5;
}

.card-header-format {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.check-format-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.check-format-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

.format-hint {
  padding: 10px 0;
}

.format-checking {
  padding: 20px 0;
}

.format-result {
  padding: 10px 0;
}

.result-summary {
  margin-bottom: 20px;
}

.result-details {
  margin-top: 15px;
}

.module-title {
  display: flex;
  align-items: center;
  flex: 1;
}

.module-name {
  font-weight: 500;
  color: #333;
}

.module-checks {
  padding: 10px 0;
}

.check-item-inline {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f0f0f0;
}

.check-item-inline:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.check-header-inline {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}

.check-icon {
  font-weight: bold;
  font-size: 16px;
  margin-right: 8px;
  width: 20px;
  text-align: center;
}

.check-icon.success {
  color: #67c23a;
}

.check-icon.error {
  color: #f56c6c;
}

.check-name-text {
  font-weight: 500;
  color: #606266;
}

.pass-text {
  color: #67c23a;
  font-weight: normal;
  margin-left: 6px;
  font-size: 13px;
}

.fail-text {
  color: #f56c6c;
  font-weight: normal;
  margin-left: 6px;
  font-size: 13px;
}

.check-messages-inline {
  padding-left: 28px;
  color: #909399;
  font-size: 13px;
}

.message-text {
  margin-bottom: 4px;
  line-height: 1.5;
}

.format-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.view-report-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.view-report-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

.paper-title-display {
  font-size: 14px;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.report-content {
  max-height: 60vh;
  overflow-y: auto;
}

.report-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
}

.download-report-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.download-report-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

.download-annotated-btn {
  background-color: #28a745 !important;
  border-color: #28a745 !important;
  color: white !important;
}

.download-annotated-btn:hover {
  background-color: #218838 !important;
  border-color: #218838 !important;
}

/* 检测报告按钮样式 */
.report-btn {
  background-color: #17a2b8 !important;
  border-color: #17a2b8 !important;
  color: white !important;
}

.report-btn:hover {
  background-color: #138496 !important;
  border-color: #138496 !important;
}

/* 标记文档按钮样式 */
.annotated-btn {
  background-color: #ffc107 !important;
  border-color: #ffc107 !important;
  color: #333 !important;
}

.annotated-btn:hover {
  background-color: #e0a800 !important;
  border-color: #e0a800 !important;
}

/* 模块选择器样式 */
.module-selector-content {
  padding: 10px 0;
}

.module-option {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.module-option:last-child {
  border-bottom: none;
}

.module-label {
  font-weight: 500;
  color: #303133;
  font-size: 14px;
}

.module-description {
  margin-left: 0;
  color: #909399;
  font-size: 13px;
}

/* 跳过检测项对话框样式 */
.skip-checks-content {
  padding: 10px 0;
}

.skip-check-option {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.skip-check-option:last-child {
  border-bottom: none;
}

.check-label {
  font-weight: 500;
  color: #303133;
  font-size: 14px;
  margin-right: 10px;
}

.check-description {
  color: #909399;
  font-size: 13px;
}

.figure-api-option {
  margin-top: 10px;
  padding: 15px;
  background-color: #fdf6ec;
  border-radius: 4px;
}

:deep(.el-checkbox) {
  display: flex;
  align-items: flex-start;
  width: 100%;
}

.term-detect-card {
  margin-bottom: 20px;
}

.new-term-item {
  padding: 15px;
  margin-bottom: 15px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background-color: #fafafa;
}

.new-term-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.term-text {
  font-size: 16px;
  font-weight: bold;
  color: #409eff;
  margin-right: 15px;
}

.term-trigger {
  color: #e6a23c;
  font-size: 13px;
  margin-right: auto;
}

.term-contexts {
  margin-top: 10px;
}

.context-text {
  padding: 10px;
  margin-bottom: 10px;
  background-color: #f5f7fa;
  border-left: 3px solid #409eff;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

:deep(.el-checkbox__label) {
  display: flex;
  flex-direction: column;
  gap: 4px;
  white-space: normal;
  line-height: 1.5;
}
</style>
