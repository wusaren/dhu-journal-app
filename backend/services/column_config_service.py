"""
列配置服务 - 使用 JSON 文件存储每个期刊的统计表列配置
"""
import os
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 配置存储目录（相对于 backend 目录）
CONFIG_DIR = Path(__file__).parent.parent / 'configs'
CONFIG_DIR.mkdir(exist_ok=True)

class ColumnConfigService:
    """列配置服务类"""
    
    def get_config_file_path(self, journal_id: int) -> Path:
        """获取配置文件的路径"""
        return CONFIG_DIR / f"journal_{journal_id}_columns.json"
    
    def save_config(self, journal_id: int, columns_config: List[Dict]) -> Dict:
        """
        保存期刊的列配置到 JSON 文件
        
        Args:
            journal_id: 期刊ID
            columns_config: 列配置列表，格式: [{'key': 'manuscript_id', 'order': 1}, ...]
        
        Returns:
            {'success': True/False, 'message': '...'}
        """
        try:
            config_file = self.get_config_file_path(journal_id)
            
            # 准备保存的数据
            config_data = {
                'journal_id': journal_id,
                'columns': columns_config,
                'updated_at': None  # 可以添加时间戳
            }
            
            # 保存到 JSON 文件
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存期刊 {journal_id} 的列配置到 {config_file}")
            return {
                'success': True,
                'message': '配置保存成功'
            }
        
        except Exception as e:
            logger.error(f"保存列配置失败: {str(e)}")
            return {
                'success': False,
                'message': f'保存配置失败: {str(e)}'
            }
    
    def load_config(self, journal_id: int) -> Optional[List[Dict]]:
        """
        从 JSON 文件加载期刊的列配置
        
        Args:
            journal_id: 期刊ID
        
        Returns:
            列配置列表，如果文件不存在则返回 None
        """
        try:
            config_file = self.get_config_file_path(journal_id)
            
            if not config_file.exists():
                logger.info(f"期刊 {journal_id} 的配置文件不存在: {config_file}")
                return None
            
            # 读取 JSON 文件
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            columns_config = config_data.get('columns', [])
            logger.info(f"已加载期刊 {journal_id} 的列配置: {len(columns_config)} 列")
            return columns_config
        
        except Exception as e:
            logger.error(f"加载列配置失败: {str(e)}")
            return None
    
    def delete_config(self, journal_id: int) -> Dict:
        """
        删除期刊的列配置文件
        
        Args:
            journal_id: 期刊ID
        
        Returns:
            {'success': True/False, 'message': '...'}
        """
        try:
            config_file = self.get_config_file_path(journal_id)
            
            if not config_file.exists():
                return {
                    'success': False,
                    'message': '配置文件不存在'
                }
            
            # 删除文件
            config_file.unlink()
            logger.info(f"已删除期刊 {journal_id} 的配置文件: {config_file}")
            return {
                'success': True,
                'message': '配置删除成功'
            }
        
        except Exception as e:
            logger.error(f"删除列配置失败: {str(e)}")
            return {
                'success': False,
                'message': f'删除配置失败: {str(e)}'
            }
    
    def has_config(self, journal_id: int) -> bool:
        """
        检查期刊是否有保存的配置
        
        Args:
            journal_id: 期刊ID
        
        Returns:
            True 如果有配置，False 如果没有
        """
        config_file = self.get_config_file_path(journal_id)
        return config_file.exists()

