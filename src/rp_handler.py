import os
import json
import uuid
import runpod
import base64
import requests
import boto3
from botocore.client import Config
from ComfyUI_API_Wrapper import ComfyUI_API_Wrapper

# --- 全局常量和初始化 ---
COMFYUI_URL = "http://127.0.0.1:8188"
client_id = str(uuid.uuid4())
output_path = "/root/comfy/ComfyUI/output"
api = ComfyUI_API_Wrapper(COMFYUI_URL, client_id, output_path)

# --- 辅助函数: 下载音频文件 ---
def download_audio(url, save_path):
    try:
        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"下载音频文件时出错: {e}")
        return False

# --- 辅助函数: 下载图片文件 ---
def download_image(url, save_path):
    try:
        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"下载图片文件时出错: {e}")
        return False

# --- RunPod Handler ---
def handler(job):
    job_input = job.get('input', {})

    # 1. 直接从输入中获取整个工作流
    workflow = job_input.get('workflow')
    if not workflow or not isinstance(workflow, dict):
        return {"error": "输入错误: 'workflow' 键是必需的，且其值必须是一个有效的JSON对象。"}

    # Cleanup: Remove UI-only nodes (Note, MarkdownNote, Reroute, PrimitiveNode)
    # These nodes are not executable by the backend and can cause validation errors.
    # IMPORTANT: We do NOT remove PrimitiveNode anymore because we replaced JWInteger with it.
    nodes_to_remove = []
    for node_id, node_data in workflow.items():
        if node_data.get("class_type") in ["Note", "MarkdownNote", "Reroute"]:
            nodes_to_remove.append(node_id)
    
    for node_id in nodes_to_remove:
        del workflow[node_id]

    # 创建输入路径
    input_path = "/root/comfy/ComfyUI/input"
    if not os.path.exists(input_path):
        os.makedirs(input_path)

    # 2. (可选) 如果提供了image_url，就自动处理图片加载
    if 'image_url' in job_input:
        image_url = job_input['image_url']

        # 判断文件扩展名
        image_ext = ".png"
        if image_url.lower().endswith(('.jpg', '.jpeg')):
            image_ext = ".jpg"

        image_filename = f"input_{uuid.uuid4()}{image_ext}"
        save_path = os.path.join(input_path, image_filename)

        if not download_image(image_url, save_path):
            return {"error": f"无法从指定的URL下载图片: {image_url}"}

        # 查找并注入到 LoadImage 节点
        load_image_node_id = None
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") == "LoadImage":
                load_image_node_id = node_id
                break

        if load_image_node_id:
            workflow[load_image_node_id]["inputs"]["image"] = image_filename
        else:
            return {"error": "提供了 'image_url' 但在工作流中找不到 'LoadImage' 节点。"}

    # 3. (可选) 如果提供了audio_url，就自动处理音频加载
    if 'audio_url' in job_input:
        audio_url = job_input['audio_url']
        input_path = "/root/comfy/ComfyUI/input"
        if not os.path.exists(input_path):
            os.makedirs(input_path)

        audio_filename = f"input_{uuid.uuid4()}.mp3"
        save_path = os.path.join(input_path, audio_filename)

        if not download_audio(audio_url, save_path):
            return {"error": f"无法从指定的URL下载音频: {audio_url}"}

        load_audio_node_id = None
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") == "LoadAudio":
                load_audio_node_id = node_id
                break

        if load_audio_node_id:
            workflow[load_audio_node_id]["inputs"]["audio"] = audio_filename
        else:
            return {"error": "提供了 'audio_url' 但在工作流中找不到 'LoadAudio' 节点。"}

    # 4. (可选) 如果提供了 width/height/num_frames，就自动处理输出尺寸和帧数
    # 针对 Infinite+Talk V4 工作流的特定节点 ID 处理
    if 'width' in job_input:
        width_value = int(job_input.get('width'))
        # Node 312 是 scaling length (原 JWInteger, 现 PrimitiveNode)
        if "312" in workflow:
            if workflow["312"].get("class_type") in ["PrimitiveNode", "JWInteger"]:
                workflow["312"]["inputs"]["value"] = width_value
                print(f"Set Node 312 (Scale Length) to {width_value}")
        
        # 同时更新 WanVideo 节点作为备份 (如果 link 断了)
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") == "WanVideoImageToVideoMultiTalk":
                workflow[node_id]["inputs"]["width"] = width_value

    if 'height' in job_input:
        height_value = int(job_input.get('height'))
        # WanVideo 节点
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") == "WanVideoImageToVideoMultiTalk":
                workflow[node_id]["inputs"]["height"] = height_value

    if 'num_frames' in job_input:
        frames_value = int(job_input.get('num_frames'))
        # Node 308 是 num_frames (原 JWInteger, 现 PrimitiveNode)
        if "308" in workflow:
            if workflow["308"].get("class_type") in ["PrimitiveNode", "JWInteger"]:
                workflow["308"]["inputs"]["value"] = frames_value
                print(f"Set Node 308 (Num Frames) to {frames_value}")
        
        # 同时也更新 MultiTalkWav2VecEmbeds 作为备份
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") == "MultiTalkWav2VecEmbeds":
                workflow[node_id]["inputs"]["num_frames"] = frames_value

    # 5. 找到最终的输出节点 (VHS_VideoCombine)
    output_node_id = None
    # 优先查找 save_output=True 的节点
    for node_id, node_data in workflow.items():
        if node_data.get("class_type") == "VHS_VideoCombine":
            if node_data.get("inputs", {}).get("save_output") is True:
                output_node_id = node_id
                break
    
    # 如果没找到显式保存的，再找任意一个
    if not output_node_id:
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") == "VHS_VideoCombine":
                output_node_id = node_id
                break

    if not output_node_id:
        return {"error": "工作流中必须包含一个 'VHS_VideoCombine' 节点作为输出。"}

    try:
        # 5. 执行工作流
        output_data = api.queue_prompt_and_get_images(workflow, output_node_id)
        if not output_data:
             return {"error": "执行超时或工作流未生成任何视频输出。"}

        # 6. 上传视频文件到 Cloudflare R2 并返回 URL
        # 初始化 R2 S3 客户端
        s3_client = boto3.client(
            's3',
            endpoint_url=os.environ.get('R2_ENDPOINT_URL'),
            aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY'),
            config=Config(signature_version='s3v4')
        )

        bucket_name = os.environ.get('R2_BUCKET_NAME')
        public_url_base = os.environ.get('R2_PUBLIC_URL')

        video_urls = []
        for video_info in output_data:
            filename = video_info.get("filename")
            if filename:
                # 获取视频字节数据
                video_bytes = api.get_image(filename, video_info.get("subfolder"), video_info.get("type"))

                # 生成唯一的文件名
                unique_filename = f"{uuid.uuid4()}_{filename}"

                # 确定 ContentType
                content_type = 'video/mp4'
                if filename.lower().endswith('.webm'):
                    content_type = 'video/webm'
                elif filename.lower().endswith('.avi'):
                    content_type = 'video/x-msvideo'

                # 上传到 R2
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=unique_filename,
                    Body=video_bytes,
                    ContentType=content_type
                )

                # 构建公开 URL
                video_url = f"{public_url_base}/{unique_filename}"
                video_urls.append(video_url)

        return {"video": video_urls}

    except Exception as e:
        return {"error": f"处理过程中发生未知错误: {str(e)}"}

# --- 启动 RunPod Worker ---
if __name__ == "__main__":
    print("WanVideo 2.1 InfiniteTalk Worker 启动中...")
    runpod.serverless.start({"handler": handler})
