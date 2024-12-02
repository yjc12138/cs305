HELP = 'Create         : create an conference\n' \
       'Join [conf_id ]: join a conference with conference ID\n' \
       'Quit           : quit an on-going conference\n' \
       'Cancel         : cancel your on-going conference (only the manager)\n\n'

SERVER_IP = '127.0.0.1'
MAIN_SERVER_PORT = 8888
TIMEOUT_SERVER = 5
# DGRAM_SIZE = 1500  # UDP
LOG_INTERVAL = 2

CHUNK = 1024
CHANNELS = 1  # Channels for audio capture
RATE = 44100  # Sampling rate for audio capture

camera_width, camera_height = 480, 480  # resolution for camera capture

# 服务器配置
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 8000
BUFFER_SIZE = 4096

# 视频配置
VIDEO_PORT = 8001
VIDEO_QUALITY = 80  # JPEG压缩质量
VIDEO_FRAME_RATE = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480

# 音频配置
AUDIO_PORT = 8002
AUDIO_CHUNK = 1024
AUDIO_FORMAT = 'int16'
AUDIO_CHANNELS = 1
AUDIO_RATE = 44100

# 聊天配置
CHAT_PORT = 8003

# 会议配置
MAX_CLIENTS = 10  # 每个会议的最大客户端数
MAX_CONFERENCES = 5  # 最大并行会议数


# 协议消息类型
class MessageType:
       # 会议管理
       CREATE_CONFERENCE = 'create_conference'
       JOIN_CONFERENCE = 'join_conference'
       QUIT_CONFERENCE = 'quit_conference'
       CANCEL_CONFERENCE = 'cancel_conference'

       # 媒体控制
       VIDEO_ON = 'video_on'
       VIDEO_OFF = 'video_off'
       AUDIO_ON = 'audio_on'
       AUDIO_OFF = 'audio_off'

       # 数据传输
       VIDEO_FRAME = 'video_frame'
       AUDIO_DATA = 'audio_data'
       CHAT_MESSAGE = 'chat_message'

       # 状态更新
       CLIENT_LIST = 'client_list'
       CONFERENCE_LIST = 'conference_list'

       # 系统消息
       ERROR = 'error'
       SUCCESS = 'success'


# 会议模式
class ConferenceMode:
       CS = 'client_server'
       P2P = 'peer_to_peer'


# 错误代码
class ErrorCode:
       SUCCESS = 200
       CONFERENCE_NOT_FOUND = 404
       CONFERENCE_FULL = 405
       INVALID_REQUEST = 400
       SERVER_ERROR = 500