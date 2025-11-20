import hashlib
import time
import xml.etree.ElementTree as ET
import logging
import requests
import json
from typing import Tuple, Optional, Set
from essay_handler import EssayHandler

logger = logging.getLogger("wechat_handler")


class WeChatHandler:
    # 🚨🚨 请替换为您自己的微信公众号配置信息 🚨🚨
    def __init__(self, essay_handler: EssayHandler):
        # ⚠️ 替换为您的配置 ⚠️
        self.token = "YOUR_WECHAT_TOKEN"
        self.app_id = "YOUR_WECHAT_APPID"
        self.app_secret = "YOUR_WECHAT_APPSECRET"

        self.essay_handler = essay_handler

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _fetch_access_token(self) -> bool:
        """实际向微信 API 请求 Access Token"""
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get("access_token"):
                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 7200)
                # 提前 5 分钟过期，防止临界点失败
                self._token_expires_at = time.time() + expires_in - 300
                logger.info("Access Token 获取成功并已缓存。")
                return True
            else:
                logger.error(f"Access Token 获取失败，微信返回错误: {data}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"请求微信 Access Token 接口失败: {e}")
            return False

    def get_access_token(self) -> Optional[str]:
        """获取 Access Token。如果缓存中的 token 未过期，则返回缓存；否则请求新的 token。"""
        if self._access_token and time.time() < self._token_expires_at:
            logger.debug("使用缓存中的 Access Token。")
            return self._access_token

        logger.info("Access Token 已过期或首次获取，正在请求新的 token...")

        if self._fetch_access_token():
            return self._access_token
        else:
            return None

    def verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        """校验微信服务器推送的签名。"""
        s = [self.token, timestamp, nonce]
        s.sort()
        s_str = "".join(s).encode('utf-8')
        sha1 = hashlib.sha1()
        sha1.update(s_str)
        calc_signature = sha1.hexdigest()
        return calc_signature == signature

    def send_text_message(self, openid: str, content: str) -> bool:
        """[主动方法] 通过客服消息接口向指定 OpenID 发送文本消息。"""
        access_token = self.get_access_token()
        if not access_token:
            logger.error("无法获取 Access Token，消息发送失败。")
            return False

        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={access_token}"
        message_data = {
            "touser": openid,
            "msgtype": "text",
            "text": {
                "content": content
            }
        }

        try:
            # 使用 try/except 配合 requests 确保网络请求健壮性
            response = requests.post(url, json=message_data, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get("errcode") == 0:
                logger.debug(f"成功向 OpenID {openid} 发送客服消息。")
                return True
            else:
                logger.error(f"向 OpenID {openid} 发送消息失败，微信返回错误: {data}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"请求微信客服消息接口失败: {e}")
            return False

    def push_to_all_subscribers(self, push_content: str, openids: Set[str]) -> Tuple[int, int]:
        """
        批量向所有已记录的 OpenID 推送格式化后的内容。
        返回 (成功数量, 失败数量)。
        """
        success_count = 0
        failure_count = 0

        if not openids:
            logger.warning("没有已记录的 OpenID，无法执行推送。")
            return 0, 0

        logger.info(f"开始批量推送，目标用户数: {len(openids)}")

        for openid in openids:
            # 调用单条消息发送方法
            if self.send_text_message(openid, push_content):
                success_count += 1
            else:
                failure_count += 1

        logger.info(f"批量推送任务完成。成功: {success_count}, 失败: {failure_count}")
        return success_count, failure_count

    def process_and_reply(self, body: bytes) -> Tuple[str, str]:
        """处理接收到的用户消息并生成回复。"""
        try:
            xml_tree = ET.fromstring(body)
            to_user = xml_tree.find('ToUserName').text
            from_user = xml_tree.find('FromUserName').text
            msg_type = xml_tree.find('MsgType').text

            # 记录用户的 OpenID
            if from_user:
                self.essay_handler.save_openid(from_user)

            reply_content = ""
            if msg_type == 'text':
                user_msg = xml_tree.find('Content').text
                reply_content = f"您已发送消息：[{user_msg}]。\n\n当前系统专注于论文信息收集和展示，如有需要，请访问Web页面进行操作。"
            elif msg_type == 'event':
                event = xml_tree.find('Event').text
                if event == 'subscribe':
                    reply_content = "欢迎关注！您的 OpenID 已记录，我们将及时向您推送最新的论文信息摘要。请访问Web页面提交论文信息。"
                else:
                    reply_content = "当前系统已记录您的ID。发送任意消息可重新触发推送。"
            else:
                reply_content = "当前系统仅支持文本消息。"

            reply_xml = self._generate_reply_xml(from_user, to_user, reply_content)
            return reply_xml, "application/xml"

        except Exception as e:
            logger.error(f"Error processing WeChat message: {e}")
            # 返回一个基本的错误回复 XML
            return self._generate_reply_xml(to_user="temp", from_user="temp", content="处理失败"), "application/xml"

    def _generate_reply_xml(self, to_user: str, from_user: str, content: str) -> str:
        """生成标准的微信文本回复 XML 结构。"""
        reply_template = """
        <xml>
        <ToUserName><![CDATA[{}]]></ToUserName>
        <FromUserName><![CDATA[{}]]></FromUserName>
        <CreateTime>{}</CreateTime>
        <MsgType><![CDATA[text]]></MsgType>
        <Content><![CDATA[{}]]></Content>
        </xml>
        """
        # 注意: 实际微信 API 的 to/from 是反过来的
        return reply_template.format(to_user, from_user, int(time.time()), content)