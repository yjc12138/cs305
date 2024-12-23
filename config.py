HELP_TEXT = """可用命令：
-u [username] : 设置用户名
create        : 创建会议
join [conf_id]: 加入指定ID的会议
quit          : 退出当前会议
cancel        : 取消当前会议（仅管理员）
camera enable : 开启摄像头
camera disable: 关闭摄像头
audio enable  : 开启音频
audio disable : 关闭音频
screen enable : 开启屏幕共享
screen disable: 关闭屏幕共享
-c [message]  : 发送聊天消息
exit          : 退出程序
"""

SERVER_IP = '10.32.141.200'
# '10.27.91.234'
# '10.25.120.234'
# '10.32.141.200'
# '10.32.62.118'
MAIN_SERVER_PORT = 8000
CLIENT_IP = '10.25.120.234'
CLIENT_PORT = 9000
TIMEOUT_SERVER = 5
# DGRAM_SIZE = 1500  # UDP
LOG_INTERVAL = 2

CHUNK = 4096
CHANNELS = 1  # Channels for audio capture
RATE = 44100  # Sampling rate for audio capture

camera_width, camera_height = 240, 240  # resolution for camera capture

BUFFER_SIZE = 65536