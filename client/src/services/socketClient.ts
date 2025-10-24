type MessageHandler = (event: MessageEvent) => void;

class SocketClient {
  private socket?: WebSocket;
  private readonly url: string;

  constructor(url: string) {
    this.url = url;
  }

  connect(onMessage: MessageHandler) {
    this.socket = new WebSocket(this.url);
    this.socket.onmessage = onMessage;
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = undefined;
    }
  }
}

export default SocketClient;
