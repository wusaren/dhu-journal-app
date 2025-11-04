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
     * 获取所有可用的检测模块
     */
    async getModules(): Promise<{ modules: FormatModule[]; total: number }> {
        const response = await apiClient.get<ApiResponse<{
            modules: FormatModule[]
            total: number
        }>>('/paper-format/modules')
        return response.data!
    },

    /**
     * 检测单个模块
     * @param moduleName 模块名称（如：Title, Abstract等）
     * @param file 要检测的docx文件
     * @param enableApi 是否启用API检测（仅对Figure模块有效）
     */
    async checkModule(
        moduleName: string,
        file: File,
        enableApi: boolean = false
    ): Promise<ApiResponse<ModuleCheckResult>> {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('enableApi', enableApi.toString())

        return await apiClient.post(
            `/paper-format/check/${moduleName}`,
            formData,
            {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            }
        )
    },

    /**
     * 执行全量检测
     * @param file 要检测的docx文件
     * @param enableFigureApi 是否启用图片内容API检测
     * @param modules 指定检测的模块列表（可选）
     */
    async checkAll(
        file: File,
        enableFigureApi: boolean = false,
        modules?: string[]
    ): Promise<ApiResponse<CheckAllResult>> {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('enableFigureApi', enableFigureApi.toString())
        
        if (modules && modules.length > 0) {
            formData.append('modules', modules.join(','))
        }

        return await apiClient.post('/paper-format/check-all', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })
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
     * 下载报告文件
     * @param filename 报告文件名
     */
    getReportDownloadUrl(filename: string): string {
        return `/api/download/${filename}`
    }
}

