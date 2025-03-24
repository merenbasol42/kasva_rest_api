document.addEventListener('DOMContentLoaded', () => {
    // DOM Elementleri
    const loadingScreen = document.getElementById('loading-screen');
    const loadingStatus = document.getElementById('loading-status');
    const mainContent = document.getElementById('main-content');
    const errorScreen = document.getElementById('error-screen');
    const errorMessage = document.getElementById('error-message');
    const retryButton = document.getElementById('retry-button');
    const cameraFeed = document.getElementById('camera-feed');
    const connectionStatus = document.getElementById('connection-status');
    const linearXSpan = document.getElementById('linear-x');
    const angularZSpan = document.getElementById('angular-z');
    const systemStatus = document.getElementById('system-status');

    // Durum değişkenleri
    let isConnected = false;
    let socket = null;
    let connectionCheckInterval = null;
    let connectionRetries = 0;
    const MAX_RETRIES = 5;
    const RETRY_INTERVAL = 3000; // 3 saniye
    const CONNECTION_TIMEOUT = 15000; // 15 saniye

    // Joystick değişkeni
    let joystick = null;
    
    // Performans ölçüm değişkenleri
    let frameCount = 0;
    let lastFpsUpdateTime = 0;
    let currentFps = 0;

    // Uygulama başlatma
    initApp();

    // Yeniden deneme butonu olayı
    retryButton.addEventListener('click', () => {
        errorScreen.style.display = 'none';
        loadingScreen.style.display = 'flex';
        loadingStatus.textContent = 'Yeniden bağlanılıyor...';
        connectionRetries = 0;
        
        // Eğer socket varsa bağlantıyı kapat
        if (socket) {
            socket.disconnect();
            socket = null;
        }
        
        initApp();
    });

    // Uygulama başlatma fonksiyonu
    function initApp() {
        // Durum kontrolü başlat
        checkSystemStatus();
        
        // Bağlantı kontrolü için zamanlayıcı
        connectionCheckInterval = setTimeout(() => {
            if (!isConnected) {
                showError('Bağlantı zaman aşımına uğradı. Lütfen tekrar deneyin.');
            }
        }, CONNECTION_TIMEOUT);
    }

    // Sistem durumunu kontrol etme fonksiyonu
    function checkSystemStatus() {
        loadingStatus.textContent = 'Sistem durumu kontrol ediliyor...';
        
        fetch('/status')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Sunucu yanıt vermiyor');
                }
                return response.json();
            })
            .then(data => {
                if (data.ros_initialized) {
                    loadingStatus.textContent = 'ROS2 başlatıldı, bağlantı bekleniyor...';
                    
                    if (data.ros_connected) {
                        // ROS bağlantısı kuruldu, SocketIO bağlantısını başlat
                        loadingStatus.textContent = 'Bağlantı kuruldu, WebSocket başlatılıyor...';
                        initializeSocketIO();
                    } else {
                        // ROS başlatıldı ama henüz bağlantı yok, tekrar kontrol et
                        connectionRetries++;
                        if (connectionRetries < MAX_RETRIES) {
                            setTimeout(checkSystemStatus, RETRY_INTERVAL);
                        } else {
                            showError('ROS2 bağlantısı kurulamadı. Lütfen robot bağlantısını kontrol edin.');
                        }
                    }
                } else {
                    // ROS başlatılamadı, tekrar dene
                    connectionRetries++;
                    if (connectionRetries < MAX_RETRIES) {
                        loadingStatus.textContent = `ROS2 başlatılamadı, yeniden deneniyor (${connectionRetries}/${MAX_RETRIES})...`;
                        setTimeout(checkSystemStatus, RETRY_INTERVAL);
                    } else {
                        showError('ROS2 başlatılamadı. Lütfen sistem durumunu kontrol edin.');
                    }
                }
            })
            .catch(error => {
                console.error('Durum kontrolü hatası:', error);
                connectionRetries++;
                if (connectionRetries < MAX_RETRIES) {
                    loadingStatus.textContent = `Bağlantı hatası, yeniden deneniyor (${connectionRetries}/${MAX_RETRIES})...`;
                    setTimeout(checkSystemStatus, RETRY_INTERVAL);
                } else {
                    showError('Sunucuya bağlanılamadı. Lütfen uygulamanın çalıştığından emin olun.');
                }
            });
    }

    // SocketIO bağlantısını başlatma
    function initializeSocketIO() {
        // Socket.IO bağlantısı oluştur
        socket = io();
        
        // Bağlantı olayları
        socket.on('connect', () => {
            console.log('WebSocket bağlantısı kuruldu');
            loadingStatus.textContent = 'WebSocket bağlantısı kuruldu, uygulama başlatılıyor...';
            
            // Bağlantı kuruldu, uygulamayı başlat
            setTimeout(() => {
                isConnected = true;
                clearTimeout(connectionCheckInterval);
                initializeApp();
            }, 500);
        });
        
        socket.on('disconnect', () => {
            console.log('WebSocket bağlantısı kesildi');
            connectionStatus.textContent = 'Bağlantı Kesildi';
            connectionStatus.classList.add('status-error');
            connectionStatus.classList.remove('status-connected', 'status-connecting');
        });
        
        socket.on('connect_error', (error) => {
            console.error('WebSocket bağlantı hatası:', error);
            connectionRetries++;
            if (connectionRetries < MAX_RETRIES) {
                loadingStatus.textContent = `WebSocket bağlantı hatası, yeniden deneniyor (${connectionRetries}/${MAX_RETRIES})...`;
            } else {
                showError('WebSocket bağlantısı kurulamadı. Lütfen sunucuyu kontrol edin.');
            }
        });
        
        // Kamera görüntüsü olayı
        socket.on('camera_frame', (data) => {
            if (data.image) {
                cameraFeed.src = `data:image/jpeg;base64,${data.image}`;
                connectionStatus.textContent = `Bağlı (${currentFps} FPS)`;
                connectionStatus.classList.add('status-connected');
                connectionStatus.classList.remove('status-connecting', 'status-error');
                
                // FPS hesaplama
                frameCount++;
                const now = performance.now();
                if (now - lastFpsUpdateTime >= 1000) { // Her saniyede bir FPS güncelle
                    currentFps = Math.round(frameCount * 1000 / (now - lastFpsUpdateTime));
                    frameCount = 0;
                    lastFpsUpdateTime = now;
                }
            }
        });
        
        // Durum bilgisi olayı
        socket.on('status', (data) => {
            updateSystemStatusFromData(data);
        });
    }

    // Hata gösterme fonksiyonu
    function showError(message) {
        clearTimeout(connectionCheckInterval);
        loadingScreen.style.display = 'none';
        errorMessage.textContent = message;
        errorScreen.style.display = 'flex';
        console.error(message);
    }

    // Uygulama başlatma fonksiyonu
    function initializeApp() {
        // Yükleme ekranını gizle, ana içeriği göster
        loadingScreen.style.display = 'none';
        mainContent.style.display = 'flex';
        
        // Joystick oluşturma
        const joystickContainer = document.getElementById('joystick');
        joystick = nipplejs.create({
            zone: joystickContainer,
            mode: 'static',
            position: { left: '50%', top: '50%' },
            color: '#007bff',
            size: 150
        });
        
        // Joystick olayları
        setupJoystickEvents();
        
        // FPS sayacını başlat
        lastFpsUpdateTime = performance.now();
    }

    // Joystick olaylarını ayarlama
    function setupJoystickEvents() {
        // Joystick hareket olayları
        joystick.on('move', (evt, data) => {
            // Joystick verilerini hız komutlarına dönüştürme
            const linear_x = data.vector.y * 0.5;  // Dikey eksen linear hız
            const angular_z = -data.vector.x * 0.5;  // Yatay eksen açısal hız
            
            sendCmdVel(linear_x, angular_z);
        });
        
        // Joystick bırakıldığında hızları sıfırlama
        joystick.on('end', () => {
            sendCmdVel(0, 0);
        });
    }

    // Sistem durumunu veri ile güncelleme
    function updateSystemStatusFromData(data) {
        if (data.ros_connected) {
            systemStatus.textContent = 'Bağlı';
            systemStatus.className = 'status-connected';
        } else if (data.ros_initialized) {
            systemStatus.textContent = 'Başlatıldı, Bağlanıyor...';
            systemStatus.className = 'status-connecting';
        } else {
            systemStatus.textContent = 'Bağlantı Hatası';
            systemStatus.className = 'status-error';
        }
    }

    // Hız komutlarını gönderme fonksiyonu
    function sendCmdVel(linear_x, angular_z) {
        // Hız değerlerini her durumda göster
        linearXSpan.textContent = linear_x.toFixed(2);
        angularZSpan.textContent = angular_z.toFixed(2);
        
        // Socket.IO ile komut gönder
        if (socket && socket.connected) {
            socket.emit('cmd_vel', { linear_x, angular_z }, (response) => {
                if (response && response.status === 'success') {
                    // Başarılı komut gönderimi
                    connectionStatus.classList.add('status-connected');
                    connectionStatus.classList.remove('status-error', 'status-connecting');
                } else {
                    // Hata durumu
                    console.error('Hız komutu gönderilemedi:', response ? response.message : 'Bilinmeyen hata');
                }
            });
        } else {
            console.error('WebSocket bağlantısı yok, komut gönderilemedi');
            connectionStatus.textContent = 'Bağlantı Yok';
            connectionStatus.classList.add('status-error');
            connectionStatus.classList.remove('status-connected', 'status-connecting');
        }
    }
});
