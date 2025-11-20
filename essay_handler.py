import json
import os
from datetime import datetime
from typing import List, Dict, Set, Optional
import logging

logger = logging.getLogger("essay_handler")


class EssayHandler:
    def __init__(self, essays_file="essays.json", openids_file="openids.json"):
        # 用于存储已提交的论文信息
        self.essays_file = essays_file
        # 用于存储所有关注公众号用户的 OpenID
        self.openids_file = openids_file
        self.initialize_files()

    def initialize_files(self):
        """初始化数据文件，如果不存在则创建空的 JSON 文件。"""
        if not os.path.exists(self.essays_file):
            with open(self.essays_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=4)
            logger.info(f"创建空的论文数据文件: {self.essays_file}")

        if not os.path.exists(self.openids_file):
            # OpenIDs 存储为一个集合，去重方便
            with open(self.openids_file, 'w', encoding='utf-8') as f:
                json.dump(list(), f, ensure_ascii=False, indent=4)
            logger.info(f"创建空的 OpenID 数据文件: {self.openids_file}")

    def _load_data(self, filename: str) -> list:
        """从 JSON 文件加载数据。"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载文件 {filename} 失败: {e}")
            return []

    def _save_data(self, filename: str, data: list):
        """将数据保存到 JSON 文件。"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"保存文件 {filename} 失败: {e}")
            return False

    # --- 论文信息相关方法 ---

    def get_all_essays(self) -> List[Dict]:
        """获取所有已保存的论文信息，按时间倒序排列。"""
        # 数据通常已经按提交顺序保存，这里直接返回
        return list(reversed(self._load_data(self.essays_file)))

    def get_latest_essay(self) -> Optional[Dict]:
        """获取最新提交的论文信息。"""
        essays = self._load_data(self.essays_file)
        if essays:
            # 列表中的最后一个元素是最新提交的
            return essays[-1]
        return None

    def save_essay_data(self, title: str, author: str, chapter: str) -> bool:
        """保存新的论文信息。"""
        new_essay = {
            "论文标题": title,
            "作者": author,
            "章节": chapter,
            "提交时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        essays = self._load_data(self.essays_file)
        essays.append(new_essay)
        return self._save_data(self.essays_file, essays)

    # --- OpenID (微信用户ID) 相关方法 ---

    def get_all_openids(self) -> Set[str]:
        """获取所有已记录的 OpenID 集合。"""
        openids_list = self._load_data(self.openids_file)
        return set(openids_list)

    def save_openid(self, openid: str) -> bool:
        """保存一个新的 OpenID，自动去重。"""
        openids_set = self.get_all_openids()

        # 只有当 OpenID 是新的时候才需要保存
        if openid not in openids_set:
            openids_set.add(openid)
            return self._save_data(self.openids_file, list(openids_set))
        return True  # 已经存在，视为成功