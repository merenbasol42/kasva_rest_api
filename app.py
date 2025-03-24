import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from cv_bridge import CvBridge, CvBridgeError
import numpy as np
import cv2
import base64
import time
import os
import logging
from typing import Dict, Any, Optional, Union, List
from threading import Thread, Event, Lock
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO
import threading


# --- Loglama Ayarları ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("robot_api")

# --- Global Variables ---
current_frame = None
frame_lock = Lock()
ros_initialized = Event()
ros_connected = Event()
clients_connected = 0

# --- Görüntü İşleme Ayarları ---
IMAGE_QUALITY = 70  # JPEG kalitesi (0-100)
IMAGE_WIDTH = 640   # Görüntü genişliği
IMAGE_HEIGHT = 480  # Görüntü yüksekliği
MAX_FPS = 30        # Maksimum FPS

# --- Varsayılan görüntü yükleme ---
def get_default_image() -> np.ndarray:
    """
    Varsayılan bir görüntü oluşturur ve döndürür
    
    Returns:
        np.ndarray: Varsayılan görüntü
    """
    # Belirtilen boyutta siyah bir görüntü oluştur
    img = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
    
    # Görüntüye "Kamera bağlantısı bekleniyor..." yazısı ekle
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = "Kamera bağlantısı bekleniyor..."
    textsize = cv2.getTextSize(text, font, 1, 2)[0]
    
    # Metni görüntünün ortasına yerleştir
    textX = (img.shape[1] - textsize[0]) // 2
    textY = (img.shape[0] + textsize[1]) // 2
    
    cv2.putText(img, text, (textX, textY), font, 1, (255, 255, 255), 2)
    
    return img

# Varsayılan görüntüyü ayarla
with frame_lock:
    current_frame = get_default_image()

# --- ROS2 Node: Web GUI ---
class WebNode(Node):
    def __init__(self):
        super().__init__("web_node")
        
        self.img: Optional[Image] = None
        self.img_flag = False
        self.last_image_time = time.time()
        self.image_timeout = 5.0  # 5 saniye içinde görüntü gelmezse timeout
        self.last_process_time = 0
        self.min_process_interval = 1.0 / MAX_FPS  # FPS sınırlaması için minimum işleme aralığı
        
        self.cv_bridge = CvBridge()
        
        # Twist mesajları için yayıncı oluşturuyoruz
        self.cmd_vel_pubber = self.create_publisher(Twist, 'cmd_vel', 10)
        
        # Kamera görüntülerini dinlemek için abonelik
        self.create_subscription(
            Image,
            "camera/image_raw",
            self.img_cb,
            10  # Daha yüksek QoS değeri
        )
        
        logger.info("ROS2 düğümü başlatıldı")
        ros_initialized.set()
        
        self.start()
    
    def start(self) -> None:
        """
        Arka planda sürekli görüntü işleme işlemi başlatır.
        """
        def func():
            while rclpy.ok():
                try:
                    # Görüntü işleme
                    if self.img_flag:
                        current_time = time.time()
                        # FPS sınırlaması kontrolü
                        if current_time - self.last_process_time >= self.min_process_interval:
                            self.process_image()
                            self.last_process_time = current_time
                    
                    # Görüntü timeout kontrolü
                    current_time = time.time()
                    if current_time - self.last_image_time > self.image_timeout:
                        # Timeout oldu, varsayılan görüntüyü göster
                        with frame_lock:
                            global current_frame
                            current_frame = get_default_image()
                        self.last_image_time = current_time
                    
                    # ROS2 spin_once çağrısı
                    rclpy.spin_once(self, timeout_sec=0.001)  # Daha hızlı spin
                    
                except Exception as e:
                    logger.error(f"ROS2 işleme hatası: {e}")
                    time.sleep(0.01)  # Hata durumunda kısa bir bekleme
            
            logger.info("ROS2 işleme döngüsü sonlandı")
        
        Thread(target=func, daemon=True).start()
        logger.info("ROS2 işleme thread'i başlatıldı")
    
    def img_cb(self, msg: Image) -> None:
        """
        ROS2 görüntü mesajı geldiğinde çağrılır.
        """
        self.img = msg
        self.img_flag = True
        self.last_image_time = time.time()
        ros_connected.set()  # ROS bağlantısı kuruldu
    
    def process_image(self) -> None:
        """
        ROS2 görüntü mesajını OpenCV görüntüsüne çevirir ve global değişkene atar.
        """
        try:
            # Numpy array olarak görüntüyü al
            frame = np.frombuffer(self.img.data, dtype=np.uint8).reshape(
                (self.img.height, self.img.width, -1)
            )
            
            # Renk uzayını BGR'ye dönüştür
            if frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Görüntüyü yeniden boyutlandır (gerekirse)
            if frame.shape[0] != IMAGE_HEIGHT or frame.shape[1] != IMAGE_WIDTH:
                frame = cv2.resize(frame, (IMAGE_WIDTH, IMAGE_HEIGHT), 
                                  interpolation=cv2.INTER_AREA)
            
            # Global değişkene at
            with frame_lock:
                global current_frame
                current_frame = frame
            
            self.img_flag = False  # İşlem tamamlandı
        except Exception as e:
            logger.error(f"Görüntü işleme hatası: {e}")
            self.img_flag = False  # Hata durumunda da flag'i sıfırla
    
    def pub_cmd_vel(self, linear_x: float, angular_z: float) -> None:
        """
        Gelen hız verilerini kullanarak Twist mesajı yayınlar.
        """
        twist = Twist()
        twist.linear.x = linear_x
        twist.angular.z = angular_z
        self.cmd_vel_pubber.publish(twist)

# --- Görüntü kodlama fonksiyonu ---
def encode_frame() -> str:
    """
    Mevcut kare görüntüsünü JPEG olarak kodlar ve base64 formatına dönüştürür
    
    Returns:
        str: Base64 kodlanmış görüntü
    """
    with frame_lock:
        frame = current_frame.copy()
    
    # JPEG olarak kodla (kalite parametresi ile)
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), IMAGE_QUALITY]
    _, buffer = cv2.imencode('.jpg', frame, encode_param)
    
    # Base64'e dönüştür
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    return img_base64

# --- Flask ve SocketIO uygulama oluşturma ---
def create_app(web_node: Optional[WebNode] = None) -> tuple:
    """
    Flask ve SocketIO uygulamasını oluşturur ve yapılandırır
    
    Args:
        web_node (Optional[WebNode]): ROS2 web düğümü
    
    Returns:
        tuple: (Flask uygulaması, SocketIO nesnesi)
    """
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    # Ana sayfa için statik dosya sunumu
    @app.route('/')
    def index():
        return app.send_static_file('index.html')
    
    # Durum bilgisi endpoint'i
    @app.route('/status')
    def status():
        return jsonify({
            "ros_initialized": ros_initialized.is_set(),
            "ros_connected": ros_connected.is_set(),
            "timestamp": time.time()
        })
    
    # SocketIO bağlantı olayları
    @socketio.on('connect')
    def handle_connect():
        global clients_connected
        clients_connected += 1
        logger.info(f"Yeni istemci bağlandı. Toplam: {clients_connected}")
        # Bağlantı durumunu gönder
        socketio.emit('status', {
            "ros_initialized": ros_initialized.is_set(),
            "ros_connected": ros_connected.is_set(),
            "timestamp": time.time()
        })
    
    @socketio.on('disconnect')
    def handle_disconnect():
        global clients_connected
        clients_connected -= 1
        logger.info(f"İstemci bağlantısı kesildi. Toplam: {clients_connected}")
    
    # Hız komutları için SocketIO olayı
    @socketio.on('cmd_vel')
    def handle_cmd_vel(data):
        if web_node and ros_initialized.is_set() and ros_connected.is_set():
            try:
                linear_x = float(data.get('linear_x', 0.0))
                angular_z = float(data.get('angular_z', 0.0))
                web_node.pub_cmd_vel(linear_x, angular_z)
                return {"status": "success"}
            except Exception as e:
                logger.error(f"Hız komutu gönderme hatası: {e}")
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "ROS bağlı değil"}
    
    return app, socketio

# --- Görüntü yayını için fonksiyon ---
def broadcast_frames(socketio):
    """
    Belirli aralıklarla görüntü karelerini tüm bağlı istemcilere yayınlar
    
    Args:
        socketio: SocketIO nesnesi
    """
    last_frame_time = 0
    min_interval = 1.0 / MAX_FPS  # FPS sınırlaması için minimum aralık
    
    while True:
        try:
            # İstemci bağlı değilse bekle
            if clients_connected <= 0:
                time.sleep(0.1)
                continue
            
            # FPS sınırlaması
            current_time = time.time()
            if current_time - last_frame_time < min_interval:
                # Çok kısa bir süre bekle
                time.sleep(0.001)
                continue
            
            # Görüntüyü kodla ve gönder
            img_base64 = encode_frame()
            socketio.emit('camera_frame', {
                'image': img_base64,
                'timestamp': int(current_time * 1000)
            })
            
            last_frame_time = current_time
            
        except Exception as e:
            logger.error(f"Görüntü yayını hatası: {e}")
            time.sleep(0.1)

# --- ROS2 düğümünü başlatma fonksiyonu ---
def run_ros_node() -> WebNode:
    """
    ROS2 düğümünü başlatır
    
    Returns:
        WebNode: Başlatılan ROS2 düğümü
    """
    try:
        rclpy.init()
        web_node = WebNode()
        logger.info("ROS2 düğümü başarıyla başlatıldı")
        return web_node
    except Exception as e:
        logger.error(f"ROS2 başlatma hatası: {e}")
        # ROS2 başlatılamazsa None döndür
        return None

if __name__ == '__main__':
    # ROS2 düğümünü başlat
    try:
        web_node = run_ros_node()
        logger.info("ROS2 düğümü başlatıldı")
        
        # Flask ve SocketIO uygulamasını oluştur
        app, socketio = create_app(web_node)
        
        # Görüntü yayını için thread başlat
        broadcast_thread = threading.Thread(
            target=broadcast_frames, 
            args=(socketio,),
            daemon=True
        )
        broadcast_thread.start()
        logger.info("Görüntü yayın thread'i başlatıldı")
        
        # SocketIO uygulamasını başlat
        logger.info("SocketIO uygulaması başlatılıyor...")
        socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"Uygulama başlatma hatası: {e}")
    finally:
        # Uygulama sonlandığında ROS2'yi kapat
        if rclpy.ok():
            rclpy.shutdown()
            logger.info("ROS2 kapatıldı")
