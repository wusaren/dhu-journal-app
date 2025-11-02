import apiClient from './axios'

export interface Journal {
    id: number
    title: string
    issue: string
    publishDate: string
    paperCount: number
    status: string
    description?: string
    fileName?: string
    fileSize?: number
}

export interface CreateJournalRequest {
    issue: string
    title: string
    publish_date: string
    status: string
    description?: string
}

export interface Paper {
    id: number
    journal_id: number
    title: string
    authors: string
    first_author: string
    corresponding: string
    doi: string
    page_start: number
    page_end: number
    pdf_pages: number
    manuscript_id: string
    issue: string
    is_dhu: boolean
    abstract: string
    keywords: string
    file_path: string
    created_at: string
}

export interface ExportResponse {
    message: string
    downloadUrl: string
    filePath: string
}

export interface ApiResponse<T> {
    success: boolean
    message: string
    data?: T
}

export interface ColumnDefinition {
    key: string
    label: string
    category: string
}

export interface ColumnConfig {
    key: string
    order: number
}

class JournalService {
    /**
     * 获取期刊列表
     */
    async getJournals(): Promise<Journal[]> {
        return await apiClient.get('/journals')
    }

    /**
     * 创建期刊
     */
    async createJournal(data: CreateJournalRequest): Promise<ApiResponse<Journal>> {
        return await apiClient.post('/journals/create', data)
    }

    /**
     * 删除期刊
     */
    async deleteJournal(journalId: number): Promise<ApiResponse<void>> {
        return await apiClient.delete(`/journals/${journalId}`)
    }

    /**
     * 获取论文列表
     */
    async getPapers(journalId?: number): Promise<Paper[]> {
        const params = journalId ? { journalId } : {}
        return await apiClient.get('/papers', { params })
    }

    /**
     * 创建论文
     */
    async createPaper(data: any): Promise<ApiResponse<Paper>> {
        return await apiClient.post('/papers/create', data)
    }

    /**
     * 更新论文
     */
    async updatePaper(paperId: number, data: any): Promise<ApiResponse<void>> {
        return await apiClient.put(`/papers/${paperId}`, data)
    }

    /**
     * 删除论文
     */
    async deletePaper(paperId: number): Promise<ApiResponse<void>> {
        return await apiClient.delete(`/papers/${paperId}`)
    }

    /**
     * 文件上传
     */
    async uploadFile(file: File, journalId?: string): Promise<any> {
        const formData = new FormData()
        formData.append('file', file)
        if (journalId) {
            formData.append('journalId', journalId)
        }

        return await apiClient.post('/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })
    }

    /**
     * 生成目录
     */
    async generateTOC(journalId: number): Promise<ExportResponse> {
        return await apiClient.post('/export/toc', { journalId })
    }

    /**
     * 生成推文
     */
    async generateWeibo(journalId: number): Promise<ExportResponse> {
        return await apiClient.post('/export/tuiwen', { journalId })
    }

    /**
     * 获取可用列定义
     */
    async getAvailableColumns(): Promise<{ success: boolean; columns: ColumnDefinition[] }> {
        return await apiClient.get('/export/columns')
    }

    /**
     * 生成统计表（支持自定义列配置）
     */
    async generateStats(journalId: number, columns?: ColumnConfig[]): Promise<ExportResponse> {
        const data: any = { journalId }
        if (columns) {
            data.columns = columns
        }
        return await apiClient.post('/export/excel', data)
    }

    /**
     * 下载文件
     */
    async downloadFile(filename: string): Promise<void> {
        const link = document.createElement('a')
        link.href = `/api/download/${filename}`
        link.download = filename
        link.click()
    }
}

export const journalService = new JournalService()
