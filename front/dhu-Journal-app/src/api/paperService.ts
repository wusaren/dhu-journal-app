import apiClient from './axios'

export interface Paper {
    id: number
    title: string
    author: string
    journalIssue: string
    startPage: number
    endPage: number
    status: string
    submitDate: string
    file_path?: string
    stored_filename?: string
    parsing_status?: string // 解析状态：parsing, completed, failed
    parsing_progress?: number // 解析进度 0-100
    authors?: string
    first_author?: string
    issue?: string
    page_start?: number
    page_end?: number
    created_at?: string
}

export interface UploadResponse {
    success: boolean
    message: string
    duplicate?: boolean
    warning?: boolean
    error?: boolean
    journalCreated?: boolean
    journalInfo?: {
        title: string
        issue: string
    }
}

export interface DeleteResponse {
    success: boolean
    message: string
}

export interface FilterForm {
    issue: string
    status: string
    keyword: string
}

export const paperService = {
    // 获取所有论文
    async getPapers(): Promise<Paper[]> {
        return await apiClient.get('/papers')
    },

    // 删除论文
    async deletePaper(paperId: number): Promise<DeleteResponse> {
        return await apiClient.delete(`/papers/${paperId}`)
    },

    // 上传论文
    async uploadPaper(file: File, journalId: string): Promise<UploadResponse> {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('journalId', journalId)

        return await apiClient.post('/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })
    },

    // 覆盖上传论文
    async uploadPaperWithOverwrite(file: File, journalId: string, overwritePaperId: number): Promise<UploadResponse> {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('journalId', journalId)
        formData.append('overwritePaperId', overwritePaperId.toString())

        return await apiClient.post('/upload/overwrite', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })
    },

    // 检查论文是否存在
    async checkPaperExists(filename: string): Promise<Paper[]> {
        const papers = await this.getPapers()
        return papers.filter((paper: Paper) => {
            const filePath = paper.file_path || ''
            const storedFilename = paper.stored_filename || ''
            return filePath.includes(filename) || storedFilename.includes(filename)
        })
    },

    // 预览PDF
    getPreviewUrl(filename: string): string {
        return `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'}/api/preview/${filename}`
    },

    // 下载PDF
    getDownloadUrl(filename: string): string {
        return `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'}/api/download/${filename}`
    }
}
