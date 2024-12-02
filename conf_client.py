import asyncio
import socket
import threading
from config import *
from util import *


class ConferenceClient:
    def __init__(self):
        self.is_working = True
        self.server_addr = (SERVER_HOST, SERVER_PORT)
        self.on_meeting = False
        self.conference_id = None
        self.username = None
        self.video_enabled = False
        self.audio_enabled = False

        self.control_socket = None
        self.video_socket = None
        self.audio_socket = None
        self.chat_socket = None

        self.video_cap = None
        self.audio_handler = None

        self.video_thread = None
        self.audio_thread = None
        self.receive_thread = None

    async def connect_to_server(self):
        """连接到服务器"""
        try:
            # 控制连接
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect(self.server_addr)

            # 视频连接
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.video_socket.bind(('', 0))

            # 音频连接
            self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_socket.bind(('', 0))

            # 聊天连接
            self.chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.chat_socket.connect((SERVER_HOST, CHAT_PORT))

            return True
        except Exception as e:
            print(f"连接服务器失败: {e}")
            return False

    def create_conference(self):
        """创建会议"""
        msg = create_message(MessageType.CREATE_CONFERENCE, {
            'username': self.username
        })
        self.control_socket.send(msg)
        response = self.control_socket.recv(BUFFER_SIZE)
        type, _, data = parse_message(response)
        if type == MessageType.SUCCESS:
            self.conference_id = data['conference_id']
            self.on_meeting = True
            self.start_conference()
            return True
        return False

    def join_conference(self, conference_id):
        """加入会议"""
        msg = create_message(MessageType.JOIN_CONFERENCE, {
            'username': self.username,
            'conference_id': conference_id
        })
        self.control_socket.send(msg)
        response = self.control_socket.recv(BUFFER_SIZE)
        type, _, data = parse_message(response)
        if type == MessageType.SUCCESS:
            self.conference_id = conference_id
            self.on_meeting = True
            self.start_conference()
            return True
        return False

    def start_conference(self):
        """启动会议相关线程"""
        if self.on_meeting:
            # 启动视频线程
            self.video_thread = threading.Thread(target=self.video_loop)
            self.video_thread.start()

            # 启动音频线程
            self.audio_thread = threading.Thread(target=self.audio_loop)
            self.audio_thread.start()

            # 启动接收线程
            self.receive_thread = threading.Thread(target=self.receive_loop)
            self.receive_thread.start()

    def video_loop(self):
        """视频循环"""
        self.video_cap = cv2.VideoCapture(0)
        while self.on_meeting and self.video_enabled:
            ret, frame = self.video_cap.read()
            if ret:
                compressed = compress_frame(frame)
                msg = create_message(MessageType.VIDEO_FRAME, {
                    'conference_id': self.conference_id,
                    'username': self.username,
                    'data': compressed
                })
                self.video_socket.sendto(msg, (SERVER_HOST, VIDEO_PORT))
            time.sleep(1 / VIDEO_FRAME_RATE)

    def audio_loop(self):
        """音频循环"""
        self.audio_handler = AudioHandler()
        while self.on_meeting and self.audio_enabled:
            audio_data = self.audio_handler.read_audio()
            if audio_data:
                msg = create_message(MessageType.AUDIO_DATA, {
                    'conference_id': self.conference_id,
                    'username': self.username,
                    'data': audio_data
                })
                self.audio_socket.sendto(msg, (SERVER_HOST, AUDIO_PORT))

    def receive_loop(self):
        """接收循环"""
        while self.on_meeting:
            try:
                data = self.control_socket.recv(BUFFER_SIZE)
                if data:
                    type, timestamp, content = parse_message(data)
                    self.handle_message(type, timestamp, content)
            except Exception as e:
                print(f"接收数据错误: {e}")
                break

    def handle_message(self, msg_type, timestamp, data):
        """处理接收到的消息"""
        if msg_type == MessageType.VIDEO_FRAME:
            # 处理视频帧
            frame = decompress_frame(data['data'])
            # 显示视频帧
            cv2.imshow(f"User: {data['username']}", frame)

        elif msg_type == MessageType.AUDIO_DATA:
            # 处理音频数据
            # 播放音频
            pass

        elif msg_type == MessageType.CHAT_MESSAGE:
            # 显示聊天消息
            print(f"[{timestamp}] {data['username']}: {data['message']}")

    def quit_conference(self):
        """退出会议"""
        if self.on_meeting:
            msg = create_message(MessageType.QUIT_CONFERENCE, {
                'conference_id': self.conference_id,
                'username': self.username
            })
            self.control_socket.send(msg)
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        self.on_meeting = False
        if self.video_cap:
            self.video_cap.release()
        if self.audio_handler:
            self.audio_handler.stop_recording()
        cv2.destroyAllWindows()

    def __del__(self):
        """析构函数"""
        self.cleanup()
        if self.control_socket:
            self.control_socket.close()
        if self.video_socket:
            self.video_socket.close()
        if self.audio_socket:
            self.audio_socket.close()
        if self.chat_socket:
            self.chat_socket.close()


def print_menu():
    """打印菜单"""
    print("\n=== 视频会议系统 ===")
    print("1. 连接服务器")
    print("2. 创建会议")
    print("3. 加入会议")
    print("4. 退出会议")
    print("5. 开关视频")
    print("6. 开关音频")
    print("0. 退出系统")
    print("================")


async def main():
    client = ConferenceClient()

    while True:
        print_menu()
        choice = input("请选择操作: ")

        if choice == "1":
            # 连接服务器
            username = input("请输入用户名: ")
            client.username = username
            if await client.connect_to_server():
                print("连接服务器成功！")
            else:
                print("连接服务器失败！")

        elif choice == "2":
            # 创建会议
            if not client.control_socket:
                print("请先连接服务器！")
                continue
            if client.create_conference():
                print(f"会议创建成功！会议ID: {client.conference_id}")
            else:
                print("创建会议失败！")

        elif choice == "3":
            # 加入会议
            if not client.control_socket:
                print("请先连接服务器！")
                continue
            conference_id = input("请输入会议ID: ")
            if client.join_conference(conference_id):
                print("加入会议成功！")
            else:
                print("加入会议失败！")

        elif choice == "4":
            # 退出会议
            if not client.on_meeting:
                print("当前不在会议中！")
                continue
            client.quit_conference()
            print("已退出会议")

        elif choice == "5":
            # 开关视频
            if not client.on_meeting:
                print("请先加入会议！")
                continue
            client.video_enabled = not client.video_enabled
            status = "开启" if client.video_enabled else "关闭"
            print(f"视频已{status}")

        elif choice == "6":
            # 开关音频
            if not client.on_meeting:
                print("请先加入会议！")
                continue
            client.audio_enabled = not client.audio_enabled
            status = "开启" if client.audio_enabled else "关闭"
            print(f"音频已{status}")

        elif choice == "0":
            # 退出系统
            print("正在退出系统...")
            client.cleanup()
            break

        else:
            print("无效的选择，请重试！")


if __name__ == "__main__":
    import asyncio

    try:
        # 对于 Python 3.7+
        asyncio.run(main())
    except AttributeError:
        # 对于 Python 3.6
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())

