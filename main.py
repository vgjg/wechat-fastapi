import os
import logging
from typing import Optional
import json
from datetime import datetime

# 导入 FastAPI 核心模块
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from essay_handler import EssayHandler
from wechat_handler import WeChatHandler

# --- 配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 初始化 FastAPI 应用
app = FastAPI()

# 初始化处理器
# EssayHandler 负责数据存储
essay_handler = EssayHandler()
# WeChatHandler 负责微信 API 交互
wechat_handler = WeChatHandler(essay_handler=essay_handler)


# ==============================================================================
# 辅助函数：生成完整的 HTML 页面 (包含渲染逻辑)
# ==============================================================================

def generate_html_content(
        essays_data: list,
        form_message: Optional[str] = None,
        push_message: Optional[str] = None
) -> str:
    """
    根据数据和消息生成完整的 HTML 页面内容。

    Args:
        essays_data: 已收集的论文信息列表。
        form_message: 论文信息表单提交后的消息。
        push_message: 论文推送操作后的消息。
    """

    # 辅助函数：根据状态设置消息框样式
    def get_message_class(message: str) -> str:
        if "成功" in message:
            return "bg-green-100 text-green-700 border-green-400"
        elif "失败" in message or "错误" in message:
            return "bg-red-100 text-red-700 border-red-400"
        else:
            return "bg-yellow-100 text-yellow-700 border-yellow-400"

    # --- 渲染论文列表 --- (负责将数据变成网页上的列表)
    essays_html = ""
    if essays_data:
        for i, data in enumerate(essays_data, 1):
            essays_html += f"""
            <li class="p-4 bg-white rounded-lg shadow-md mb-3 border-l-4 border-blue-500">
                <p class="font-bold text-lg text-gray-800">No. {i}: {data.get('论文标题', 'N/A')}</p>
                <p class="text-sm text-gray-600">作者: {data.get('作者', 'N/A')}</p>
                <p class="text-sm text-gray-600">章节: {data.get('章节', 'N/A')}</p>
                <p class="text-xs text-gray-400 mt-1">提交时间: {data.get('提交时间', 'N/A')}</p>
            </li>
            """
    else:
        essays_html = '<li class="text-center text-gray-500 py-4">暂无已收集的论文信息。</li>'

    # --- 渲染表单消息框 --- (负责将提交状态变成提示框)
    form_message_html = ""
    if form_message:
        form_message_html = f"""
        <div class="mt-4 p-3 rounded-lg border {get_message_class(form_message)}">
            <p class="font-medium">{form_message}</p>
        </div>
        """

    # --- 渲染推送消息框 --- (负责将推送状态变成提示框)
    push_message_html = ""
    if push_message:
        push_message_html = f"""
        <div class="mt-4 p-3 rounded-lg border {get_message_class(push_message)}">
            <p class="font-medium">{push_message}</p>
        </div>
        """

    # --- 完整的 HTML 模板 ---
    html_template = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>论文信息管理面板</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body {{ font-family: 'Inter', sans-serif; background-color: #f7f9fc; }}
            .container {{ max-width: 900px; }}
            .card {{ background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.06); }}
        </style>
    </head>
    <body>
        <div class="container mx-auto p-4 sm:p-8">
            <header class="text-center mb-8">
                <h1 class="text-4xl font-bold text-blue-700">论文信息管理面板</h1>
                <p class="text-sm text-gray-500 mt-2">点击“推送”按钮会导致页面刷新，因为我们没有使用 JavaScript。</p>
            </header>

            <!-- A. 论文信息收集表单 -->
            <div class="card p-6 mb-8">
                <h2 class="text-2xl font-semibold text-gray-800 mb-4">A. 论文信息收集</h2>

                <form action="/submit_essay" method="post" class="space-y-4">
                    <div>
                        <label for="title" class="block text-sm font-medium text-gray-700">论文标题</label>
                        <input type="text" id="title" name="title" required
                               class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                    </div>
                    <div>
                        <label for="author" class="block text-sm font-medium text-gray-700">作者</label>
                        <input type="text" id="author" name="author" required
                               class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                    </div>
                    <div>
                        <label for="chapter" class="block text-sm font-medium text-gray-700">章节</label>
                        <input type="text" id="chapter" name="chapter" required
                               class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                    </div>
                    <button type="submit"
                            class="w-full px-4 py-2 bg-blue-600 text-white font-semibold rounded-lg shadow-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition duration-150">
                        提交论文信息
                    </button>
                </form>
                {form_message_html}
            </div>

            <!-- B. 已收集的信息列表 -->
            <div class="card p-6 mb-8">
                <h2 class="text-2xl font-semibold text-gray-800 mb-4">B. 已收集的论文信息</h2>
                <ul class="space-y-3">
                    {essays_html}
                </ul>
            </div>

            <!-- C. 论文推送管理 (无 JavaScript 实现) -->
            <div class="card p-6">
                <h2 class="text-2xl font-semibold text-gray-800 mb-4">C. 论文推送管理</h2>
                <p class="text-sm text-gray-600 mb-4">点击下方按钮，将最新的论文信息推送给所有已关注公众号的用户。</p>

                <!-- 传统表单提交：点击后，页面会跳转到 /push_all_essays，服务器处理完后重定向回来 -->
                <form action="/push_all_essays" method="post">
                    <button type="submit" id="push-button"
                            class="w-full sm:w-auto px-6 py-2 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition duration-150">
                        主动推送最新信息
                    </button>
                </form>

                {push_message_html}
            </div>

        </div>
    </body>
    </html>
    """
    return html_template


# ==============================================================================
# 路由定义
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request, form_status: Optional[str] = None, push_status: Optional[str] = None):
    """
    主页路由：加载所有数据并渲染页面。
    同时检查 URL 中的状态参数，以显示消息。
    """

    # 1. 读取所有已保存的论文数据
    essays = essay_handler.get_all_essays()

    # 2. 根据 URL 参数设置消息 (这是 /submit_essay 重定向回来带的状态)
    form_message = None
    if form_status == "success":
        form_message = "✅ 论文信息提交成功！"
    elif form_status == "error":
        form_message = "❌ 论文信息提交失败，请检查输入或文件权限！"

    # 3. 根据 URL 参数设置消息 (这是 /push_all_essays 重定向回来带的状态)
    push_message = None
    if push_status == "success":
        push_message = "✅ 论文信息已成功推送到所有关注用户！"
    elif push_status == "error":
        push_message = "❌ 论文推送失败，请检查微信公众号配置或网络连接！"
    elif push_status == "no_essay":
        push_message = "⚠️ 推送任务完成，但没有最新的论文信息可供推送。"

    # 4. 生成并返回 HTML
    html_content = generate_html_content(
        essays_data=essays,
        form_message=form_message,
        push_message=push_message
    )
    return html_content


@app.post("/submit_essay")
async def submit_essay(
        title: str = Form(...),
        author: str = Form(...),
        chapter: str = Form(...)
):
    """
    处理论文信息提交的路由。
    """
    success = essay_handler.save_essay_data(title=title, author=author, chapter=chapter)

    # 提交成功或失败后，重定向回主页并带上状态参数 (HTTP 303 See Other)
    if success:
        return RedirectResponse(url="/?form_status=success", status_code=303)
    else:
        return RedirectResponse(url="/?form_status=error", status_code=303)


@app.post("/push_all_essays")
async def push_all_essays():
    """
    处理主动推送请求的路由。（无 JavaScript 实现）
    """
    logger.info("开始执行主动推送所有最新论文信息的任务...")

    try:
        # 1. 获取最新论文数据
        latest_essay = essay_handler.get_latest_essay()

        if not latest_essay:
            # 没有论文可推
            logger.warning("没有可推送的论文信息。")
            return RedirectResponse(url="/?push_status=no_essay", status_code=303)

        # 2. 格式化推送内容
        push_content = f"【最新论文推送】\n\n" \
                       f"标题: 《{latest_essay.get('论文标题', 'N/A')}》\n" \
                       f"作者: {latest_essay.get('作者', 'N/A')}\n" \
                       f"章节: {latest_essay.get('章节', 'N/A')}\n" \
                       f"提交时间: {latest_essay.get('提交时间', 'N/A')}"

        # 3. 获取所有 OpenID
        all_openids = essay_handler.get_all_openids()

        # 4. 执行批量推送
        success_count, failure_count = wechat_handler.push_to_all_subscribers(push_content, all_openids)

        if success_count > 0:
            # 成功后，重定向回主页，并带上成功状态
            return RedirectResponse(url="/?push_status=success", status_code=303)
        else:
            # 失败后，重定向回主页，并带上错误状态
            return RedirectResponse(url="/?push_status=error", status_code=303)

    except Exception as e:
        logger.error(f"推送过程中发生致命错误: {e}")
        # 发生异常，重定向回主页，并带上错误状态
        return RedirectResponse(url="/?push_status=error", status_code=303)


# 微信服务器验证接口（保持不变）
@app.get("/wechat")
async def wechat_verification(signature: str, timestamp: str, nonce: str, echostr: str):
    """微信公众号服务器验证接口"""
    if wechat_handler.verify_signature(signature, timestamp, nonce):
        return PlainTextResponse(echostr)
    raise HTTPException(status_code=400, detail="Signature verification failed")


@app.post("/wechat")
async def wechat_message(request: Request):
    """接收微信公众号用户消息的接口"""
    body = await request.body()
    reply_xml, content_type = wechat_handler.process_and_reply(body)
    return PlainTextResponse(content=reply_xml, media_type=content_type)