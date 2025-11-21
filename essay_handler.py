import json
import os
import threading
from datetime import datetime
from typing import List, Dict, Set, Any, Optional
import logging
import pandas as pd

logger = logging.getLogger("essay_handler")


class EssayHandler:
    DATA_DIR = "data"
    # 文件路径常量
    ESSAYS_FILE = os.path.join(DATA_DIR, "essays.xlsx")
    OPENIDS_FILE = os.path.join(DATA_DIR, "openids.json")
    # 消息记录文件路径已更新到 data 目录下
    MESSAGE_EXCEL_PATH = os.path.join(DATA_DIR, "messages.xlsx")

    def __init__(self):
        # 线程锁初始化，用于保护 Excel/JSON 文件的并发读写安全
        self.file_lock = threading.Lock()
        self.initialize_files()

    def initialize_files(self):
        """初始化数据文件和 Excel 文件。"""

        # 1. 确保 data 目录存在
        if not os.path.exists(self.DATA_DIR):
            os.makedirs(self.DATA_DIR)
            logger.info(f"创建数据目录: {self.DATA_DIR}")

        # 2. OpenID 数据 (JSON)
        if not os.path.exists(self.OPENIDS_FILE):
            with open(self.OPENIDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(), f, ensure_ascii=False, indent=4)
            logger.info(f"创建空的 OpenID 数据文件: {self.OPENIDS_FILE}")

        # 3. 论文数据 (Excel)
        if not os.path.exists(self.ESSAYS_FILE):
            # 定义论文数据的表头
            empty_df = pd.DataFrame(columns=['论文标题', '作者', '章节', '提交时间'])
            with self.file_lock:
                try:
                    # 写入 Excel 文件
                    empty_df.to_excel(self.ESSAYS_FILE, index=False)
                    logger.info(f"创建空的论文数据文件: {self.ESSAYS_FILE}")
                except Exception as e:
                    logger.error(f"创建论文 Excel 文件失败: {e}")

        # 4. 微信消息记录 (Excel) - 路径已更新
        if not os.path.exists(self.MESSAGE_EXCEL_PATH):
            empty_df = pd.DataFrame(columns=['接收时间', '发送者ID', '消息类型', '消息内容'])
            with self.file_lock:
                try:
                    empty_df.to_excel(self.MESSAGE_EXCEL_PATH, index=False)
                    logger.info(f"创建空的微信消息记录文件: {self.MESSAGE_EXCEL_PATH}")
                except Exception as e:
                    logger.error(f"创建微信消息 Excel 文件失败: {e}")

    # --- JSON 读写辅助方法 (仅用于 OpenID) ---

    def _load_data(self, filename: str) -> list:
        """从 JSON 文件加载数据。"""
        with self.file_lock:
            try:
                # 检查文件是否存在且非空
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    with open(filename, 'r', encoding='utf-8') as f:
                        return json.load(f)
                else:
                    return []
            except json.JSONDecodeError:
                logger.warning(f"文件 {filename} 内容为空或格式错误，返回空列表。")
                return []
            except Exception as e:
                logger.error(f"加载文件 {filename} 失败: {e}")
                return []

    def _save_data(self, filename: str, data: list):
        """将数据保存到 JSON 文件。"""
        with self.file_lock:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                return True
            except Exception as e:
                logger.error(f"保存文件 {filename} 失败: {e}")
                return False

    # --- 论文信息 Excel 读写方法 ---

    def _load_essays_from_excel(self) -> List[Dict]:
        """从 Excel 文件加载论文数据并转换为列表，返回空列表如果失败。"""
        try:
            # 检查文件是否存在
            if not os.path.exists(self.ESSAYS_FILE):
                logger.warning(f"Excel 文件不存在: {self.ESSAYS_FILE}")
                return []

            # pandas 读取 Excel
            df = pd.read_excel(self.ESSAYS_FILE)

            # 检查是否为空 DataFrame
            if df.empty:
                return []

            # 将 DataFrame 转换为字典列表
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"加载论文 Excel 文件失败: {e}")
            return []

    def _save_essays_to_excel(self, essays: List[Dict]) -> bool:
        """将论文数据列表保存到 Excel 文件。"""
        with self.file_lock:
            try:
                df = pd.DataFrame(essays)
                df.to_excel(self.ESSAYS_FILE, index=False)
                return True
            except Exception as e:
                logger.error(f"保存论文 Excel 文件失败: {e}")
                return False

    # --- 论文信息相关方法 (保持不变) ---

    def get_all_essays(self) -> List[Dict]:
        """获取所有已保存的论文信息，按提交时间倒序排列 (Excel读取)。"""
        essays = self._load_essays_from_excel()
        # 反转列表，使最新的提交排在前面
        return list(reversed(essays))

    def get_latest_essay(self) -> Optional[Dict]:
        """获取最新提交的论文信息 (Excel读取)。"""
        essays = self._load_essays_from_excel()
        return essays[-1] if essays else None

    def save_essay_data(self, title: str, author: str, chapter: str) -> bool:
        """保存新的论文信息 (Excel写入)。"""
        try:
            new_essay = {
                "论文标题": title,
                "作者": author,
                "章节": chapter,
                "提交时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # 1. 读取所有现有数据
            essays = self._load_essays_from_excel()

            # 如果读取失败，初始化空列表
            if essays is None:
                essays = []

            # 2. 追加新数据
            essays.append(new_essay)

            # 3. 重新写入整个 Excel 文件
            if self._save_essays_to_excel(essays):
                logger.info(f"✅ Saved new essay to Excel: {title} by {author}")
                return True
            else:
                logger.error("❌ 保存到 Excel 文件失败")
                return False

        except Exception as e:
            logger.error(f"❌ 论文数据保存发生错误: {e}")
            return False

    # --- OpenID (微信用户ID) 相关方法 (保持不变) ---

    def get_all_openids(self) -> Set[str]:
        """获取所有已记录的 OpenID 集合。"""
        # 使用正确的路径 self.OPENIDS_FILE
        openids_list = self._load_data(self.OPENIDS_FILE)
        return set(openids_list)

    def save_openid(self, openid: str) -> bool:
        """保存一个新的 OpenID，自动去重。"""
        openids_set = self.get_all_openids()

        if openid not in openids_set:
            openids_set.add(openid)
            # 使用正确的路径 self.OPENIDS_FILE
            return self._save_data(self.OPENIDS_FILE, list(openids_set))
        return True

    # --- 微信消息记录方法 (Excel) - 路径已更新 ---
    def save_message_to_excel(self, message_data: Dict[str, Any]) -> bool:
        """
        将微信消息记录追加写入 Excel 文件。
        """
        # 使用文件锁保护 Excel 读写操作
        with self.file_lock:
            try:
                # 1. 读取现有数据（如果文件存在）- 使用更新后的路径
                if os.path.exists(self.MESSAGE_EXCEL_PATH):
                    df = pd.read_excel(self.MESSAGE_EXCEL_PATH)
                else:
                    # 如果文件不存在，则创建空的DataFrame
                    df = pd.DataFrame(columns=['接收时间', '发送者ID', '消息类型', '消息内容'])

                # 2. 构造新的DataFrame行
                new_row_df = pd.DataFrame([message_data])

                # 3. 追加数据
                df = pd.concat([df, new_row_df], ignore_index=True)

                # 4. 写入Excel - 使用更新后的路径
                df.to_excel(self.MESSAGE_EXCEL_PATH, index=False)
                logger.info(
                    f"✅ 成功记录一条微信消息: 类型={message_data.get('消息类型')}, 发送者={message_data.get('发送者ID')}")
                return True
            except PermissionError:
                logger.error("❌ 写入 Excel 失败！文件可能正在被其他程序打开，请关闭后重试。")
                return False
            except Exception as e:
                logger.error(f"❌ 写入微信消息记录时发生错误: {e}")
                return False