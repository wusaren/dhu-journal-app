import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { paperService, type Paper, type FilterForm, type Journal } from '@/api/paperService'
import { journalService } from '@/api/journalService'
import { ElMessage, ElMessageBox } from 'element-plus'

export const usePaperStore = defineStore('paper', () => {
    // 状态
    const allPaperList = ref<Paper[]>([])
    const selectedPapers = ref<Paper[]>([])
    const journalList = ref<Journal[]>([])
    const filterForm = ref<FilterForm>({
        issue: '',
        status: '',
        keyword: ''
    })
    const currentPage = ref(1)
    const pageSize = ref(10)
    const parsingPapers = ref<Set<number>>(new Set())

    // 计算属性
    const filteredPaperList = computed(() => {
        return allPaperList.value.filter((paper: Paper) => {
            // 刊期筛选：直接匹配期刊刊期
            const matchesIssue = !filterForm.value.issue ||
                paper.journalIssue === filterForm.value.issue

            // 状态筛选：将英文状态值映射为中文状态
            const statusMap: Record<string, string> = {
                'pending': '待审核',
                'approved': '已通过',
                'need_revision': '需修改',
                'rejected': '已拒绝'
            }
            const matchesStatus = !filterForm.value.status ||
                paper.status === statusMap[filterForm.value.status]

            // 关键词筛选：不区分大小写
            const matchesKeyword = !filterForm.value.keyword ||
                paper.title.toLowerCase().includes(filterForm.value.keyword.toLowerCase()) ||
                paper.author.toLowerCase().includes(filterForm.value.keyword.toLowerCase())

            return matchesIssue && matchesStatus && matchesKeyword
        })
    })

    const pagedPaperList = computed(() => {
        const start = (currentPage.value - 1) * pageSize.value
        const end = start + pageSize.value
        return filteredPaperList.value.slice(start, end)
    })

    // Actions
    const loadJournals = async () => {
        try {
            console.log('开始加载期刊列表...')
            const journals = await journalService.getJournals()
            console.log('期刊列表响应:', journals)

            if (journals && journals.length > 0) {
                journalList.value = journals.map((journal: any) => ({
                    id: journal.id,
                    title: journal.title,
                    issue: journal.issue,
                    status: journal.status
                }))
                console.log('成功加载期刊列表:', journalList.value)
            } else {
                journalList.value = []
                console.log('暂无期刊数据')
            }
        } catch (error: any) {
            console.error('加载期刊列表失败:', error)
            // 这里不显示错误消息，因为axios拦截器已经显示了
            journalList.value = []
        }
    }

    const loadPapers = async (showSuccessMessage = false) => {
        try {
            console.log('开始加载论文列表...')
            const papers = await paperService.getPapers()
            console.log('论文列表响应:', papers)

            if (papers && papers.length > 0) {
                // 将API数据转换为前端格式
                allPaperList.value = papers.map((paper: any) => ({
                    id: paper.id,
                    title: paper.title || '无标题',
                    author: paper.authors || paper.first_author || '未知作者',
                    journalIssue: paper.issue || '未知刊期',
                    startPage: paper.page_start || 0,
                    endPage: paper.page_end || 0,
                    status: '待审核', // 默认状态，实际应该从数据库获取
                    submitDate: paper.created_at ? paper.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
                    file_path: paper.file_path,
                    stored_filename: paper.stored_filename,
                    parsing_status: paper.parsing_status, // 解析状态
                    parsing_progress: paper.parsing_progress || 0 // 解析进度
                }))

                // 只在指定情况下显示成功消息
                if (showSuccessMessage) {
                    ElMessage.success(`成功加载 ${papers.length} 篇论文`)
                }
            } else {
                allPaperList.value = []
                if (showSuccessMessage) {
                    ElMessage.info('暂无论文数据')
                }
            }
        } catch (error: any) {
            console.error('加载论文列表失败:', error)
            // 这里不显示错误消息，因为axios拦截器已经显示了
        }
    }

    const deletePaper = async (paperId: number) => {
        try {
            const response = await paperService.deletePaper(paperId)
            if (response.success) {
                ElMessage.success('论文删除成功')
                await loadPapers()
            } else {
                ElMessage.error(response.message || '论文删除失败')
            }
        } catch (error: any) {
            console.error('删除论文失败:', error)
            ElMessage.error(error.message)
        }
    }

    const batchDeletePapers = async () => {
        if (selectedPapers.value.length === 0) {
            ElMessage.warning('请先选择要删除的论文')
            return
        }

        try {
            const deletePromises = selectedPapers.value.map((paper: Paper) =>
                paperService.deletePaper(paper.id)
            )

            const responses = await Promise.all(deletePromises)

            // 检查是否所有删除都成功
            const failedCount = responses.filter((r: any) => !r.success).length
            const successCount = responses.length - failedCount

            if (failedCount === 0) {
                ElMessage.success(`批量删除成功，共删除 ${successCount} 篇论文`)
            } else {
                ElMessage.warning(`部分删除失败，成功删除 ${successCount} 篇，失败 ${failedCount} 篇`)
            }

            // 刷新论文列表
            await loadPapers()
            selectedPapers.value = []
        } catch (error: any) {
            console.error('批量删除失败:', error)
            ElMessage.error(error.message)
        }
    }

    const uploadPaper = async (file: File, journalId: string = '1') => {
        // 检查论文是否已存在
        const existingPapers = await paperService.checkPaperExists(file.name)
        if (existingPapers.length > 0) {
            ElMessage.warning(`论文 "${file.name}" 已存在于数据库中，不可重复上传`)
            return false
        }

        // 显示持续的解析提示
        let loadingMessage = ElMessage({
            message: '正在上传并解析论文...',
            type: 'info',
            duration: 0, // 不自动关闭
            showClose: false
        })

        try {
            const response = await paperService.uploadPaper(file, journalId)

            // 关闭持续的解析提示
            loadingMessage.close()

            // 调试信息
            console.log('响应数据:', response)
            console.log('duplicate:', response.duplicate)
            console.log('requires_confirmation:', response.requires_confirmation)

            // 检查重复文件（在success分支处理，就像创建期刊一样）
            if (response.duplicate) {
                // 显示确认对话框
                const shouldOverwrite = await showOverwriteConfirmation(response.existing_paper)
                if (shouldOverwrite) {
                    // 执行覆盖上传
                    const overwriteResponse = await paperService.uploadPaperWithOverwrite(
                        file, 
                        journalId, 
                        response.existing_paper.id
                    )
                    
                    if (overwriteResponse.success) {
                        ElMessage.success('论文覆盖上传成功！原有论文已被替换。')
                        // 刷新论文列表
                        await loadPapers()
                        return true
                    } else {
                        ElMessage.error(overwriteResponse.message || '覆盖上传失败')
                        return false
                    }
                } else {
                    ElMessage.info('已取消覆盖上传')
                    return false
                }
            } else if (response.warning) {
                ElMessage.warning(response.message || '文件上传成功，但未能解析出论文信息')
            } else if (response.error) {
                ElMessage.error(response.message || '文件上传失败')
            } else {
                // 检查解析状态
                const parsingStatus = response.parsing_status
                const parsingSuccess = response.parsing_success

                // 根据解析状态显示不同的成功消息
                if (parsingStatus === 'completed') {
                    if (parsingSuccess) {
                        ElMessage.success('论文上传成功！解析完成，已提取论文信息')
                    } else {
                        ElMessage.warning('论文上传成功！但未能解析出论文信息，请检查PDF文件格式')
                    }
                } else {
                    ElMessage.success(response.message || '论文添加成功！系统已自动解析论文信息')
                }

                // 检查是否创建了新期刊
                if (response.journalCreated && response.journalInfo) {
                    const journalTitle = response.journalInfo.title
                    const journalIssue = response.journalInfo.issue
                    ElMessage.success(`已为您在期刊管理页面创建期刊 ${journalTitle}（${journalIssue}）`)
                }
            }

            // 刷新论文列表
            await loadPapers()
            return true
        } catch (error: any) {
            // 关闭持续的解析提示
            loadingMessage.close()
            console.error('上传失败:', error)
            
            // 其他错误，显示错误消息
            ElMessage.error(error.message || '上传失败')
            return false
        }
    }

    const batchUploadPapers = async (files: File[]) => {
        // 显示持续的解析提示
        let loadingMessage = ElMessage({
            message: `正在批量上传 ${files.length} 个文件，解析中...`,
            type: 'info',
            duration: 0, // 不自动关闭
            showClose: false
        })

        let successCount = 0
        let failCount = 0

        for (let i = 0; i < files.length; i++) {
            const file = files[i]
            if (!file) continue

            try {
                console.log(`开始上传文件 ${i + 1}/${files.length}: ${file.name}`)
                const success = await uploadPaper(file)
                if (success) {
                    successCount++
                    console.log(`文件 ${file.name} 上传成功`)
                } else {
                    failCount++
                    console.log(`文件 ${file.name} 上传失败`)
                }
            } catch (error) {
                console.error(`文件 "${file.name}" 上传失败:`, error)
                ElMessage.error(`文件 "${file.name}" 上传失败`)
                failCount++
            }

            // 关闭当前消息并显示新的进度消息
            loadingMessage.close()
            loadingMessage = ElMessage({
                message: `正在批量上传 ${files.length} 个文件，已处理 ${i + 1}/${files.length}，解析中...`,
                type: 'info',
                duration: 0,
                showClose: false
            })

            // 添加小延迟，避免请求过于频繁
            if (i < files.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 500))
            }
        }

        // 关闭持续的解析提示
        loadingMessage.close()

        // 显示批量上传结果
        if (failCount === 0) {
            ElMessage.success(`批量上传完成！成功上传 ${successCount} 个文件`)
        } else if (successCount > 0) {
            ElMessage.warning(`批量上传完成！成功 ${successCount} 个，失败 ${failCount} 个`)
        } else {
            ElMessage.error('批量上传失败')
        }

        // 最终刷新论文列表
        await loadPapers()
    }

    const batchDownloadPapers = async () => {
        if (selectedPapers.value.length === 0) {
            ElMessage.warning('请先选择要下载的论文')
            return
        }

        try {
            ElMessage.info(`正在批量下载 ${selectedPapers.value.length} 篇论文...`)

            // 检查选中的论文是否有PDF文件
            const papersWithFiles = selectedPapers.value.filter((paper: Paper) =>
                paper.file_path || paper.stored_filename
            )

            if (papersWithFiles.length === 0) {
                ElMessage.warning('选中的论文都没有PDF文件')
                return
            }

            // 逐个下载PDF文件
            for (const paper of papersWithFiles) {
                // 从文件路径中提取文件名
                let filename = ''
                if (paper.file_path) {
                    const pathParts = paper.file_path.split(/[\\/]/)
                    filename = pathParts[pathParts.length - 1]
                } else if (paper.stored_filename) {
                    filename = paper.stored_filename
                }

                if (filename) {
                    // 使用下载API下载PDF文件
                    const downloadUrl = paperService.getDownloadUrl(filename)

                    // 创建下载链接并触发下载
                    const link = document.createElement('a')
                    link.href = downloadUrl
                    link.download = filename
                    link.style.display = 'none'
                    document.body.appendChild(link)
                    link.click()
                    document.body.removeChild(link)

                    // 添加小延迟避免浏览器限制
                    await new Promise(resolve => setTimeout(resolve, 100))
                }
            }

            ElMessage.success(`批量下载完成，共下载 ${papersWithFiles.length} 篇论文`)

        } catch (error) {
            console.error('批量下载失败:', error)
            ElMessage.error('批量下载失败，请稍后重试')
        }
    }

    // 状态操作方法
    const setFilterIssue = (issue: string) => {
        filterForm.value.issue = issue
    }

    const setFilterStatus = (status: string) => {
        filterForm.value.status = status
    }

    const setFilterKeyword = (keyword: string) => {
        filterForm.value.keyword = keyword
    }

    const setSelectedPapers = (selection: Paper[]) => {
        selectedPapers.value = selection
    }

    const setCurrentPage = (page: number) => {
        currentPage.value = page
    }

    const setPageSize = (size: number) => {
        pageSize.value = size
        currentPage.value = 1
    }

    const resetFilter = () => {
        filterForm.value = {
            issue: '',
            status: '',
            keyword: ''
        }
        currentPage.value = 1
    }

    return {
        // 状态
        allPaperList,
        selectedPapers,
        journalList,
        filterForm,
        currentPage,
        pageSize,
        parsingPapers,

        // 计算属性
        filteredPaperList,
        pagedPaperList,

        // Actions
        loadJournals,
        loadPapers,
        deletePaper,
        batchDeletePapers,
        uploadPaper,
        batchUploadPapers,
        batchDownloadPapers,

        // 状态操作方法
        setFilterIssue,
        setFilterStatus,
        setFilterKeyword,
        setSelectedPapers,
        setCurrentPage,
        setPageSize,
        resetFilter
    }
})

// 显示覆盖确认对话框
async function showOverwriteConfirmation(existingPaper: any): Promise<boolean> {
    try {
        await ElMessageBox.confirm(
            `检测到稿件号"${existingPaper.manuscript_id}"已存在：\n\n` +
            `标题：${existingPaper.title}\n` +
            `作者：${existingPaper.authors}\n\n` +
            `是否要覆盖现有论文？此操作将删除原有论文并上传新文件。`,
            '发现重复论文',
            {
                confirmButtonText: '覆盖上传',
                cancelButtonText: '取消',
                type: 'warning',
                dangerouslyUseHTMLString: false
            }
        )
        return true
    } catch {
        return false
    }
}
