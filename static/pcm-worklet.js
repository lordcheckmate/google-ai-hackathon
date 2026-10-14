/**
 * PCM AudioWorklet Processor
 * Converts incoming Float32 audio samples to Int16 LINEAR16 at 16 kHz.
 * Emits ~100ms buffers (1600 samples) to main thread for binary WebSocket streaming.
 */
class PCMWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 1600; // 100 ms at 16,000 Hz
    this.buffer = new Int16Array(this.bufferSize);
    this.bytesWritten = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) {
      return true;
    }

    const channelData = input[0];
    for (let i = 0; i < channelData.length; i++) {
      // Clamp Float32 to [-1.0, 1.0] and convert to 16-bit PCM integer
      const s = Math.max(-1, Math.min(1, channelData[i]));
      this.buffer[this.bytesWritten++] = s < 0 ? s * 0x8000 : s * 0x7FFF;

      if (this.bytesWritten >= this.bufferSize) {
        // Send transferrable ArrayBuffer to main thread
        this.port.postMessage(this.buffer.buffer, [this.buffer.buffer]);
        this.buffer = new Int16Array(this.bufferSize);
        this.bytesWritten = 0;
      }
    }
    return true;
  }
}

registerProcessor('pcm-worklet', PCMWorkletProcessor);
