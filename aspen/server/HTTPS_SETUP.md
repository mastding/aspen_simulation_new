# Aspen Agent HTTPS 配置指南

## 概述

aspenagent.py 现已支持 HTTPS 模式启动，提供更安全的通信方式。

## 快速开始

### 方式一：使用自动生成的临时证书（推荐用于开发测试）

直接运行服务，Flask 会自动生成临时证书：

```bash
python aspenagent.py
```

**注意**: 需要安装 `pyOpenSSL` 库才能使用 adhoc 模式：

```bash
pip install pyOpenSSL
```

### 方式二：使用自签名证书

1. 生成自签名证书：

```bash
python generate_cert.py
```

这将在当前目录生成 `cert.pem` 和 `key.pem` 文件。

2. 运行服务：

```bash
python aspenagent.py
```

服务会自动检测并使用这些证书文件。

### 方式三：使用自定义证书路径

通过环境变量指定证书路径：

**Windows CMD:**
```cmd
set SSL_CERT_FILE=D:\path\to\your\cert.pem
set SSL_KEY_FILE=D:\path\to\your\key.pem
python aspenagent.py
```

**Windows PowerShell:**
```powershell
$env:SSL_CERT_FILE="D:\path\to\your\cert.pem"
$env:SSL_KEY_FILE="D:\path\to\your\key.pem"
python aspenagent.py
```

### 方式四：在 .env 文件中配置

编辑 `aspen/.env` 文件，添加：

```env
SSL_CERT_FILE=cert.pem
SSL_KEY_FILE=key.pem
ASPEN_SIMULATOR_PORT=6000
```

## 访问服务

启动后，服务将运行在 HTTPS 模式：

```
https://127.0.0.1:6000
```

## 客户端连接

### Python 客户端示例

```python
import requests

# 开发环境：忽略SSL证书验证（仅用于自签名证书）
response = requests.post(
    'https://127.0.0.1:6000/run-aspen-simulation',
    json=your_data,
    verify=False  # 忽略证书验证
)

# 生产环境：使用有效证书
response = requests.post(
    'https://127.0.0.1:6000/run-aspen-simulation',
    json=your_data,
    verify=True  # 验证证书
)
```

### JavaScript/前端客户端

```javascript
// 使用 fetch API
fetch('https://127.0.0.1:6000/run-aspen-simulation', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(data)
})
.then(response => response.json())
.then(data => console.log(data));
```

## 生产环境部署

对于生产环境，建议：

1. **使用正式的SSL证书**（如 Let's Encrypt）
2. **配置反向代理**（如 Nginx）处理 HTTPS
3. **不要使用 Flask 内置服务器**，改用生产级 WSGI 服务器（如 Gunicorn + Nginx）

### Nginx 反向代理示例

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:6000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 故障排查

### 问题：启动时提示找不到证书文件

**解决方案**：
- 运行 `python generate_cert.py` 生成证书
- 或安装 `pyOpenSSL` 使用 adhoc 模式
- 或通过环境变量指定正确的证书路径

### 问题：浏览器显示"不安全"警告

**原因**：使用自签名证书

**解决方案**：
- 开发环境：可以忽略警告继续访问
- 生产环境：使用正式的SSL证书

### 问题：客户端连接失败

**检查项**：
1. 确认服务已启动并监听正确端口
2. 确认使用 `https://` 而不是 `http://`
3. 如使用自签名证书，客户端需要禁用证书验证或信任该证书

## 依赖库

HTTPS 模式需要以下额外依赖：

```bash
# 使用 adhoc 模式（自动生成临时证书）
pip install pyOpenSSL

# 生成自签名证书
pip install cryptography
```

## 安全建议

1. **不要将私钥文件提交到版本控制系统**
2. **定期更新SSL证书**
3. **生产环境使用强密码保护私钥**
4. **考虑使用证书管理工具**（如 certbot）
5. **启用 HSTS（HTTP Strict Transport Security）**
