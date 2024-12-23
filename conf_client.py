import socket
import struct
import threading
import time
import traceback
import tkinter as tk
from tkinter import scrolledtext
import cv2
from queue import Queue, Empty
from datetime import datetime

from util import *

cap = cv2.VideoCapture(0)
queue = Queue()
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
        return None


class ConferenceClient:
    def __init__(self, ):
        # sync client
        self.cnt = 0
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

        self.on_meeting = False  # status

        self.camera_flag = False
        self.audio_flag = False
        self.screen_flag = False

        self.word_conn = None
        self.screen_conn = None
        self.isServer = False
        self.server_ip = None

        self.root = None
        self.message_queue = Queue()
        self.chat_area = None
        self.running = True  # 添加运行状态标志
        self.camera_thread = None  # 添加线程引用

    def set_username(self, username):
        """设置用户名"""
        if not username or len(username.strip()) == 0:
            print("用户名不能为空")
            if self.log_area:
                self.log_area.insert(tk.END, "错误: 用户名不能为空\n")
                self.log_area.see(tk.END)
            return False

        self.username = username.strip()
        if self.log_area:
            self.log_area.insert(tk.END, f"已设置用户名: {self.username}\n")
            self.log_area.see(tk.END)
        return True

    def create_conference(self):
        if not self.username:
            print("请先设置用户名")
            if self.log_area:
                self.log_area.insert(tk.END, "请先使用 -u <用户名> 设置用户名\n")
                self.log_area.see(tk.END)
            return False

        if not self.is_connected:
            print("请先连接服务器！")
            return False

        self.screen = None
        self.dic.clear()
        try:
            msg = str('create').encode()
            self.control_socket.send(msg)
            response = self.control_socket.recv(BUFFER_SIZE).decode()
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
            self.is_connected = False
            return None

    def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data to
        """
        if not self.username:
            print("请先设置用户名")
            if self.log_area:
                self.log_area.insert(tk.END, "请先使用 -u <用户名> 设置用户名\n")
                self.log_area.see(tk.END)
            return False

        if not self.is_connected:
            print("请先连接服务器！")
            return False

        self.screen = None
        self.dic.clear()
        try:
            msg = str('join' + ' ' + conference_id).encode()
            self.control_socket.send(msg)

            response = self.control_socket.recv(BUFFER_SIZE).decode()
            print(response)

            sign, message = response.split(":")

            if int(sign) == 200:
                address = message.split(' ')[0]
                port = int(message.split(' ')[1])
                self.conference_id = conference_id
                self.on_meeting = True
                if port == 0:
                    print("加入会议成功！目前只有你一个人在会议中。")
                    t1 = threading.Thread(target=self.recv_info, args=(self.control_socket,))
                    t1.daemon = True
                    t1.start()
                    self.cnt += 1
                    if self.cnt == 1:
                        t2 = threading.Thread(target=self.output_image, args=())
                        t2.daemon = True
                        t2.start()
                    return True
                self.isServer = False
                self.word_conn = None
                self.screen_conn = None
                self.server_ip = address
                try:
                    if self.word_socket:
                        if not getattr(self.word_socket, '_closed'):
                            self.word_socket.close()
                    word_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    word_socket.bind((CLIENT_IP, CLIENT_PORT + 1))
                    word_socket.connect((self.server_ip, port))
                    self.word_socket = word_socket
                except Exception as e:
                    return
                try:
                    if self.screen_socket:
                        if not getattr(self.screen_socket, '_closed'):
                            self.screen_socket.close()
                    screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    screen_socket.bind((CLIENT_IP, CLIENT_PORT + 2))
                    screen_socket.connect((self.server_ip, port + 1))
                    screen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

                    screen_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)  # 初始60秒没有数据交换后开始探测
                    screen_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  # 探测间隔时间为10秒
                    screen_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)  # 探测次数为5次
                    self.screen_socket = screen_socket
                except Exception as e:
                    return
                self.camera_port = port + 2
                self.audio_port = port + 3
                self.join()
                t = threading.Thread(target=self.recv_info, args=(self.control_socket,))
                t.daemon = True
                t.start()
                print("连接成功！")
                return True
            else:
                print(f"连接失败:{message}")
                return False
        except Exception as e:
            print(f"加入会议错误: {e}")
            traceback.print_exc()
            return False

    def clear_chat_area(self):
        """清空聊天区域"""
        try:
            if self.chat_area:
                self.chat_area.delete('1.0', tk.END)
                self.chat_area.update_idletasks()
                # 可以添加一条提示消息
                # self.chat_area.insert(tk.END, "已退出会议，聊天记录已清空\n")
        except Exception as e:
            print(f"清空聊天区域失败: {e}")

    def quit_conference(self):
        try:
            try:
                self.audio_flag = False
                self.camera_flag = False
                for i in range(10):
                    self.stop_camera(self.camera_socket)
                    time.sleep(0.1)
                self.dic.clear()
                self.screen = None
                self.screen_flag = False
                if self.screen_socket:
                    self.keep_share_screen(self.screen_socket, 50, True)
            except Exception as e:
                pass

            msg = str('quit' + ' ' + self.conference_id).encode()

            self.control_socket.send(msg)

            try:
                response = self.control_socket.recv(BUFFER_SIZE).decode()
            except ConnectionAbortedError:
                return False

            sign, message = response.split(":")
            if int(sign) == 200:
                print("已退出会议")
                self.server_ip = None
                self.on_meeting = False
                self.conference_id = None
                self.screen = None
                self.dic = {}
                self.audio_flag = False
                if self.word_socket:
                    if not getattr(self.word_socket, '_closed'):
                        self.word_socket.close()
                if self.screen_socket:
                    if not getattr(self.screen_socket, '_closed'):
                        self.screen_socket.close()
                for _ in range(10):
                    queue.put("destroy")
                    time.sleep(0.01)
                if self.root and self.chat_area:
                    self.root.after(0, self.clear_chat_area)
                return True
            else:
                self.server_ip = None
                self.on_meeting = False
                self.conference_id = None
                self.screen = None
                self.dic = {}
                self.audio_flag = False
                if self.word_socket:
                    if not getattr(self.word_socket, '_closed'):
                        self.word_socket.close()
                if self.screen_socket:
                    if not getattr(self.screen_socket, '_closed'):
                        self.screen_socket.close()
                for _ in range(10):
                    queue.put("destroy")
                    time.sleep(0.01)
                return False
        except Exception as e:
            print(f"退出会议错误: {e}")
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

            msg = str('cancel' + ' ' + conference_id).encode()
            self.control_socket.send(msg)

            response = self.control_socket.recv(BUFFER_SIZE).decode()

            sign, message = response.split(":")
            if int(sign) == 200:
                print("已取消会议")
                self.on_meeting = False
                if self.root and self.chat_area:
                    self.root.after(0, self.clear_chat_area)
                return True
            else:
                print(f"取消会议失败:{message}")
                return False

        except Exception as e:
            print(f"取消会议错误: {e}")
            self.is_connected = False
            return False

    def keep_share_camera(self, send_conn, fps):
        interval = 1.0 / fps
        while self.on_meeting and self.camera_flag:
            try:
                _, frame = cap.read()
                frame = cv2.flip(frame, 1)
                # 自己更新自己的dic
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)
                local_ip, local_port = send_conn.getsockname()

                # 删除自己的摄像头
                key = (local_ip, local_port)
                self.dic.update({key: pil_image})
            except Exception as e:
                print(f"捕获摄像头图像失败: {e}")
                continue

            _, send_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            local_ip, local_port = send_conn.getsockname()
            ip_address = local_ip.encode('utf-8')
            port_number = struct.pack('!H', local_port)
            ip_length = struct.pack('!B', len(ip_address))
            identifier = b'c'
            send_data = identifier + ip_length + ip_address + port_number + send_data.tobytes()
            # 创建消息并发送
            try:
                if self.server_ip:
                    send_conn.sendto(send_data, (self.server_ip, self.camera_port))
            except Exception as e:
                pass
            time.sleep(interval)

    def stop_camera(self, send_conn):
        local_ip, local_port = send_conn.getsockname()

        #删除自己的摄像头
        key = (local_ip, local_port)
        if key in self.dic:
            del self.dic[key]
        # 检查 dic 是否为空
        if len(self.dic) == 0 and not self.screen:
            queue.put('destroy')

        ip_address = local_ip.encode('utf-8')
        port_number = struct.pack('!H', local_port)
        ip_length = struct.pack('!B', len(ip_address))
        identifier = b'd'
        send_data = identifier + ip_length + ip_address + port_number
        try:
            if self.camera_port and self.server_ip:
                send_conn.sendto(send_data, (self.server_ip, self.camera_port))
        except Exception as e:
            pass

    def keep_share_screen(self, send_conn, fps, stop_screen=False):
        if stop_screen:
            for i in range(10):
                stop_message = "stop"
                send_conn.sendall(stop_message.encode('utf-8'))
                time.sleep(0.1)
            return
        interval = 1.0 / fps
        while self.on_meeting and self.screen_flag and not getattr(send_conn, '_closed'):
            try:
                screen = ImageGrab.grab()
                screen = screen.resize((1920, 1080))
                frame = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
            except Exception as e:
                continue

            _, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            send_data = encoded.tobytes()
            data_length = len(send_data)
            try:
                send_conn.sendall(data_length.to_bytes(8, 'big'))
                send_conn.sendall(send_data)
            except Exception as e:
                pass
            time.sleep(interval)

    def keep_recv_screen(self, recv_conn):
        try:
            while self.on_meeting:
                # 接收数据长度
                length_data = recv_conn.recv(8)
                if not length_data:
                    break
                try:
                    if length_data.decode('utf-8')[:4] == "stop":
                        self.screen = None
                        if len(self.dic) == 0 and not self.screen:
                            queue.put('destroy')
                        continue
                except:
                    pass
                data_length = int.from_bytes(length_data, 'big')
                data = b''
                while len(data) < data_length:
                    chunk = recv_conn.recv(min(data_length - len(data), 65500))
                    if not chunk:
                        break
                    data += chunk
                # 解码并显示图像
                nparr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(nparr, 1)
                self.screen = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        except Exception as e:
            pass

    def keep_recv_image(self, recv_conn):
        while self.on_meeting:
            try:
                # 接收数据
                data, _ = recv_conn.recvfrom(65536)
                if not data:
                    print("no data recved")
                    break
                identifier = data[0:1].decode('utf-8')
                ip_length = data[1]
                ip_address = data[2:2 + ip_length].decode('utf-8')
                port = struct.unpack('!H', data[2 + ip_length:4 + ip_length])[0]
                if ip_address == self.server_ip or self.server_ip == SERVER_IP:
                    if identifier == 'd':
                        key = (ip_address, port)
                        if key in self.dic:
                            del self.dic[key]
                        # 检查 dic 是否为空
                        if len(self.dic) == 0 and not self.screen:
                            queue.put('destroy')
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
                break

    def output_image(self):
        while True:
            try:
                if not queue.empty():
                    task = queue.get()
                    if task == 'destroy':
                        try:
                            cv2.destroyWindow('image')
                            cv2.waitKey(1)
                            continue
                        except Exception as e:
                            continue

                if len(self.dic) != 0 or self.screen:
                    if len(self.dic) != 0:
                        img = overlay_camera_images(self.screen, [value for value in self.dic.values()])
                    else:
                        img = overlay_camera_images(self.screen, None)

                    img = np.array(img)

                    if img.ndim == 3:
                        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

                    if self.on_meeting:
                        cv2.imshow('image', img)
                        cv2.waitKey(1)

            except Exception as e:
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
                              )
            while self.audio_flag:
                audio_data = stream1.read(CHUNK)
                audio_data = np.frombuffer(audio_data, dtype=np.int16)[None, :]

                local_ip, local_port = send_conn.getsockname()
                ip_address = local_ip.encode('utf-8')
                port_number = struct.pack('!H', local_port)
                ip_length = struct.pack('!B', len(ip_address))
                identifier = b'c'
                audio_data = identifier + ip_length + ip_address + port_number + audio_data.tobytes()

                try:
                    if self.server_ip:
                        send_conn.sendto(audio_data, (self.server_ip, self.audio_port))
                except Exception as e:
                    pass
        except Exception as e:
            pass

    def mix_audio(self, audio_data_dict):
        max_length = max(len(data_list) for data_list in audio_data_dict.values())
        mixed_data = []
        for i in range(max_length):
            mixed_frame = np.zeros_like(audio_data_dict[list(audio_data_dict.keys())[0]][0])
            for ip, data_list in audio_data_dict.items():
                if i < len(data_list):
                    mixed_frame += data_list[i]
            mixed_data.append(mixed_frame)
        return mixed_data

    def keep_recv_audio(self, recv_conn):
        p = pyaudio.PyAudio()
        stream = p.open(channels=CHANNELS,
                        rate=RATE,
                        output=True,
                        format=FORMAT,
                        )
        audio_data_dict = {}
        start_time = time.time()
        while True:
            try:
                data, _ = recv_conn.recvfrom(BUFFER_SIZE)
                identifier = data[0:1].decode('utf-8')
                ip_length = data[1]
                ip_address = data[2:2 + ip_length].decode('utf-8')
                port = struct.unpack('!H', data[2 + ip_length:4 + ip_length])[0]
                audio_data = data[4 + ip_length:]
                if ip_address == self.server_ip or self.server_ip == SERVER_IP:
                    if ip_address not in audio_data_dict:
                        audio_data_dict[ip_address] = []

                    audio_data_dict[ip_address].append(np.frombuffer(audio_data, dtype=np.int16))
                    mixed_list = self.mix_audio(audio_data_dict)

                    current_time = time.time()
                    if current_time - start_time > 0.05:
                        for mixed_data in mixed_list:
                            stream.write(mixed_data.tobytes(), num_frames=CHUNK)
                        start_time = time.time()
                        audio_data_dict = {}
            except Exception as e:
                break

    def keep_share_word(self, send_conn, word):
        try:
            if self.on_meeting and send_conn:
                send_conn.sendall(word.encode('utf-8'))

                # 在日志区域显示调试信息
                if self.log_area:
                    self.log_area.see(tk.END)

                if self.root and self.chat_area:
                    # 方法1：直接在主线程更新
                    try:
                        self.chat_area.insert(tk.END, f"{word}\n")
                        self.chat_area.see(tk.END)
                        self.chat_area.update_idletasks()
                    except tk.TclError:
                        # 如果出现 TclError，说明可能在非主线程，使用 after 方法
                        self.root.after(1, lambda m=word: self.update_chat_area(m))
        except Exception as e:
            pass

    def keep_recv_word(self):
        while self.running:
            try:
                if not self.word_socket:
                    break

                message = self.word_socket.recv(1024).decode('utf-8')
                if message:
                    if self.root and self.chat_area:
                        try:
                            self.chat_area.insert(tk.END, f"{message}\n")
                            self.chat_area.see(tk.END)
                            self.chat_area.update_idletasks()
                        except tk.TclError:
                            self.root.after(1, lambda m=message: self.update_chat_area(m))
            except Exception as e:
                break

    def update_chat_area(self, message):
        try:
            self.chat_area.insert(tk.END, f"{message}\n")
            self.chat_area.see(tk.END)
            self.chat_area.update_idletasks()
        except Exception as e:
            print(f"更新聊天区域失败: {e}")

    def create_chat_window(self):
        if self.root is None:
            self.root = tk.Tk()
            self.root.title("会议客户端")
            self.root.geometry("1080x720")

            main_frame = tk.Frame(self.root)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            chat_frame = tk.Frame(main_frame)
            chat_frame.pack(fill=tk.BOTH, expand=True)

            chat_label = tk.Label(chat_frame, text="聊天室")
            chat_label.pack(anchor=tk.W)

            self.chat_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, width=70, height=15)
            self.chat_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            log_frame = tk.Frame(main_frame)
            log_frame.pack(fill=tk.BOTH, expand=True)

            log_label = tk.Label(log_frame, text="命令日志")
            log_label.pack(anchor=tk.W)

            self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=70, height=5)
            self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            cmd_frame = tk.Frame(main_frame)
            cmd_frame.pack(fill=tk.X, pady=5)

            self.status_label = tk.Label(cmd_frame, text="状态: Free")
            self.status_label.pack(side=tk.LEFT, padx=5)

            self.cmd_entry = tk.Entry(cmd_frame)
            self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            self.cmd_entry.bind('<Return>', self.handle_command)

            help_button = tk.Button(cmd_frame, text="帮助(?)", command=self.show_help)
            help_button.pack(side=tk.RIGHT, padx=5)

    def update_status(self):
        status = 'Free' if not self.on_meeting else f'OnMeeting-{self.conference_id}'
        self.status_label.config(text=f"状态: {status}")

    def show_help(self):
        self.log_area.insert(tk.END, HELP_TEXT + '\n')
        self.log_area.see(tk.END)

    def recv_info(self, recv_conn):
        isQuitted = False
        try:
            while True:
                data = recv_conn.recv(BUFFER_SIZE).decode()
                time.sleep(0.2)
                print(data)
                if data.startswith('Connect'):
                    address = data.split(' ')[1]
                    port = int(data.split(' ')[2])
                    self.isServer = False
                    self.word_conn = None
                    self.screen_conn = None
                    self.server_ip = address
                    try:
                        if self.word_socket:
                            if not getattr(self.word_socket, '_closed') :
                                self.word_socket.close()
                        word_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        word_socket.bind((CLIENT_IP, CLIENT_PORT + 1))
                        word_socket.connect((self.server_ip, port))
                        self.word_socket = word_socket
                    except Exception as e:
                        break
                    try:
                        if self.screen_socket:
                            if not getattr(self.screen_socket, '_closed'):
                                self.screen_socket.close()
                        screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        screen_socket.bind((CLIENT_IP, CLIENT_PORT + 2))
                        screen_socket.connect((self.server_ip, port + 1))
                        self.screen_socket = screen_socket
                    except Exception as e:
                        break
                    if self.screen_flag:
                        t = threading.Thread(target=self.keep_share_screen, args=(self.screen_socket, 50, False))
                        t.daemon = True
                        t.start()
                    self.camera_port = port + 2
                    self.audio_port = port + 3
                    self.join()
                    print(f'Successfully Connected with {self.server_ip}')
                    print("连接成功！")
                elif data.startswith('Cancelled'):
                    isQuitted = True
                    if self.word_socket:
                        if not getattr(self.word_socket, '_closed'):
                            self.word_socket.close()
                    if self.screen_socket:
                        if not getattr(self.screen_socket, '_closed'):
                            self.screen_socket.close()
                    self.on_meeting = False
                    self.update_status()
                    break
                elif data.startswith('Quitted'):
                    break
        except Exception as e:
            pass
        if isQuitted:
            self.quit_conference()
            self.dic.clear()
            self.screen = None

    def handle_command(self, event=None):
        cmd_input = self.cmd_entry.get().strip()
        self.cmd_entry.delete(0, tk.END)

        if not cmd_input:
            return

        self.log_area.insert(tk.END, f"> {cmd_input}\n")
        self.log_area.see(tk.END)

        if cmd_input.startswith('-u '):
            username = cmd_input[3:].strip()
            self.set_username(username)
            return

        if not self.username and not cmd_input in ('?', '？', 'exit'):
            self.log_area.insert(tk.END, "请先使用 -u <用户名> 设置用户名\n")
            self.log_area.see(tk.END)
            return

        if cmd_input.startswith('-c '):
            now=datetime.now()
            now=now.strftime("%H:%M:%S")
            message = f"{self.username}-{now}: {cmd_input[3:]}"
            if not message.strip():
                return

            if not self.on_meeting:
                self.log_area.insert(tk.END, "请先加入会议再发送消息\n")
                return

            if self.word_socket and not getattr(self.word_socket, '_closed'):
                self.keep_share_word(self.word_socket, message)
            else:
                if self.root and self.chat_area:
                    try:
                        self.chat_area.insert(tk.END, f"{message}\n")
                        self.chat_area.see(tk.END)
                        self.chat_area.update_idletasks()
                    except tk.TclError:
                        # 如果出现 TclError，说明可能在非主线程，使用 after 方法
                        self.root.after(1, lambda m=message: self.update_chat_area(m))
            return

        cmd_input = cmd_input.lower()

        fields = cmd_input.split(maxsplit=1)
        if len(fields) == 1:
            if cmd_input in ('?', '？'):
                self.show_help()
            elif cmd_input == 'create':
                self.create_conference()
            elif cmd_input == 'quit':
                self.quit_conference()
            elif cmd_input == 'cancel':
                self.cancel_conference()
        elif len(fields) == 2:
            if fields[0] == 'join':
                self.join_conference(fields[1])
            elif fields[0] == 'cancel':
                self.cancel_conference(fields[1])
            elif fields[0] == 'camera' and fields[1] == 'enable':
                if not self.camera_flag:
                    self.camera_flag = True
                    self.camera_thread = threading.Thread(
                        target=self.keep_share_camera,
                        args=(self.camera_socket, 50)
                    )
                    self.camera_thread.daemon = True
                    self.camera_thread.start()
                else:
                    self.chat_area.insert(tk.END, "摄像头已经在运行\n")
            elif fields[0] == 'camera' and fields[1] == 'disable':
                self.camera_flag = False
                for i in range(10):
                    self.stop_camera(self.camera_socket)
                    time.sleep(0.1)

            elif fields[0] == 'audio' and fields[1] == 'enable':
                self.audio_flag = True
                t = threading.Thread(target=self.keep_share_audio, args=(self.audio_socket,))
                t.daemon = True
                t.start()
            elif fields[0] == 'audio' and fields[1] == 'disable':
                self.audio_flag = False
            elif fields[0] == 'screen' and fields[1] == 'enable':
                if not self.screen:
                    self.screen_flag = True
                    if self.isServer:
                        t_conn = self.screen_conn
                    else:
                        t_conn = self.screen_socket
                    if t_conn:
                        t = threading.Thread(target=self.keep_share_screen, args=(t_conn, 50, False))
                        t.daemon = True
                        t.start()
                else:
                    print('Cannot share screen when other user sharing')
            elif fields[0] == 'screen' and fields[1] == 'disable':
                self.screen_flag = False
                if self.isServer:
                    t_conn = self.screen_conn
                else:
                    t_conn = self.screen_socket
                t = threading.Thread(target=self.keep_share_screen, args=(t_conn, 50, True))
                t.daemon = True
                t.start()
            else:
                recognized = False

        self.update_status()

    def on_closing(self):
        self.running = False
        if self.root:
            self.root.destroy()
            self.root = None

    def join(self):
        self.screen = None
        self.dic.clear()
        self.cnt += 1
        t1 = threading.Thread(target=self.keep_recv_audio, args=(self.audio_socket,))
        t1.daemon = True
        t1.start()

        t2 = threading.Thread(target=self.keep_recv_image, args=(self.camera_socket,))
        t2.daemon = True
        t2.start()

        if self.isServer:
            t3_conn = self.screen_conn
        else:
            t3_conn = self.screen_socket
        t3 = threading.Thread(target=self.keep_recv_screen, args=(t3_conn,))
        t3.daemon = True
        t3.start()

        t4 = threading.Thread(target=self.keep_recv_word)
        t4.daemon = True
        t4.start()

        self.create_chat_window()

        if self.cnt == 1:
            t5 = threading.Thread(target=self.output_image, args=())
            t5.daemon = True
            t5.start()

    def start(self):
        try:
            self.control_socket.connect((SERVER_IP, MAIN_SERVER_PORT))
            self.is_connected = True
        except Exception as e:
            print(f"初始连接失败: {e}")
            self.is_connected = False
            return

        self.create_chat_window()
        if self.root:
            try:
                self.root.mainloop()
            except Exception as e:
                print(f"GUI错误: {e}")
            finally:
                self.running = False

if __name__ == '__main__':
    client1 = ConferenceClient()
    try:
        client1.start()
    except KeyboardInterrupt:
        print("\n程序正在退出...")
    finally:
        client1.running = False
        if client1.root:
            client1.root.quit()