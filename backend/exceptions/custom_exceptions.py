"""
自定义异常类
为后续封装做准备，暂时不影响现有功能
"""
class JournalException(Exception):
    """期刊相关异常基类"""
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class JournalNotFoundError(JournalException):
    """期刊不存在异常"""
    def __init__(self, journal_id):
        super().__init__(f'期刊ID {journal_id} 不存在', 404)

class JournalAlreadyExistsError(JournalException):
    """期刊已存在异常"""
    def __init__(self, title, issue):
        super().__init__(f'期刊"{title} - {issue}"已存在', 400)

class PaperException(Exception):
    """论文相关异常基类"""
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class PaperNotFoundError(PaperException):
    """论文不存在异常"""
    def __init__(self, paper_id):
        super().__init__(f'论文ID {paper_id} 不存在', 404)

class FileException(Exception):
    """文件相关异常基类"""
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class FileNotFoundError(FileException):
    """文件不存在异常"""
    def __init__(self, filename):
        super().__init__(f'文件 {filename} 不存在', 404)

class ValidationException(Exception):
    """数据验证异常"""
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

