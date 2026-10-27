import firebase_admin
from firebase_admin import credentials, auth, firestore, storage
from pathlib import Path

# caminho do arquivo de credenciais relativo a este arquivo
KEY_PATH = Path(__file__).resolve().parent / "serviceAccountKey.json"

print(f"[DEBUG] Tentando carregar credenciais em: {KEY_PATH}")

try:
	cred = credentials.Certificate(str(KEY_PATH))
	print("[SUCESSO] Credenciais carregadas com sucesso.")
except Exception as e:
	print(f"[FALHA] Erro ao carregar credenciais: {e}")
	raise

# --- CORREÇÃO: Garantir que o app seja inicializado apenas uma vez ---
try:
	# Tenta obter o app padrão, se já estiver inicializado
	firebase_app = firebase_admin.get_app()
	print("[INFO] App Firebase já existia, reaproveitando.")
except ValueError:
	# Se não estiver inicializado, inicializa
	try:
		firebase_app = firebase_admin.initialize_app(cred)
		print("[SUCESSO] Firebase inicializado com sucesso.")
	except Exception as e:
		print(f"[FALHA] Erro ao inicializar Firebase: {e}")
		raise
# --------------------------------------------------------------------

try:
	db = firestore.client()
	print("[SUCESSO] Conectado ao Firestore.")
except Exception as e:
	print(f"[FALHA] Não foi possível conectar ao Firestore: {e}")
	raise

# WEB API key usada pelo Firebase client/REST (opcional)
# Você pode preencher esta chave aqui ou exportar `FIREBASE_API_KEY` como variável de ambiente.
# Exemplo (obtida no Firebase Console, Project settings -> Your apps -> config):
WEB_API_KEY = "AIzaSyB0IRYXyYN5HDqxOgwT2aPju3TQKhg_9nM"

def fetch_collection(collection_name: str) -> list:
	print(f"[DEBUG] Buscando documentos da coleção: {collection_name}")
	try:
		cols = db.collection(collection_name).stream()
		print(f"[DEBUG] cols",cols)
		results = []
		for doc in cols:
			data = doc.to_dict() or {}
			print(f"[DEBUG] data",data)
			data["_id"] = doc.id
			results.append(data)
		print(f"[SUCESSO] {len(results)} documentos encontrados em '{collection_name}'.")
		return results
	except Exception as e:
		print(f"[FALHA] Erro ao buscar coleção '{collection_name}': {e}")
		raise


def fetch_document(collection_name: str, doc_id: str) -> dict | None:
	print(f"[DEBUG] Buscando doc '{doc_id}' em '{collection_name}'")
	try:
		doc_ref = db.collection(collection_name).document(doc_id)
		doc = doc_ref.get()
		if doc.exists:
			data = doc.to_dict() or {}
			data["_id"] = doc.id
			print("[SUCESSO] Documento encontrado.")
			return data
		print("[INFO] Documento não encontrado.")
		return None
	except Exception as e:
		print(f"[FALHA] Erro ao buscar documento '{doc_id}' em '{collection_name}': {e}")
		raise


def fetch_query(collection_name: str, field: str, op: str, value) -> list:
	print(f"[DEBUG] Executando query em '{collection_name}' onde {field} {op} {value}")
	try:
		q = db.collection(collection_name).where(field, op, value).stream()
		results = []
		for doc in q:
			data = doc.to_dict() or {}
			data["_id"] = doc.id
			results.append(data)
		print(f"[SUCESSO] Query retornou {len(results)} resultados.")
		return results
	except Exception as e:
		print(f"[FALHA] Erro na query:{e}")
		raise

# Exemplo de como usar a função e verificar o resultado
if __name__ == "__main__":
	print("\n--- Iniciando busca de teste ---")
	usuarios = fetch_collection("usuario")

	if usuarios:
		print("\n--- Resultado Final do Teste ---")
		print("Usuários encontrados:")
		for u in usuarios:
			print(f"  - ID: {u.get('_id')}, Dados: {u}")
	else:
		print("\n--- Resultado Final do Teste ---")
		print("Nenhum usuário foi encontrado na coleção 'usuario'. Verifique o console do Firebase.")
