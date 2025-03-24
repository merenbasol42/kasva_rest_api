# Kasva Robot Kontrol ve Görüntü Akış Sistemi

## Proje Genel Bakış
Bu proje, ROS2 ve Flask kullanılarak geliştirilmiş bir robot kontrol ve kamera görüntü akış uygulamasıdır. Gerçek zamanlı robot kontrolü ve kamera görüntüsü sağlama özellikleri içerir.

## Özellikler
- ROS2 entegrasyonu
- WebSocket üzerinden canlı kamera görüntüsü
- Robot hareket kontrolleri
- Esnek görüntü işleme
- Çoklu istemci desteği

## Teknolojiler
- Python
- ROS2
- Flask
- SocketIO
- OpenCV

## Gereksinimler
- Python 3.8+
- ROS2 (herhangi bir sürüm)
- Gerekli kütüphaneler: `requirements.txt` dosyasında listelenmiştir

## Kurulum

1. Depoyu klonlayın:
```bash
git clone https://github.com/kullanici_adi/kasva_robot_kontrol.git
cd kasva_robot_kontrol
```

2. Sanal ortam oluşturun:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Bağımlılıkları yükleyin:
```bash
pip install -r requirements.txt
```

## Çalıştırma
```bash
python3 app.py
```

Web arayüzü: `http://localhost:5000`

## Konfigürasyon Parametreleri
- Görüntü kalitesi
- Kamera çözünürlüğü
- Maksimum FPS

## Geliştirme
- Hata bildirimleri için GitHub Issues kullanılabilir
- Pull request'ler kabul edilmektedir

## Lisans
Proje lisans detayları için LICENSE dosyasını inceleyiniz.
