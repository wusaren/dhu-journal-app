"""
MinIO对象存储服务
用于上传和管理图片文件
"""

import os
import logging
from pathlib import Path
from typing import Optional

# 添加父目录到Python路径，以便导入config
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from config import current_config

logger = logging.getLogger(__name__)

class MinioService:
    """MinIO对象存储服务类"""
    
    def __init__(self):
        """初始化MinIO客户端"""
        try:
            from minio import Minio
            from minio.error import S3Error
            
            # 从配置获取MinIO连接信息
            self.endpoint = current_config.MINIO_ENDPOINT
            self.access_key = current_config.MINIO_ACCESS_KEY
            self.secret_key = current_config.MINIO_SECRET_KEY
            self.secure = current_config.MINIO_SECURE
            self.bucket_name = current_config.MINIO_BUCKET_NAME
            self.webui_url = current_config.MINIO_WEBUI_URL
            self.api_url = current_config.MINIO_API_URL
            
            # 初始化MinIO客户端
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
            
            # 确保存储桶存在
            self._ensure_bucket_exists()
            
            logger.info(f"MinIO客户端初始化成功: {self.endpoint}")
            
        except ImportError:
            logger.error("minio库未安装，请运行: pip install minio")
            self.client = None
        except Exception as e:
            logger.error(f"MinIO客户端初始化失败: {str(e)}")
            self.client = None
    
    def _ensure_bucket_exists(self):
        """确保存储桶存在"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"创建存储桶: {self.bucket_name}")
            else:
                logger.info(f"存储桶已存在: {self.bucket_name}")
        except Exception as e:
            logger.error(f"检查/创建存储桶失败: {str(e)}")
            raise
    
    def upload_image(self, local_file_path: str, object_name: str) -> Optional[str]:
        """
        上传图片到MinIO
        
        Args:
            local_file_path: 本地图片文件路径
            object_name: MinIO中的对象名称
            
        Returns:
            MinIO访问URL，失败返回None
        """
        if not self.client:
            logger.error("MinIO客户端未初始化")
            return None
        
        try:
            # 检查本地文件是否存在
            if not os.path.exists(local_file_path):
                logger.error(f"本地文件不存在: {local_file_path}")
                return None
            
            # 上传文件到MinIO
            self.client.fput_object(
                self.bucket_name,
                object_name,
                local_file_path
            )
            
            # 生成访问URL
            image_url = f"{self.api_url}/{self.bucket_name}/{object_name}"
            
            logger.info(f"图片上传成功: {local_file_path} -> {image_url}")
            return image_url
            
        except Exception as e:
            logger.error(f"图片上传失败: {str(e)}")
            return None
    
    def upload_paper_image(self, local_file_path: str, paper_id: int, journal_issue: str) -> Optional[str]:
        """
        上传论文图片到MinIO，使用有意义的对象名称
        
        Args:
            local_file_path: 本地图片文件路径
            paper_id: 论文ID
            journal_issue: 期刊期号
            
        Returns:
            MinIO访问URL，失败返回None
        """
        # 生成有意义的对象名称
        file_extension = Path(local_file_path).suffix.lower()
        object_name = f"papers/{journal_issue}/paper_{paper_id}_image{file_extension}"
        
        return self.upload_image(local_file_path, object_name)
    
    def delete_image(self, object_name: str) -> bool:
        """
        从MinIO删除图片
        
        Args:
            object_name: MinIO中的对象名称
            
        Returns:
            删除成功返回True，失败返回False
        """
        if not self.client:
            logger.error("MinIO客户端未初始化")
            return False
        
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"图片删除成功: {object_name}")
            return True
        except Exception as e:
            logger.error(f"图片删除失败: {str(e)}")
            return False
    
    def list_images(self, prefix: str = "") -> list:
        """
        列出存储桶中的图片
        
        Args:
            prefix: 对象名称前缀
            
        Returns:
            图片对象列表
        """
        if not self.client:
            logger.error("MinIO客户端未初始化")
            return []
        
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            image_list = []
            
            for obj in objects:
                image_list.append({
                    'name': obj.object_name,
                    'size': obj.size,
                    'last_modified': obj.last_modified
                })
            
            return image_list
        except Exception as e:
            logger.error(f"列出图片失败: {str(e)}")
            return []


# 创建全局MinIO服务实例
minio_service = MinioService()
