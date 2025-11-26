# firebase/firebase_singleton.py
import firebase_admin
from firebase_admin import credentials

_firebase_initialized = False

def initialize_firebase_once():
    global _firebase_initialized
    if not _firebase_initialized and not firebase_admin._apps:
        cred = credentials.Certificate('firebase/serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        print("✅ Firebase inicializado uma única vez")