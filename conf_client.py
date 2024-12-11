import socket
import traceback
import asyncio
import time
import multiprocessing

from util import *

cap=cv2.VideoCapture(0)


def init_socket(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((CLIENT_IP, port))
        return sock
    except Exception as e:
        print(f"连接时出错: {e}")
        return None


class ConferenceClient:
    def __init__(self, ):
        # sync client
        self.is_connected = False
        self.username = None
        self.conference_id = None
        # udp
        self.screen_socket = None
        self.camera_socket = None
        self.audio_socket = None
        self.screen_port = None
        self.camera_port = None
        self.audio_port = None
        # tcp
        self.control_socket = None
        self.word_socket = None

        self.is_working = True
        self.server_addr = None  # server addr
        self.on_meeting = False  # status
        self.conns = None  # you may need to maintain multiple conns for a single conference
        self.support_data_types = []  # for some types of data
        self.share_data = {}

        self.conference_info = None  # you may need to save and update some conference_info regularly

        self.recv_data = None  # you may need to save received streamd data from other clients in conference

        self.reader = None
        self.writer = None

    def create_conference(self):
        if not self.is_connected:
            print("请先连接服务器！")
            return False

        try:
            print("DEBUG: 准备创建会议...")
            msg = str('create').encode()
            self.control_socket.send(msg)
            print("DEBUG: 等待服务器响应...")
            response = self.control_socket.recv(BUFFER_SIZE).decode()
            print(f"DEBUG: 收到响应: {response}")
            conference_id, port = response.split()

            if conference_id:
                print(f"会议创建成功！会议ID: {conference_id}")
                self.conference_id = conference_id
                self.join_conference(conference_id)
                self.on_meeting = True
                return conference_id
            else:
                print(f"创建会议失败")
                return None

        except Exception as e:
            print(f"创建会议错误: {e}")
            print("DEBUG: 错误详情:")
            traceback.print_exc()
            self.is_connected = False
            return None

    def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data to
        """
        if not self.is_connected:
            print("请先连接服务器！")
            return False

        try:
            msg = str('join' + ' ' + conference_id).encode()
            self.control_socket.send(msg)

            response = self.control_socket.recv(BUFFER_SIZE).decode()
            print(response)
            port = int(response.split(':')[0])

            if port:
                print("加入会议成功！")
                self.conference_id = conference_id
                self.on_meeting = True
                word_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                word_socket.bind((CLIENT_IP, CLIENT_PORT + 1))
                word_socket.connect((SERVER_IP, port))
                self.word_socket = word_socket
                self.screen_socket = init_socket(CLIENT_PORT + 2)
                self.camera_socket = init_socket(CLIENT_PORT + 3)
                self.audio_socket = init_socket(CLIENT_PORT + 4)
                self.screen_port = port + 1
                self.camera_port = port + 2
                self.audio_port = port + 3
                self.join(port)
                return True
            else:
                print(f"加入会议失败 ")
                return False

        except Exception as e:
            print(f"加入会议错误: {e}")
            traceback.print_exc()
            return False

    def quit_conference(self):
        """
        quit your on-going conference
        """
        if not self.on_meeting:
            print("当前不在会议中！")
            return False

        try:
            print("DEBUG: 准备发送退出请求...")

            msg = str('quit' + ' ' + self.conference_id).encode()
            print(f"DEBUG: 发送消息: {msg}")

            self.control_socket.send(msg)
            print("DEBUG: 消息发送成功")

            print("DEBUG: 等待服务器响应...")
            try:
                response = self.control_socket.recv(BUFFER_SIZE).decode()
                print(f"DEBUG: 收到响应: {response}")
            except ConnectionAbortedError:
                print("DEBUG: 连接已断开")
                return False

            if response:
                print("已退出会议")
                self.on_meeting = False
                self.conference_id = None
                self.screen_socket = None
                self.camera_socket = None
                self.audio_socket = None
                self.word_socket = None
                return True
            else:
                print(f"退出会议失败")
                return False

        except Exception as e:
            print(f"退出会议错误: {e}")
            print("DEBUG: 错误详情:")
            traceback.print_exc()
            self.is_connected = False
            return False

    def cancel_conference(self):
        if not self.is_connected:
            print("无法连接到服务器！")
            return False

        try:
            # 保存会议ID，因为quit_conference会将其设为None
            conference_id = self.conference_id

            # 先退出会议
            if self.on_meeting:
                if not self.quit_conference():
                    print("退出会议失败，无法取消会议")
                    return False

            if not conference_id:
                print("没有可取消的会议")
                return False

            print("DEBUG: 准备发送取消请求...")
            # 发送取消会议请求
            msg = str('cancel' + ' ' + conference_id).encode()
            self.control_socket.send(msg)

            print("DEBUG: 等待服务器响应...")
            response = self.control_socket.recv(BUFFER_SIZE).decode()
            print(f"DEBUG: 收到响应: {response}")

            if response:
                print("已取消会议")
                self.on_meeting = False
                self.conference_id = None
                return True
            else:
                print(f"取消会议失败")
                return False

        except Exception as e:
            print(f"取消会议错误: {e}")
            print("DEBUG: 错误详情:")
            traceback.print_exc()
            self.is_connected = False
            return False

    def keep_share_camera(self, send_conn, fps):
        interval = 1.0 / fps
        while self.on_meeting:  # 保证在会议进行时持续发送
            # 捕获摄像头图像
            try:
                _, frame = cap.read()
                frame = cv2.flip(frame, 1)
            except Exception as e:
                print(f"捕获摄像头图像失败: {e}")
                continue

            # 压缩图像
            _, send_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])

            # 创建消息并发送
            try:
                send_conn.sendto(send_data, (SERVER_IP, self.camera_port))  # 发送数据
            except Exception as e:
                print(f"发送视频帧失败: {e}")
            time.sleep(interval)

    def keep_recv_camera(self, recv_conn):
        while self.on_meeting:  # 保证在会议进行时持续接收数据
            try:
                print("ready recv")
                # 接收数据
                data, _ = recv_conn.recvfrom(65536)
                if not data:
                    break  # 如果没有数据，表示连接已关闭或出现问题
                print("recv data")
                data = np.frombuffer(data, dtype=np.uint8)
                # 处理视频帧
                img = cv2.imdecode(data, 1)
                print("show img")
                # 显示或处理视频帧
                cv2.imshow('c', img)
                cv2.waitKey(1)

            except Exception as e:
                print(f"接收数据时发生错误: {e}")
                break
            time.sleep(0.02)

    def keep_share_screen(self, send_conn, capture_function, compress=None, fps_or_frequency=30):
        '''
        running task: keep sharing (capture and send) certain type of data from server or clients (P2P)
        you can create different functions for sharing various kinds of data
        '''
        pass

    def keep_share_audio(self, send_conn):
        try:
            p1 = pyaudio.PyAudio()  # 实例化对象
            stream1 = p1.open(format=FORMAT,
                              channels=CHANNELS,
                              rate=RATE,
                              input=True,
                              frames_per_buffer=CHUNK,
                              input_device_index=1,
                              )  # 打开流，传入响应参数
            while True:
                audio_data = stream1.read(CHUNK)
                audio_data = np.frombuffer(audio_data, dtype=np.int16)[None, :]
                try:
                    print((SERVER_IP, self.audio_port))
                    send_conn.sendto(audio_data, (SERVER_IP, self.audio_port))
                except Exception as e:
                    print(f"发送音频失败: {e}")
        except Exception as e:
            print(f"捕获音频失败: {e}")

    def keep_recv_audio(self, recv_conn):
        p = pyaudio.PyAudio()
        stream = p.open(channels=CHANNELS,
                        rate=RATE,
                        output=True,
                        format=FORMAT,
                        )
        while True:
            try:
                data, _ = recv_conn.recvfrom(BUFFER_SIZE)
                stream.write(data, num_frames=CHUNK)
            except Exception as e:
                print(f"接收数据时发生错误: {e}")
                break

    def keep_share_word(self, send_conn, capture_function, compress=None, fps_or_frequency=30):
        '''
        running task: keep sharing (capture and send) certain type of data from server or clients (P2P)
        you can create different functions for sharing various kinds of data
        '''
        pass

    def output_data(self, data, type):
        '''
        running task: output received stream data
        '''
        if type == 'camera':
            try:
                if data:
                    # 显示视频帧
                    frame = resize_image_to_fit_screen(data, my_screen_size)
                    cv2.imshow("Received Camera Feed", np.array(frame))  # 使用 OpenCV 显示视频
                    cv2.waitKey(1)  # 确保显示更新
            except Exception as e:
                print(f"显示摄像头视频时发生错误: {e}")

    def join(self, port):
        p1 = multiprocessing.Process(target=self.keep_share_audio, args=(self.audio_socket,))
        p1.daemon = True
        p1.start()

        p2 = multiprocessing.Process(target=self.keep_recv_audio, args=(self.audio_socket,))
        p2.daemon = True
        p2.start()

        p3 = multiprocessing.Process(target=self.keep_share_camera, args=(self.camera_socket, 50))
        p3.daemon = True
        p3.start()

        p4 = multiprocessing.Process(target=self.keep_recv_camera, args=(self.camera_socket,))
        p4.daemon = True
        p4.start()

        p1.join()
        p2.join()
        p3.join()
        p4.join()

    def start(self):
        """
        execute functions based on the command line input
        """
        try:
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.bind((CLIENT_IP, CLIENT_PORT))
            self.control_socket.connect((SERVER_IP, MAIN_SERVER_PORT))
            self.is_connected = True
        except Exception as e:
            print(f"初始连接失败: {e}")
            self.is_connected = False
            return

        while True:
            if not self.on_meeting:
                status = 'Free'
            else:
                status = f'OnMeeting-{self.conference_id}'

            recognized = True
            cmd_input = input(f'({status}) Please enter a operation (enter "?" to help): ').strip().lower()

            fields = cmd_input.split(maxsplit=1)
            if len(fields) == 1:
                if cmd_input in ('?', '？'):
                    print(HELP)
                elif cmd_input == 'create':
                    self.create_conference()
                    # await self.create_conference()
                elif cmd_input == 'quit':
                    self.quit_conference()
                elif cmd_input == 'cancel':
                    self.cancel_conference()
                else:
                    recognized = False
            elif len(fields) == 2:
                if fields[0] == 'join':
                    input_conf_id = fields[1]
                    self.join_conference(input_conf_id)
                elif fields[0] == 'camera' and fields[1] == 'enable':
                    self.keep_share_camera()
                else:
                    recognized = False
            else:
                recognized = False

            if not recognized:
                print(f'[Warn]: Unrecognized cmd_input {cmd_input}')

if __name__ == '__main__':
    client1 = ConferenceClient()
    client1.start()