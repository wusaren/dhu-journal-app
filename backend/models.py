from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100))
    role = db.Column(db.Enum('admin', 'editor', 'viewer'), default='editor')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Author(db.Model):
    """作者表 - 管理作者信息"""
    __tablename__ = 'authors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)  # 作者姓名，如: "HUANG Jiacui"
    name_en = db.Column(db.String(200))  # 英文名
    name_cn = db.Column(db.String(200))  # 中文名
    email = db.Column(db.String(100))  # 邮箱
    affiliation = db.Column(db.String(500))  # 所属机构
    is_dhu = db.Column(db.Boolean, default=False)  # 是否东华大学
    is_corresponding = db.Column(db.Boolean, default=False)  # 是否为通讯作者
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    paper_authors = db.relationship('PaperAuthor', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    
    # 索引
    __table_args__ = (
        db.Index('idx_name', 'name'),
        db.Index('idx_is_dhu', 'is_dhu'),
    )

class Journal(db.Model):
    """期刊表 - 简化设计，专注于目录和统计表功能"""
    __tablename__ = 'journals'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, default='东华学报')
    issue = db.Column(db.String(100), nullable=False)  # 如: "2025, 42(3)"
    publish_date = db.Column(db.Date)
    status = db.Column(db.Enum('draft', 'published', 'archived'), default='draft')
    description = db.Column(db.Text)
    paper_count = db.Column(db.Integer, default=0)  # 论文数量
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # 关系
    papers = db.relationship('Paper', backref='journal', lazy='dynamic', cascade='all, delete-orphan')
    file_uploads = db.relationship('FileUpload', backref='journal', lazy='dynamic')
    
    # 唯一约束：同一期刊的同一期应该唯一
    __table_args__ = (
        db.UniqueConstraint('title', 'issue', name='uk_journal_title_issue'),
        db.Index('idx_journal_title', 'title'),
        db.Index('idx_journal_issue', 'issue'),
    )

class PaperAuthor(db.Model):
    """论文-作者关联表 - 多对多关系"""
    __tablename__ = 'paper_authors'
    
    id = db.Column(db.Integer, primary_key=True)
    paper_id = db.Column(db.Integer, db.ForeignKey('papers.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('authors.id'), nullable=False)
    author_order = db.Column(db.Integer, nullable=False)  # 作者顺序，1为第一作者
    is_corresponding = db.Column(db.Boolean, default=False)  # 是否为通讯作者
    
    # 唯一约束：同一论文中作者顺序不能重复
    __table_args__ = (
        db.UniqueConstraint('paper_id', 'author_order', name='unique_paper_author_order'),
        db.Index('idx_paper_id', 'paper_id'),
        db.Index('idx_author_id', 'author_id'),
    )

class Paper(db.Model):
    """论文表 - 专门为目录和统计表设计"""
    __tablename__ = 'papers'
    
    id = db.Column(db.Integer, primary_key=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journals.id'), nullable=False)
    
    # 基础信息
    title = db.Column(db.String(500), nullable=False)
    authors = db.Column(db.Text, nullable=False)  # 完整作者列表（保留用于兼容）
    
    # 目录生成需要的字段
    page_start = db.Column(db.Integer, nullable=False)  # 起始页码
    page_end = db.Column(db.Integer)  # 结束页码
    
    # 统计表生成需要的字段 - 严格按照你的参考代码
    manuscript_id = db.Column(db.String(100), nullable=False)  # 稿件号，如: E202405007
    pdf_pages = db.Column(db.Integer, nullable=False)  # 页数，如: 15
    first_author = db.Column(db.String(200), nullable=False)  # 一作，如: HUANG Jiacui
    corresponding = db.Column(db.String(200))  # 通讯，如: ZHAO Mingbo
    issue = db.Column(db.String(100), nullable=False)  # 刊期，如: 2025, 42(3) - 从PDF解析
    is_dhu = db.Column(db.Boolean, default=False)  # 是否东华大学
    
    # 其他字段
    doi = db.Column(db.String(200))
    abstract = db.Column(db.Text)
    keywords = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    
    # 中文标题和作者字段
    chinese_title = db.Column(db.Text)  # 中文标题
    chinese_authors = db.Column(db.Text)  # 中文作者
    
    image_path = db.Column(db.String(500))  # MinIO图片URL（保留用于兼容）
    first_image_url = db.Column(db.String(500))  # 第一张图片URL（QRcode）
    second_image_url = db.Column(db.String(500))  # 第二张图片URL
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    paper_authors = db.relationship('PaperAuthor', backref='paper', lazy='dynamic', cascade='all, delete-orphan')
    
    # 索引和唯一约束
    __table_args__ = (
        db.Index('idx_journal_id', 'journal_id'),
        db.Index('idx_page_start', 'page_start'),
        db.Index('idx_manuscript_id', 'manuscript_id'),
        # 唯一约束：稿件号应该唯一
        db.UniqueConstraint('manuscript_id', name='uk_paper_manuscript_id'),
        # 唯一约束：同一期刊中论文标题应该唯一
        db.UniqueConstraint('journal_id', 'title', name='uk_paper_journal_title'),
    )

class FileUpload(db.Model):
    """文件上传表"""
    __tablename__ = 'file_uploads'
    
    id = db.Column(db.Integer, primary_key=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('journals.id'))
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.Enum('pdf', 'docx', 'xlsx'), nullable=False)
    file_size = db.Column(db.BigInteger)
    upload_path = db.Column(db.String(500), nullable=False)
    upload_status = db.Column(db.Enum('uploading', 'processing', 'completed', 'failed'), default='uploading')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
