import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { journalService, type Journal, type Paper } from '@/api/journalService'
import { ElMessage } from 'element-plus'

export const useJournalStore = defineStore('journal', () => {
    // 状态
    const journalList = ref<Journal[]>([])
    const selectedJournals = ref<Journal[]>([])
    const loading = ref(false)
    const filterForm = ref({
        issue: ''
    })
    const currentPage = ref(1)
    const pageSize = ref(10)

    // 计算属性
    const filteredJournalList = computed(() => {
        if (!filterForm.value.issue) {
            return [...journalList.value]
        } else {
            return journalList.value.filter((journal: Journal) =>
                journal.issue === filterForm.value.issue
            )
        }
    })

    const pagedJournalList = computed(() => {
        const start = (currentPage.value - 1) * pageSize.value
        const end = start + pageSize.value
        return filteredJournalList.value.slice(start, end)
    })

    const totalJournals = computed(() => filteredJournalList.value.length)

    // Actions
    const loadJournals = async () => {
        loading.value = true
        try {
            console.log('开始加载期刊列表...')
            const journals = await journalService.getJournals()
            console.log('期刊列表响应:', journals)

            if (journals && journals.length > 0) {
                journalList.value = journals
                console.log('使用数据库数据，期刊数量:', journals.length)
            } else {
                journalList.value = []
                console.log('数据库为空，显示空列表')
            }

            ElMessage.success('期刊列表加载成功')
        } catch (error: any) {
            console.error('加载期刊列表失败:', error)
            ElMessage.error(error.message)
            journalList.value = []
        } finally {
            loading.value = false
        }
    }

    const deleteJournal = async (journalId: number) => {
        try {
            const response = await journalService.deleteJournal(journalId)
            if (response.success) {
                ElMessage.success('期刊删除成功')
                await loadJournals()
            } else {
                ElMessage.error(response.message || '期刊删除失败')
            }
        } catch (error: any) {
            console.error('删除期刊失败:', error)
            ElMessage.error(error.message)
        }
    }

    const batchDeleteJournals = async () => {
        if (selectedJournals.value.length === 0) {
            ElMessage.warning('请先选择要删除的期刊')
            return
        }

        try {
            const deletePromises = selectedJournals.value.map((journal: Journal) =>
                journalService.deleteJournal(journal.id)
            )

            const results = await Promise.allSettled(deletePromises)

            const successfulDeletes = results.filter((result: any) => result.status === 'fulfilled' && result.value.success).length
            const failedDeletes = results.length - successfulDeletes

            if (failedDeletes === 0) {
                ElMessage.success(`批量删除成功，共删除 ${successfulDeletes} 个期刊`)
            } else if (successfulDeletes > 0) {
                ElMessage.warning(`部分删除成功：成功 ${successfulDeletes} 个，失败 ${failedDeletes} 个`)
            } else {
                ElMessage.error('批量删除失败')
            }

            selectedJournals.value = []
            await loadJournals()
        } catch (error: any) {
            console.error('批量删除期刊失败:', error)
            ElMessage.error(error.message)
        }
    }

    const getPapers = async (journalId: number): Promise<Paper[]> => {
        try {
            return await journalService.getPapers(journalId)
        } catch (error: any) {
            console.error('获取论文列表失败:', error)
            ElMessage.error(error.message)
            return []
        }
    }

    const generateTOC = async (journalId: number, journalIssue: string) => {
        try {
            ElMessage.info(`正在生成目录: ${journalIssue}`)
            const response = await journalService.generateTOC(journalId)

            if (response.downloadUrl) {
                // 提供下载选项，因为浏览器可能无法预览Word文件
                const filename = response.downloadUrl.split('/').pop()
                const downloadUrl = `http://localhost:5000${response.downloadUrl}`

                // 使用window.open方式强制弹出下载对话框
                const downloadWindow = window.open(downloadUrl, '_blank')

                if (downloadWindow) {
                    // 如果新窗口打开成功，说明浏览器可能会显示下载对话框
                    setTimeout(() => {
                        downloadWindow.close()
                    }, 1000)
                    ElMessage.success('目录生成成功！请查看浏览器的下载对话框')
                } else {
                    // 如果弹窗被阻止，使用备用下载方式
                    const link = document.createElement('a')
                    link.href = downloadUrl
                    link.download = `目录_${journalIssue}.docx`
                    link.style.display = 'none'
                    document.body.appendChild(link)
                    link.click()
                    document.body.removeChild(link)
                    ElMessage.success('目录生成成功！文件已开始下载到默认文件夹')
                }
            }
        } catch (error: any) {
            console.error('生成目录失败:', error)
            ElMessage.error(error.message)
        }
    }

    const generateWeibo = async (journalId: number, journalIssue: string) => {
        try {
            ElMessage.info(`正在生成推文: ${journalIssue}`)
            const response = await journalService.generateWeibo(journalId)

            if (response.downloadUrl) {
                // 提供下载选项，因为浏览器可能无法预览Word文件
                const filename = response.downloadUrl.split('/').pop()
                const downloadUrl = `http://localhost:5000${response.downloadUrl}`

                // 使用window.open方式强制弹出下载对话框
                const downloadWindow = window.open(downloadUrl, '_blank')

                if (downloadWindow) {
                    // 如果新窗口打开成功，说明浏览器可能会显示下载对话框
                    setTimeout(() => {
                        downloadWindow.close()
                    }, 1000)
                    ElMessage.success('推文生成成功！请查看浏览器的下载对话框')
                } else {
                    // 如果弹窗被阻止，使用备用下载方式
                    const link = document.createElement('a')
                    link.href = downloadUrl
                    link.download = `推文_${journalIssue}.docx`
                    link.style.display = 'none'
                    document.body.appendChild(link)
                    link.click()
                    document.body.removeChild(link)
                    ElMessage.success('推文生成成功！文件已开始下载到默认文件夹')
                }
            }
        } catch (error: any) {
            console.error('生成推文失败:', error)
            ElMessage.error(error.message)
        }
    }

    const generateStats = async (journalId: number, journalIssue: string) => {
        try {
            ElMessage.info(`正在生成统计表: ${journalIssue}`)
            const response = await journalService.generateStats(journalId)

            if (response.downloadUrl) {
                // 提供下载选项，因为浏览器可能无法预览Excel文件
                const filename = response.downloadUrl.split('/').pop()
                const downloadUrl = `http://localhost:5000${response.downloadUrl}`

                // 使用window.open方式强制弹出下载对话框
                const downloadWindow = window.open(downloadUrl, '_blank')

                if (downloadWindow) {
                    // 如果新窗口打开成功，说明浏览器可能会显示下载对话框
                    setTimeout(() => {
                        downloadWindow.close()
                    }, 1000)
                    ElMessage.success('统计表生成成功！请查看浏览器的下载对话框')
                } else {
                    // 如果弹窗被阻止，使用备用下载方式
                    const link = document.createElement('a')
                    link.href = downloadUrl
                    link.download = `统计表_${journalIssue}.xlsx`
                    link.style.display = 'none'
                    document.body.appendChild(link)
                    link.click()
                    document.body.removeChild(link)
                    ElMessage.success('统计表生成成功！文件已开始下载到默认文件夹')
                }
            }
        } catch (error: any) {
            console.error('生成统计表失败:', error)
            ElMessage.error(error.message)
        }
    }

    // 状态操作方法
    const setFilterIssue = (issue: string) => {
        filterForm.value.issue = issue
    }

    const setSelectedJournals = (selection: Journal[]) => {
        selectedJournals.value = selection
    }

    const setCurrentPage = (page: number) => {
        currentPage.value = page
    }

    const setPageSize = (size: number) => {
        pageSize.value = size
        currentPage.value = 1
    }

    const resetFilter = () => {
        filterForm.value.issue = ''
    }

    return {
        // 状态
        journalList,
        selectedJournals,
        loading,
        filterForm,
        currentPage,
        pageSize,

        // 计算属性
        filteredJournalList,
        pagedJournalList,
        totalJournals,

        // Actions
        loadJournals,
        deleteJournal,
        batchDeleteJournals,
        getPapers,
        generateTOC,
        generateWeibo,
        generateStats,

        // 状态操作方法
        setFilterIssue,
        setSelectedJournals,
        setCurrentPage,
        setPageSize,
        resetFilter
    }
})
