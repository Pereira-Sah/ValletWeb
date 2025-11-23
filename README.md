# ValletWeb 

## Pré-requisitos

Antes de começar, você vai precisar ter instalado em sua máquina:
- [Python 3+](https://www.python.org/downloads/)
- `pip` (geralmente já vem com o Python)
- Acesso a um projeto no Firebase.

---

## 🚀 Instalação e Configuração

Siga os passos abaixo para configurar o ambiente e rodar o projeto.

### 1. Clone o Repositório

```bash
git clone <url-do-seu-repositorio>
cd ValletWeb
```

### 2. Crie e Ative o Ambiente Virtual

É uma boa prática usar um ambiente virtual para isolar as dependências do projeto.

```bash
# Crie o ambiente virtual (venv)
python -m venv AmbienteVirtual

# Ative o ambiente
# No Windows (cmd.exe)
AmbienteVirtual\Scripts\activate
# No macOS/Linux
# source venv/bin/activate
```

### 3. Instale as Dependências

Com o ambiente virtual ativo, instale todas as bibliotecas necessárias usando o arquivo `requirements.txt`.

```bash
pip install -r requirements.txt
```

### Faça as migrações
```bash
 py manage.py migrate  
```

### Rode o projeto
```bash
py manage.py runserver    
```

### Abra o projeto no localhost
```bash
http://127.0.0.1:8000/
```
