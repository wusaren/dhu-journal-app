import apiClient from './axios'

// 检测模块信息接口
export interface FormatModule {
    exists: boolean
    module_name: string
    default_template: string
    description: string
}

// 检测结果接口
export interface CheckResult {
    ok: boolean
    messages: string[]
}

// 模块检测结果接口
export interface ModuleCheckResult {
    module: string
    checks: {
        [key: string]: CheckResult
    }
    summary: string[]
    extracted?: any
    details?: any
}

// 全量检测结果接口
export interface CheckAllResult {
    results: {
        [moduleName: string]: ModuleCheckResult
    }
    summary: {
        total_checks: number
        passed_checks: number
        failed_checks: number
        pass_rate: number
    }
    report_saved?: boolean
    report_filename?: string
    report_download_url?: string
    report_text?: string
    annotated_saved?: boolean
    annotated_filename?: string
    annotated_download_url?: string
}

// API响应接口
export interface ApiResponse<T = any> {
    success: boolean
    data?: T
    message: string
    status_code?: number
}

export const paperFormatService = {
    /**
     * 获取所有格式审查文件列表
     */
    async getFiles(): Promise<ApiResponse<any[]>> {
        return await apiClient.get('/paper-format/files')
    },

    /**
     * 检查标题是否重复
     * @param title 论文标题
     */
    async checkDuplicate(title: string): Promise<ApiResponse<any>> {
        return await apiClient.post('/paper-format/check-duplicate', { title })
    },

    /**
     * 删除格式审查文件记录
     * @param fileId 文件ID
     */
    async deleteFile(fileId: number): Promise<ApiResponse<any>> {
        return await apiClient.delete(`/paper-format/delete/${fileId}`)
    },

    /**
     * 保存临时文件
     * @param formData 包含文件的FormData
     */
    async saveTempFile(formData: FormData): Promise<ApiResponse<{ temp_file_path: string; file_id: number }>> {
        return await apiClient.post('/paper-format/save-temp', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })
    },

    /**
     * 执行检测任务
     * @param tempFilePath 临时文件路径
     * @param enableFigureApi 是否启用图片内容API检测
     * @param modules 指定检测的模块列表（可选）
     * @param fileId 文件数据库ID（可选）
     */
    async checkAll(
        tempFilePath: string,
        enableFigureApi: boolean = false,
        modules?: string[],
        fileId?: number
    ): Promise<ApiResponse<CheckAllResult>> {
        const data: any = {
            temp_file_path: tempFilePath,
            enableFigureApi: enableFigureApi
        }

        if (modules && modules.length > 0) {
            data.modules = modules.join(',')
        }

        if (fileId) {
            data.file_id = fileId
        }

        return await apiClient.post('/paper-format/check-all', data)
    },

    /**
     * 生成检测报告
     * @param checkResults 检测结果数据
     */
    async generateReport(
        checkResults: ApiResponse<CheckAllResult>
    ): Promise<ApiResponse<{ report_text: string; download_url: string }>> {
        return await apiClient.post('/paper-format/generate-report', {
            checkResults: checkResults
        })
    },

    /**
     * 获取报告文本内容
     * @param fileId 文件ID
     */
    async getReportText(fileId: number): Promise<ApiResponse<{ report_text: string }>> {
        return await apiClient.get(`/paper-format/get-report-text/${fileId}`)
    },

    /**
     * 下载报告文件
     * @param filename 报告文件名
     */
    getReportDownloadUrl(filename: string): string {
        return `/api/download/${filename}`
    }
}

