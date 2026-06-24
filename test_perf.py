import requests
import time

# 测试127.0.0.1 vs localhost性能
print("测试API性能...\n")

# 测试127.0.0.1
print("1. 使用127.0.0.1:")
times = []
for i in range(3):
    start = time.time()
    r = requests.get("http://127.0.0.1:8000/", timeout=5)
    elapsed = time.time() - start
    times.append(elapsed)
    print(f"   第{i+1}次: {elapsed*1000:.0f}ms")
print(f"   平均: {sum(times)/len(times)*1000:.0f}ms")

print()

# 测试localhost
print("2. 使用localhost:")
times = []
for i in range(3):
    start = time.time()
    r = requests.get("http://localhost:8000/", timeout=5)
    elapsed = time.time() - start
    times.append(elapsed)
    print(f"   第{i+1}次: {elapsed*1000:.0f}ms")
print(f"   平均: {sum(times)/len(times)*1000:.0f}ms")
