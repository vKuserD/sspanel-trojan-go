# SSPanel-Trojan-go

一个基于Python3构建的Trojan-go动态用户管理小工具

**该项目仅为个人兴趣，不提供任何支持。使用时请自行承担风险**

**因代码实现较为糟糕，现已停止维护。**

已实现的功能:

- 从sspanel中加载用户列表
- 从sspanel中设置节点限速
- 同步删除sspanel中不存在的账户
- 同步更新sspenal中的用户限速
- 汇报用户流量到sspanel中

# 使用方法

## 安装Python依赖

```bash
pip install -r requirements.txt
```

## 程序配置

复制示例配置文件 config.example.ini 重命名为 config.ini

<details>
  <summary>点击查看示例文件</summary>

```ini
[sspanel]
api = https://example.com
key = abcde
id = 1
interval = 60

[trojan_server]
hostname = localhost
port = 1234

[trojan_client]
executable = /opt/trojan-go/trojan-go
remote_host = localhost
remote_port = 443
local_port = 5566

[probe]
enabled = true
interval = 60
auto_restart = true
test_url = http://www.bing.com
service = trojan-go.service

[executor]
enabled = true
```
</details>

## 启动程序

```bash
python3 --config config.ini
```

## 配置文件详解

### sspanel 部分

- api: sspanel 面板API地址
- key: sspanel 面板设置的api key
- id: sspanel 面板中节点id
- interval: 更新间隔 （需与sspanel面板中设置的值一致）

## trojan_server 部分

- hostname: trojan go 服务器端api地址，一般为本机（127.0.0.1）
- port: trojan go 服务器端api端口

### trojan_client 部分

- executable: trojan go可执行文件路径
- remote_host: trojan-go的连入地址 （在客户端中使用的地址）
- remote_port: trojan-go的连入端口 （在客户端中使用的端口，默认为443）
- local_port: 任意一个不重复的端口，用于状态检查

### probe 部分

- enabled: 是否启用状态检查
- interval: 状态检查间隔时间
- auto_restart: 状态检查失败时候，是否自动重启trojan-go
- test_url: 用于状态检查的地址
- service: 需要重启的服务名字，默认（trojan-go.service）
