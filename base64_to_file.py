import json
import base64
import os

# 创建 output 目录（如果不存在）
output_dir = 'output'
os.makedirs(output_dir, exist_ok=True)

# 打开并读取 JSON 文件
with open('response.json', 'r') as file:
    data = json.load(file)

# 遍历 output.images 列表
for image in data['output']['images']:
    # 获取 base64 编码的数据
    base64_data = image['data']
    # 获取文件名
    filename = image['filename']
    # 构建保存路径（output/文件名）
    save_path = os.path.join(output_dir, filename)

    # 解码 base64 数据
    decoded_data = base64.b64decode(base64_data)

    # 将解码后的数据保存为文件
    with open(save_path, 'wb') as img_file:
        img_file.write(decoded_data)

    print(f"文件 {save_path} 已成功保存。")