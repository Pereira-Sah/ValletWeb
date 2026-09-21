# ValletWeb - Versão web para gestores
<img align="right" src="https://github.com/user-attachments/assets/fee4e949-8803-41e0-b21e-f68f17017f75" alt="logo vallet" width="25%" />


<a href="https://git.io/typing-svg"><img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=24&pause=1000&color=4CAF50&width=600&height=55&lines=Sistema+de+Gest%C3%A3o+de+Estacionamentos" alt="Typing SVG" /></a>

<p>
Seja bem-vindo ao projeto <b>Vallet</b>, um aplicativo Android e plataforma web, seguindo a arquitetura MVVM (Model-View-ViewModel) e com integração total ao Firebase.
Ele busca otimizar o processo de <b>reserva, monitoramento e administração de vagas de estacionamento,</b> beneficiando tanto motoristas quanto os administradores de estacionamentos.
</p>

<p>Este repositório inclui as funções para gestor de estacionamento com dashboards e controle de vagas completo.<br> Caso queira acessar a versão para app android, acesse esse repositório: https://github.com/lariiscriis/ValletProjeto</p>

<p> Também possui o sistema de leitura de placas com uso de webcam, acesse esse repositório: https://github.com/Almile/ValletIOT</p>
<br><br>
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
git clone https://github.com/Pereira-Sah/ValletWeb
cd ValletWeb
```

### 2. Crie e Ative o Ambiente Virtual

É uma boa prática usar um ambiente virtual para isolar as dependências do projeto.


### Crie o ambiente virtual (venv)

```bash
python -m venv AmbienteVirtual
```

### Ative o ambiente

```bash
# No Windows (cmd.exe)
AmbienteVirtual\Scripts\activate
```

### 3. Instale as Dependências

Com o ambiente virtual ativo, instale todas as bibliotecas necessárias usando o arquivo `requirements.txt`.

```bash
pip install -r requirements.txt
```

### Faça as migrações
```bash
 python manage.py migrate  
```

### Rode o projeto
```bash
python manage.py runserver 8001
```

### Abra o projeto no localhost
```bash
http://127.0.0.1:8000/
```
