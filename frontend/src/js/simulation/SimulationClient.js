export class SimulationClient {
  constructor(url, onMessage, onOpen, onClose, onError) {
    this.url = url;
    this.onMessage = onMessage;
    this.onOpen = onOpen;
    this.onClose = onClose;
    this.onError = onError;
    this.ws = null;
    this.isConnected = false;
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.isConnected = true;
      if (this.onOpen) this.onOpen();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (this.onMessage) this.onMessage(data);
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    };

    this.ws.onclose = (event) => {
      this.isConnected = false;
      if (this.onClose) this.onClose(event);
      setTimeout(() => this.connect(), 5000);
    };

    this.ws.onerror = (error) => {
      if (this.onError) this.onError(error);
    };
  }

  sendCommand(command, data = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ command, ...data }));
    }
  }
}
