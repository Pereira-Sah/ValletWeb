from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from firebase_admin import auth as fb_auth

User = get_user_model()

class FirebaseBackend(BaseBackend):
    def authenticate(self, request, token=None):
        if token is None:
            return None
        try:
            decoded = fb_auth.verify_id_token(token)
            uid = decoded['uid']
            email = decoded.get('email', '')
            user, _ = User.objects.get_or_create(username=uid, defaults={'email': email})
            return user
        except Exception:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None