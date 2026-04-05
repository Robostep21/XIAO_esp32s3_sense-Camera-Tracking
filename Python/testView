import cv2
import numpy as np
import socket
import time

UDP_IP = "0.0.0.0"
UDP_PORT = 8889
BUFFER_SIZE = 65535


START_MARKER = bytes([0xAA, 0xBB, 0xCC, 0xDD])
END_MARKER = bytes([0xEE, 0xFF, 0x00, 0x11])

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((UDP_IP, UDP_PORT))
sock.settimeout(0.5)

print(f"Listening on {UDP_IP}:{UDP_PORT}")
print("Waiting for frames from ESP32...")
print("Press Ctrl+C to stop\n")

frame_count = 0
buffer = bytearray()

while True:
    try:
        data, addr = sock.recvfrom(BUFFER_SIZE)
        buffer.extend(data)
        
        start_pos = buffer.find(START_MARKER)
        
        if start_pos != -1:
            buffer = buffer[start_pos:]
            
            if len(buffer) >= 8:  
                frame_size = int.from_bytes(buffer[4:8], 'little')
                

                total_needed = 8 + frame_size + 4  
                
                if len(buffer) >= total_needed:
                    jpeg_data = buffer[8:8+frame_size]
                    
                    end_pos = buffer.find(END_MARKER, 8+frame_size)
                    
                    if end_pos == 8+frame_size:
                        frame = cv2.imdecode(np.frombuffer(jpeg_data, np.uint8), cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            frame_count += 1
                            print(f"Frame {frame_count}: {len(jpeg_data)} bytes, {frame.shape[1]}x{frame.shape[0]}")
                            
                            cv2.imshow('ESP32 Camera', frame)
                            
                            if cv2.waitKey(1) & 0xFF == ord('q'):
                                break
                        else:
                            print(f"Failed to decode frame {frame_count + 1}")
                        
                        buffer = buffer[total_needed:]
                    else:
                        print("END marker not found, clearing buffer")
                        buffer = bytearray()
                else:
                    pass
            else:
                pass
        elif len(buffer) > 1000:
            print(f"Buffer overflow, clearing ({len(buffer)} bytes)")
            buffer = bytearray()
            
    except socket.timeout:
        pass
    except Exception as e:
        print(f"Error: {e}")

cv2.destroyAllWindows()
sock.close()
print(f"\nTotal frames received: {frame_count}")
