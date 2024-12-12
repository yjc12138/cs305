import socket
import struct
import threading
import time
import traceback

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
        self.screen_port = None
        self.camera_port = None
        self.audio_port = None
        self.screen_socket = init_socket(CLIENT_PORT + 2)
        self.camera_socket = init_socket(CLIENT_PORT + 3)
        self.audio_socket = init_socket(CLIENT_PORT + 4)

        # TCP
        try:
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.bind((CLIENT_IP, CLIENT_PORT))
        except Exception as e:
            print("初始化control_socket错误")
            return

        try:
            word_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            word_socket.bind((CLIENT_IP, CLIENT_PORT + 1))
            self.word_socket = word_socket
        except Exception as e:
            print("初始化word_socket错误")
            return

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

        self.camera_flag = False
        self.audio_flag = False
        self.screen_flag = False

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
                self.conference_id = conference_id
                self.on_meeting = True
                try:
                    self.word_socket.connect((SERVER_IP, port))
                except Exception as e:
                    print("word_socket连接失败")
                    return
                self.screen_port = port + 1
                self.camera_port = port + 2
                self.audio_port = port + 3
                self.join()
                print("加入会议成功！")
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
                self.word_socket.close()
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
        while self.on_meeting and  self.camera_flag:  # 保证在会议进行时持续发送
            # 捕获摄像头图像
            try:
                _, frame = cap.read()
                frame = cv2.flip(frame, 1)
            except Exception as e:
                print(f"捕获摄像头图像失败: {e}")
                continue

            # 压缩图像
            _, send_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            local_ip, local_port = send_conn.getsockname()
            ip_address = local_ip.encode('utf-8')
            port_number = struct.pack('!H', local_port)  # 转换为两个字节的大端格式
            ip_length = struct.pack('!B', len(ip_address))
            identifier = b'c'
            send_data = identifier + ip_length + ip_address + port_number + send_data.tobytes()
            # 创建消息并发送
            try:
                send_conn.sendto(send_data, (SERVER_IP, self.camera_port))  # 发送数据
            except Exception as e:
                print(f"发送摄像头视频帧失败: {e}")
            time.sleep(interval)

    def keep_share_screen(self, send_conn, fps):
        interval = 1.0 / fps
        while self.on_meeting and self.screen_flag:
            try:
                frame = ImageGrab.grab()
                frame = frame.resize((960, 540))
                frame = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
            except Exception as e:
                print(f"捕获屏幕图像失败: {e}")
                continue

            _, send_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            local_ip, local_port = send_conn.getsockname()
            ip_address = local_ip.encode('utf-8')
            port_number = struct.pack('!H', local_port)  # 转换为两个字节的大端格式
            ip_length = struct.pack('!B', len(ip_address))
            identifier = b's'
            send_data = identifier + ip_length + ip_address + port_number + send_data.tobytes()
            try:
                send_conn.sendto(send_data, (SERVER_IP, self.camera_port))  # 发送数据
            except Exception as e:
                print(f"发送屏幕视频帧失败: {e}")
            time.sleep(interval)

    def keep_recv_image(self, recv_conn):
        dic = {}
        screen = None
        while self.on_meeting:  # 保证在会议进行时持续接收数据
            try:
                # 接收数据
                data, _ = recv_conn.recvfrom(65536)
                if not data:
                    print("no data recved")
                    break  # 如果没有数据，表示连接已关闭或出现问题
                identifier = data[0:1].decode('utf-8')
                ip_length = data[1]
                ip_address = data[2:2 + ip_length].decode('utf-8')
                port = struct.unpack('!H', data[2 + ip_length:4 + ip_length])[0]
                img_data = data[4 + ip_length:]
                data = np.frombuffer(img_data, dtype=np.uint8)
                # 处理视频帧
                img = cv2.imdecode(data, 1)
                # 将BGR转换为RGB（适用于PIL）
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                # 转换为PIL图像
                pil_image = Image.fromarray(img_rgb)

                if identifier == 'c':
                    dic.update({(ip_address, port): pil_image})
                elif identifier == 's':
                    local_ip, local_port = recv_conn.getsockname()
                    if ip_address == local_ip and port == local_port:
                        screen = None
                    else:
                        screen = pil_image

                if not (len(dic) == 0 and not screen):
                    if len(dic) != 0:
                        # print(1)
                        img = overlay_camera_images(screen, [value for value in dic.values()])
                    else:
                        # print(2)
                        img = overlay_camera_images(screen, None)

                    img = np.array(img)

                    # 确保图像维度正确
                    if img.ndim == 3:
                        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

                    cv2.imshow('c', img)
                    cv2.waitKey(1)

            except Exception as e:
                print(f"接收数据时发生错误: {e}")
                break

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
            while self.audio_flag:
                audio_data = stream1.read(CHUNK)
                audio_data = np.frombuffer(audio_data, dtype=np.int16)[None, :]
                try:
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

    def join(self):

        t1 = threading.Thread(target=self.keep_recv_audio, args=(self.audio_socket,))
        t1.daemon = True
        t1.start()

        t2 = threading.Thread(target=self.keep_recv_image, args=(self.camera_socket,))
        t2.daemon = True
        t2.start()

    def start(self):
        """
        execute functions based on the command line input
        """
        try:
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
                    self.camera_flag = True
                    t = threading.Thread(target=self.keep_share_camera, args=(self.camera_socket, 50))
                    t.daemon = True
                    t.start()
                elif fields[0] == 'camera' and fields[1] == 'disable':
                    self.camera_flag = False
                elif fields[0] == 'audio' and fields[1] == 'enable':
                    self.audio_flag = True
                    t = threading.Thread(target=self.keep_share_audio, args=(self.audio_socket,))
                    t.daemon = True
                    t.start()
                elif fields[0] == 'audio' and fields[1] == 'disable':
                    self.audio_flag = False
                elif fields[0] == 'screen' and fields[1] == 'enable':
                    self.screen_flag = True
                    t = threading.Thread(target=self.keep_share_screen, args=(self.camera_socket, 50))
                    t.daemon = True
                    t.start()
                elif fields[0] == 'screen' and fields[1] == 'disable':
                    self.screen_flag = False
                else:
                    recognized = False
            else:
                recognized = False

            if not recognized:
                print(f'[Warn]: Unrecognized cmd_input {cmd_input}')

if __name__ == '__main__':
    client1 = ConferenceClient()
    client1.start()