# 本地前端测试服务器
import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8080
DIRECTORY = "medrag_frontend"

# 切换到脚本所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

print(f"="*50)
print(f"本地测试服务器已启动")
print(f"请在浏览器访问: http://localhost:{PORT}/llm_index.html")
print(f"="*50)

with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    try:
        webbrowser.open(f"http://localhost:{PORT}/llm_index.html")
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
