from typing import Dict, Any
from flask import Flask, jsonify, request
from flask_restful import Api, Resource

class HelloWorld(Resource):
    def get(self) -> Dict[str, str]:
        """
        Basit bir GET endpoint'i
        
        Returns:
            Dict[str, str]: Karşılama mesajı
        """
        return {"message": "Merhaba, Dünya!"}

    def post(self) -> Dict[str, Any]:
        """
        Basit bir POST endpoint'i
        
        Returns:
            Dict[str, Any]: Gelen veriyi içeren yanıt
        """
        data = request.get_json()
        return {"received": data}, 201

class UserResource(Resource):
    def __init__(self) -> None:
        """
        Kullanıcı kaynaklarını yönetmek için başlatıcı
        """
        self.users: Dict[int, Dict[str, Any]] = {
            1: {"id": 1, "name": "Ahmet", "email": "ahmet@example.com"},
            2: {"id": 2, "name": "Mehmet", "email": "mehmet@example.com"}
        }

    def get(self, user_id: int) -> Dict[str, Any]:
        """
        Belirli bir kullanıcıyı ID'sine göre getirir
        
        Args:
            user_id (int): Kullanıcı ID'si
        
        Returns:
            Dict[str, Any]: Kullanıcı bilgileri
        """
        user = self.users.get(user_id)
        if user:
            return user
        return {"message": "Kullanıcı bulunamadı"}, 404

def create_app() -> Flask:
    """
    Flask uygulamasını oluşturur ve endpoint'leri ayarlar
    
    Returns:
        Flask: Yapılandırılmış Flask uygulaması
    """
    app = Flask(__name__)
    api = Api(app)
    
    # Endpoint'leri tanımla
    api.add_resource(HelloWorld, '/')
    api.add_resource(UserResource, '/users/<int:user_id>')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
