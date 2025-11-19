# 文件名: src/ComfyUI_API_Wrapper.py

import websocket
import uuid
import json
import urllib.request
import urllib.parse
from urllib.parse import urlparse
import os

class ComfyUI_API_Wrapper:
    def __init__(self, server_address, client_id, output_path):
        self.server_address = server_address
        self.client_id = client_id
        self.output_path = output_path

    def queue_prompt_and_get_images(self, prompt, output_node_id):
        prompt_id = self.queue_prompt(prompt).get('prompt_id')
        if not prompt_id:
            return None

        ws_url = f"ws://{urlparse(self.server_address).netloc}/ws?clientId={self.client_id}"
        ws = websocket.WebSocket()
        ws.connect(ws_url)

        try:
            while True:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message.get('type') == 'executed' and message.get('data', {}).get('prompt_id') == prompt_id:
                        history = self.get_history(prompt_id)
                        if history and prompt_id in history:
                            outputs = history[prompt_id]['outputs'].get(output_node_id, {})
                            # Try multiple output keys: images, audio, gifs (VHS_VideoCombine)
                            return (outputs.get('images') or
                                    outputs.get('audio') or
                                    outputs.get('gifs') or
                                    [])
        finally:
            ws.close()

        return None

    def queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"{self.server_address}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def get_image(self, filename, subfolder, folder_type):
        url = f"{self.server_address}/view?filename={urllib.parse.quote_plus(filename)}&subfolder={urllib.parse.quote_plus(subfolder)}&type={folder_type}"
        with urllib.request.urlopen(url) as response:
            return response.read()

    def get_history(self, prompt_id):
        with urllib.request.urlopen(f"{self.server_address}/history/{prompt_id}") as response:
            return json.loads(response.read())