import asyncio
from util import compress_image, decompress, decode_request, encode_response


class ConferenceServer:
    def __init__(self):
        self.conference_id = None
        self.conf_serve_ports = None
        self.data_serve_ports = {}
        self.data_types = ['screen', 'camera', 'audio']
        self.clients_info = None
        self.client_conns = None
        self.mode = 'Client-Server'

    async def handle_data(self, reader, writer, data_type):
        while True:
            try:
                data = await reader.read(1024)
                if not data:
                    break

                decompressed_data = decompress(data)
                print(f"Received {data_type} data")

                for conn_writer in self.client_conns:
                    if conn_writer is not writer:
                        conn_writer.write(compress_image(decompressed_data))
                        await conn_writer.drain()
            except Exception as e:
                print(f"Error in handle_data: {e}")
                break

    async def handle_client(self, reader, writer):
        try:
            request_data = await reader.read(1024)
            request = decode_request(request_data)
            print("Client request:", request)

            response = {"status": "ok"}
            writer.write(encode_response(response))
            await writer.drain()
        except Exception as e:
            print(f"Error in handle_client: {e}")

    async def log(self):
        while True:
            print('Logging server status...')
            await asyncio.sleep(5)

    async def cancel_conference(self):
        for conn_writer in self.client_conns:
            conn_writer.close()
        self.client_conns.clear()
        print("Conference canceled")

    def start(self):
        print(f"Starting ConferenceServer {self.conference_id}")


class MainServer:
    def __init__(self, server_ip, main_port):
        self.server_ip = server_ip
        self.server_port = main_port
        self.conference_servers = {}

    def handle_create_conference(self):
        print("Create conference")

    def handle_join_conference(self, conference_id):
        print(f"Join conference {conference_id}")

    async def request_handler(self, reader, writer):
        try:
            data = await reader.read(1024)
            request = decode_request(data)
            print("MainServer received:", request)

            response = {"status": "ok"}
            writer.write(encode_response(response))
            await writer.drain()
        except Exception as e:
            print(f"Error in request_handler: {e}")

    def start(self):
        print("MainServer started")


if __name__ == '__main__':
    server = MainServer("127.0.0.1", 8000)
    server.start()