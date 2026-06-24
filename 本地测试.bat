# 本地前端测试服务器
# 双击运行此文件，然后浏览器访问 http://localhost:8080
import http.server
import socketserver
import webbrowser
import os

PORT = 8080
DIRECTORY = "medrag_frontend"

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

os.chdir(os.path.dirname(os.path.abspath(__file__)))
with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    print(f"本地服务器已启动: http://localhost:{PORT}")
    print("按 Ctrl+C 停止服务器")
    webbrowser.open(f"http://localhost:{PORT}")
    httpd.serve_forever()
