import socket
import struct
import threading
import time
import traceback

from util import *

cap = cv2.VideoCapture(0)
if cap.isOpened():
    can_capture_camera = True
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)


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
        self.camera_socket = init_socket(CLIENT_PORT + 3)
        self.audio_socket = init_socket(CLIENT_PORT + 4)

        self.dic = {}
        self.screen = None
        self.screen_addr = None
        # TCP
        try:
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.bind((CLIENT_IP, CLIENT_PORT))
        except Exception as e:
            print("初始化control_socket错误")
            return
        self.word_socket = None
        self.screen_socket = None

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
            sign, message = response.split(":")
            conference_id, port = message.split(" ")
            if int(sign) == 200:
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

            sign, message = response.split(":")

            if int(sign) == 200:
                port = int(message.split(' ')[0])
                self.conference_id = conference_id
                self.on_meeting = True
                try:
                    word_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    word_socket.bind((CLIENT_IP, CLIENT_PORT + 1))
                    word_socket.connect((SERVER_IP, port))
                    self.word_socket = word_socket
                except Exception as e:
                    print(f"word_socket连接失败:{e}")
                    return
                try:
                    screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    screen_socket.bind((CLIENT_IP, CLIENT_PORT + 2))
                    screen_socket.connect((SERVER_IP, port + 1))
                    self.screen_socket = screen_socket
                except Exception as e:
                    print(f"screen_socket连接失败:{e}")
                    return
                self.camera_port = port + 2
                self.audio_port = port + 3
                self.join()
                print("加入会议成功！")
                return True
            else:
                print(f"加入会议失败:{message}")
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

            sign, message = response.split(":")
            if int(sign) == 200:
                print("已退出会议")
                self.on_meeting = False
                self.conference_id = None
                self.word_socket.close()
                self.screen_socket.close()
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

    def cancel_conference(self, conference=None):
        if not self.is_connected:
            print("无法连接到服务器！")
            return False

        try:
            # 保存会议ID，因为quit_conference会将其设为None
            if not conference:
                conference_id = self.conference_id
            else:
                conference_id = conference

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

            sign, message = response.split(":")
            if int(sign) == 200:
                print("已取消会议")
                self.on_meeting = False
                self.conference_id = None
                self.word_socket.close()
                return True
            else:
                print(f"取消会议失败:{message}")
                return False

        except Exception as e:
            print(f"取消会议错误: {e}")
            print("DEBUG: 错误详情:")
            traceback.print_exc()
            self.is_connected = False
            return False

    def keep_share_camera(self, send_conn, fps,stop_camera=False):
        interval = 1.0 / fps
        while self.on_meeting and self.camera_flag:  # 保证在会议进行时持续发送
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

    def stop_camera(self, send_conn):
        local_ip, local_port = send_conn.getsockname()
        ip_address = local_ip.encode('utf-8')
        port_number = struct.pack('!H', local_port)  # 转换为两个字节的大端格式
        ip_length = struct.pack('!B', len(ip_address))
        identifier = b'd'
        send_data = identifier + ip_length + ip_address + port_number
        try:
            send_conn.sendto(send_data, (SERVER_IP, self.camera_port))  # 发送数据
        except Exception as e:
            print(f"发送屏幕视频帧失败: {e}")

    def keep_share_screen(self, send_conn, fps, stop_screen=False):
        if stop_screen:
            stop_message = "stop"
            send_conn.sendall(stop_message.encode('utf-8'))
            print("已发送停止信号")
            return
        interval = 1.0 / fps
        while self.on_meeting and self.screen_flag:
            try:
                screen = ImageGrab.grab()
                screen = screen.resize((1920, 1080))
                frame = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
                #print(f'len of pic is {len(frame)}')
            except Exception as e:
                print(f"捕获屏幕图像失败: {e}")
                continue

            _, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            send_data = encoded.tobytes()
            data_length = len(send_data)
            try:
                send_conn.sendall(data_length.to_bytes(8, 'big'))
                send_conn.sendall(send_data)
            except Exception as e:
                print(f"发送屏幕视频帧失败: {e}")
            time.sleep(interval)

    def keep_recv_screen(self, recv_conn):
        try:
            while self.on_meeting:
                # 接收数据长度
                length_data = recv_conn.recv(8)
                if not length_data:
                    break
                try:
                    if length_data.decode('utf-8') == "stop":
                        print("已接收到停止信号")
                        self.screen = None
                        continue
                except:
                    pass
                data_length = int.from_bytes(length_data, 'big')
                data = b''
                while len(data) < data_length:
                    chunk = recv_conn.recv(min(data_length - len(data), 65500))
                    if not chunk:
                        print("接收图像数据时连接断开")
                        break
                    data += chunk
                # 解码并显示图像
                nparr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(nparr, 1)
                self.screen = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        except Exception as e:
            print(f"接收屏幕错误: {e}")
            print("错误详细信息:", traceback.format_exc())

    def keep_recv_image(self, recv_conn):
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
                if identifier == 'd':
                    print(2)
                    key = (ip_address, port)  # 要删除的键
                    if key in self.dic:  # 检查键是否存在，避免 KeyError
                        del self.dic[key]
                        print(1)
                    # 检查 dic 是否为空
                    if not self.dic and not self.screen:  # 如果 dic 为空
                        cv2.destroyWindow('c')  # 关闭窗口
                else:
                    img_data = data[4 + ip_length:]
                    data = np.frombuffer(img_data, dtype=np.uint8)
                    # 处理视频帧
                    img = cv2.imdecode(data, 1)
                    # 将BGR转换为RGB（适用于PIL）
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                    # 转换为PIL图像
                    pil_image = Image.fromarray(img_rgb)

                    if identifier == 'c':
                        self.dic.update({(ip_address, port): pil_image})
                    else:
                        print("camera identifier 无法识别")
            except Exception as e:
                print(f"接收数据时发生错误: {e}")
                break

    def output_image(self):
        while True:
            if len(self.dic) != 0 or self.screen:
                if len(self.dic) != 0:
                    img = overlay_camera_images(self.screen, [value for value in self.dic.values()])
                else:
                    img = overlay_camera_images(self.screen, None)

                img = np.array(img)

                if img.ndim == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

                cv2.imshow('c', img)
                cv2.waitKey(1)
            else:
                continue

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

    def join(self):
        t1 = threading.Thread(target=self.keep_recv_audio, args=(self.audio_socket,))
        t1.daemon = True
        t1.start()

        t2 = threading.Thread(target=self.keep_recv_image, args=(self.camera_socket,))
        t2.daemon = True
        t2.start()

        t4 = threading.Thread(target=self.keep_recv_screen, args=(self.screen_socket,))
        t4.daemon = True
        t4.start()

        t3 = threading.Thread(target=self.output_image, args=())
        t3.daemon = True
        t3.start()

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
                elif fields[0] == 'cancel':
                    input_conf_id = fields[1]
                    self.cancel_conference(input_conf_id)
                elif fields[0] == 'camera' and fields[1] == 'enable':
                    self.camera_flag = True
                    t = threading.Thread(target=self.keep_share_camera, args=(self.camera_socket, 50))
                    t.daemon = True
                    t.start()
                elif fields[0] == 'camera' and fields[1] == 'disable':
                    self.camera_flag = False
                    t = threading.Thread(target=self.keep_share_camera, args=(self.screen_socket, 50, True))
                    t.daemon = True
                    t.start()
                    self.stop_camera(self.camera_socket)
                elif fields[0] == 'audio' and fields[1] == 'enable':
                    self.audio_flag = True
                    t = threading.Thread(target=self.keep_share_audio, args=(self.audio_socket,))
                    t.daemon = True
                    t.start()
                elif fields[0] == 'audio' and fields[1] == 'disable':
                    self.audio_flag = False
                elif fields[0] == 'screen' and fields[1] == 'enable':
                    self.screen_flag = True
                    t = threading.Thread(target=self.keep_share_screen, args=(self.screen_socket, 50))
                    t.daemon = True
                    t.start()
                elif fields[0] == 'screen' and fields[1] == 'disable':
                    self.screen_flag = False
                    t = threading.Thread(target=self.keep_share_screen, args=(self.screen_socket, 50, True))
                    t.daemon = True
                    t.start()
                else:
                    recognized = False
            else:
                recognized = False

            if not recognized:
                print(f'[Warn]: Unrecognized cmd_input {cmd_input}')


if __name__ == '__main__':
    client1 = ConferenceClient()
    client1.start()
