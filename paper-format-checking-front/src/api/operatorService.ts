import apiClient from './axios'

// 文件信息接口
export interface FileInfo {
  filename: string
  student_id: string
  student_name: string
  path: string
}

// 论文检测结果接口
export interface PaperCheckResult {
  id: number
  batch_job_id: number
  student_id: string
  student_name: string
  original_filename: string
  original_path: string
  annotated_path: string
  report_path: string
  check_status: 'pending' | 'completed' | 'failed'
  review_status: 'pending' | 'reviewed' | 'needs_revision'
  pass_rate: number | null
  error_message: string | null
  created_at: string | null
  completed_at: string | null
}

// 批次任务接口
export interface BatchJob {
  id: number
  directory_path: string
  output_path: string
  total_papers: number
  processed: number
  passed: number
  failed: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  pass_threshold: number
  started_at: string | null
  completed_at: string | null
  created_at: string | null
}

// 批次详情接口
export interface BatchJobDetail extends BatchJob {
  papers: PaperCheckResult[]
}

// 批次进度接口
export interface BatchProgress {
  batch_id: number
  status: string
  total_papers: number
  processed: number
  passed: number
  failed: number
  progress_percent: number
  current_paper: string | null
  started_at: string | null
  completed_at: string | null
}

// 批次汇总接口
export interface BatchSummary {
  batch_id: number
  total_papers: number
  processed: number
  passed: number
  failed: number
  reviewed_count: number
  needs_revision_count: number
  pending_count: number
  avg_pass_rate: number
  status: string
  pass_threshold: number
}

// API响应接口
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message: string
  status_code?: number
}

export const operatorService = {
  /**
   * 扫描目录，返回符合格式的论文文件列表
   * @param directoryPath 目录路径
   */
  async scanDirectory(directoryPath: string): Promise<ApiResponse<FileInfo[]>> {
    return await apiClient.post('/operator/directories/scan', {
      directory_path: directoryPath
    })
  },

  /**
   * 启动批量检测任务
   * @param directoryPath 论文目录
   * @param passThreshold 自动通过阈值（默认85）
   * @param modules 检测模块列表（可选）
   */
  async startBatchCheck(
    directoryPath: string,
    passThreshold: number = 85,
    modules?: string[]
  ): Promise<ApiResponse<{ batch_id: number; total_papers: number; output_dir: string }>> {
    return await apiClient.post('/operator/batch/start', {
      directory_path: directoryPath,
      pass_threshold: passThreshold,
      modules: modules
    })
  },

  /**
   * 获取批量任务列表
   * @param limit 返回数量（默认50）
   */
  async getBatchJobs(limit: number = 50): Promise<ApiResponse<BatchJob[]>> {
    return await apiClient.get('/operator/batch/jobs', {
      params: { limit }
    })
  },

  /**
   * 获取批次任务详情（含论文列表）
   * @param jobId 批次ID
   */
  async getBatchJobDetail(jobId: number): Promise<ApiResponse<BatchJobDetail>> {
    return await apiClient.get(`/operator/batch/jobs/${jobId}`)
  },

  /**
   * 获取批次任务进度
   * @param jobId 批次ID
   */
  async getBatchProgress(jobId: number): Promise<ApiResponse<BatchProgress>> {
    return await apiClient.get(`/operator/batch/jobs/${jobId}/progress`)
  },

  /**
   * 取消批次任务
   * @param jobId 批次ID
   */
  async cancelBatchJob(jobId: number): Promise<ApiResponse<void>> {
    return await apiClient.post(`/operator/batch/jobs/${jobId}/cancel`)
  },

  /**
   * 导出批次Excel汇总表
   * @param batchId 批次ID
   */
  async exportBatchExcel(batchId: number): Promise<Blob> {
    const response = await apiClient.get(`/operator/batch/export-excel/${batchId}`, {
      responseType: 'blob'
    })
    return response as unknown as Blob
  },

  /**
   * 获取批次汇总信息
   * @param batchId 批次ID
   */
  async getBatchSummary(batchId: number): Promise<ApiResponse<BatchSummary>> {
    return await apiClient.get(`/operator/batch/summary/${batchId}`)
  },

  /**
   * 获取单篇论文检测详情
   * @param paperId 论文ID
   */
  async getPaperDetail(paperId: number): Promise<ApiResponse<PaperCheckResult>> {
    return await apiClient.get(`/operator/batch/papers/${paperId}`)
  },

  /**
   * 获取Excel下载链接
   * @param batchId 批次ID
   */
  getExcelDownloadUrl(batchId: number): string {
    return `/api/operator/batch/export-excel/${batchId}`
  },

  /**
   * 上传论文文件夹（仅上传，不自动检测）
   * @param files FileList 或 File[]
   */
  async uploadFolder(
    files: FileList | File[]
  ): Promise<ApiResponse<{
    batch_id: number | null;
    files: FileInfo[];
    temp_dir: string;
    total: number;
  }>> {
    const formData = new FormData()

    const fileArray = Array.from(files)
    fileArray.forEach((file, index) => {
      formData.append(`files`, file)
    })

    return await apiClient.post('/operator/batch/upload-and-check', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  /**
   * 从已上传的文件启动批量检测
   * @param files 文件信息列表
   * @param tempDir 临时目录
   * @param passThreshold 自动通过阈值
   * @param modules 检测模块列表
   */
  async startBatchCheckFromUpload(
    files: FileInfo[],
    tempDir: string,
    passThreshold: number = 85,
    modules?: string[]
  ): Promise<ApiResponse<{ batch_id: number; total_papers: number; output_dir: string }>> {
    return await apiClient.post('/operator/batch/start-from-upload', {
      files: files,
      temp_dir: tempDir,
      pass_threshold: passThreshold,
      modules: modules
    })
  }
}
