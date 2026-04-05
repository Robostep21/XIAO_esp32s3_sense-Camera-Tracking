#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiClient.h>

// Change ssid, password and pcIP
const char* ssid = "********";
const char* password = "********";
const char* pcIP = "192.168.*.*";
const int tcpPort = 8889;

WiFiClient client;

// Camera pins for XIAO_esp32s3_sense
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39
#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

camera_fb_t *fb = nullptr;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  pinMode(4, OUTPUT);
  digitalWrite(4, HIGH);
  delay(100);
  
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  
  esp_camera_init(&config);
  Serial.println("Camera OK");
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.println(WiFi.localIP());
  
  while (!client.connect(pcIP, tcpPort)) {
    delay(1000);
    Serial.println("Connecting to PC...");
  }
  Serial.println("Connected to PC");
}

void loop() {
  if (!client.connected()) {
    client.connect(pcIP, tcpPort);
    delay(1000);
    return;
  }
  
  fb = esp_camera_fb_get();
  if (fb) {
    uint32_t size = fb->len;
    client.write((uint8_t*)&size, 4);
    client.write(fb->buf, fb->len);
    esp_camera_fb_return(fb);
    Serial.printf("Sent %d bytes\n", size);
  }
  delay(100);
}
