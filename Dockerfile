# --- 1. 基础镜像和环境设置 ---
FROM runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ="Etc/UTC"
ENV COMFYUI_PATH=/root/comfy/ComfyUI
ENV VENV_PATH=/venv

# --- 2. 安装系统依赖 ---
RUN apt-get update && apt-get install -y \
    curl \
    git \
    ffmpeg \
    wget \
    unzip \
    build-essential \
    ninja-build \
    && apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# --- 3. 设置 Python 虚拟环境 (VENV) ---
RUN python -m venv $VENV_PATH
ENV PATH="$VENV_PATH/bin:$PATH"
RUN /venv/bin/python -m pip install --upgrade pip

# --- 4. 安装 ComfyUI 和核心 Python 包 ---
RUN /venv/bin/python -m pip install comfy-cli
RUN comfy --skip-prompt install --nvidia --cuda-version 12.9

# --- 关键修改：明确安装所有handler需要的依赖 ---
RUN /venv/bin/python -m pip install \
    opencv-python \
    imageio-ffmpeg \
    runpod \
    requests \
    websocket-client \
    boto3 \
    huggingface-hub

# --- 5. 创建 WanVideo 模型目录 ---
RUN mkdir -p \
    $COMFYUI_PATH/models/unet \
    $COMFYUI_PATH/models/text_encoders \
    $COMFYUI_PATH/models/vae \
    $COMFYUI_PATH/models/clip_vision \
    $COMFYUI_PATH/models/loras \
    $COMFYUI_PATH/models/wav2vec2

# --- 6. 下载 WanVideo 模型文件 ---
# Main I2V model FP8 (for new workflow)
RUN wget -O $COMFYUI_PATH/models/unet/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors \
    "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors"

# InfiniteTalk model FP16 (for new workflow)
RUN /venv/bin/huggingface-cli download Kijai/WanVideo_comfy \
    InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors \
    --local-dir /tmp/infinitetalk_fp16_dl && \
    mv /tmp/infinitetalk_fp16_dl/InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors \
       $COMFYUI_PATH/models/unet/Wan2_1-InfiniTetalk-Single_fp16.safetensors && \
    rm -rf /tmp/infinitetalk_fp16_dl

# VAE BF16 (Specific name for new workflow)
RUN wget -O $COMFYUI_PATH/models/vae/Wan2_1_VAE_bf16.safetensors \
    "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors"

# Distill LoRA rank64 (Specific name for new workflow)
RUN wget -O $COMFYUI_PATH/models/loras/Wan21_I2V_14B_lightx2v_cfg_step_distill_lora_rank64.safetensors \
    "https://huggingface.co/lightx2v/Wan2.1-I2V-14B-480P-StepDistill-CfgDistill-Lightx2v/resolve/main/loras/Wan21_I2V_14B_lightx2v_cfg_step_distill_lora_rank64.safetensors"

# rCM LoRA (New for this workflow)
RUN wget -O $COMFYUI_PATH/models/loras/Wan_2_1_T2V_14B_rCM_lora_average_rank_83_bf16.safetensors \
    "https://huggingface.co/Kijai/WanVideo_comfy/resolve/6654d68213b74e05ca1b89c05d2f1b3f10670a79/LoRAs/rCM/Wan_2_1_T2V_14B_rCM_lora_average_rank_83_bf16.safetensors"

# --- 7. 安装 WanVideo 自定义节点 ---
# Main WanVideo wrapper
RUN git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git \
    $COMFYUI_PATH/custom_nodes/ComfyUI-WanVideoWrapper && \
    cd $COMFYUI_PATH/custom_nodes/ComfyUI-WanVideoWrapper && \
    /venv/bin/python -m pip install -r requirements.txt || true

# ComfyUI Layer Style (Required for ImageScaleByAspectRatio)
RUN git clone https://github.com/chflame163/ComfyUI_LayerStyle.git \
    $COMFYUI_PATH/custom_nodes/ComfyUI_LayerStyle && \
    cd $COMFYUI_PATH/custom_nodes/ComfyUI_LayerStyle && \
    /venv/bin/python -m pip install -r requirements.txt || true

# ComfyUI JW Nodes (Required for JWInteger/JWFloat)
RUN git clone https://github.com/StartHua/ComfyUI_JWNodes.git \
    $COMFYUI_PATH/custom_nodes/ComfyUI_JWNodes && \
    cd $COMFYUI_PATH/custom_nodes/ComfyUI_JWNodes && \
    /venv/bin/python -m pip install -r requirements.txt || true

# Comfyroll Custom Nodes (Required for CR Prompt Text)
RUN git clone https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git \
    $COMFYUI_PATH/custom_nodes/ComfyUI_Comfyroll_CustomNodes && \
    cd $COMFYUI_PATH/custom_nodes/ComfyUI_Comfyroll_CustomNodes && \
    /venv/bin/python -m pip install -r requirements.txt || true

# Audio separation nodes
RUN git clone https://github.com/christian-byrne/audio-separation-nodes-comfyui.git \
    $COMFYUI_PATH/custom_nodes/audio-separation-nodes-comfyui && \
    cd $COMFYUI_PATH/custom_nodes/audio-separation-nodes-comfyui && \
    /venv/bin/python -m pip install -r requirements.txt || true

# Video helper suite (for VHS_VideoCombine)
RUN git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git \
    $COMFYUI_PATH/custom_nodes/ComfyUI-VideoHelperSuite && \
    cd $COMFYUI_PATH/custom_nodes/ComfyUI-VideoHelperSuite && \
    /venv/bin/python -m pip install -r requirements.txt || true

# KJNodes (utilities)
RUN git clone https://github.com/kijai/ComfyUI-KJNodes.git \
    $COMFYUI_PATH/custom_nodes/ComfyUI-KJNodes && \
    cd $COMFYUI_PATH/custom_nodes/ComfyUI-KJNodes && \
    /venv/bin/python -m pip install -r requirements.txt || true

# --- 8. 安装 WanVideo Python 依赖 ---
RUN /venv/bin/python -m pip install \
    transformers \
    soundfile \
    librosa \
    einops \
    safetensors \
    demucs \
    accelerate

# --- 9. 安装 SageAttention (单独安装以避免编译问题) ---
# Only compile for RTX 5090 (sm_120) to speed up build time
ENV TORCH_CUDA_ARCH_LIST="12.0"
RUN /venv/bin/python -m pip install wheel setuptools
RUN /venv/bin/python -m pip install sageattention --no-build-isolation

# --- 8. 复制脚本并设置权限 ---
# --- 关键修改：不再复制 workflow_api.json ---
COPY src/start.sh /root/start.sh
COPY src/rp_handler.py /root/rp_handler.py
COPY src/ComfyUI_API_Wrapper.py /root/ComfyUI_API_Wrapper.py

RUN chmod +x /root/start.sh

# --- 9. 定义容器启动命令 ---
CMD ["/root/start.sh"]
