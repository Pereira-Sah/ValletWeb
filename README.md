<div align="center">
   <img height="200" alt="VALLET_logo" src="https://github.com/user-attachments/assets/c016879c-235f-423f-b553-08cb60cf02e3" />
   
   <a href="https://git.io/typing-svg"><img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=26&pause=10000&color=3b5042&width=600&height=55&lines=Sistema+de+Gest%C3%A3o+de+Estacionamentos" alt="Typing SVG" /></a>
</div>


<p>
Seja bem-vindo ao projeto <b>Vallet</b>, uma aplicação quee busca otimizar o processo de <b>reserva, monitoramento e administração de vagas de estacionamento,</b> beneficiando tanto motoristas quanto os administradores de estacionamentos.<br>
Este repositório inclui as funções para gestor de estacionamento com dashboards e controle de vagas completo.
</p>


<h3>Verifique outras partes do nosso projeto</h3>

 | Módulo / Repositório | Descrição | Link de Acesso |
| :--- | :--- | :--- |
| **ValletWeb** (Gestores) | Dashboards e controle de ocupação para gestores de estacionamento. | [Repositório Web](https://github.com/Pereira-Sah/ValletWeb) |
| **ValletApp** (Android) | Aplicativo móvel voltado para motoristas e usuários finais. | [Repositório Android](https://github.com/lariiscriis/ValletProjeto) |
| **ValletAPI** | API backend para conexão e gerenciamento de todo o ecossistema. | [Repositório API](https://github.com/Almile/ValletAPI) |
| **ValletIOT** | Sistema de leitura de placas (LPR) com uso de webcam. | [Repositório IOT](https://github.com/Almile/ValletIOT) |
| **ValletDesktop** | Sistema desktop voltado para os administradores gerais. | [Repositório Desktop](https://github.com/Almile/valletDesktop) |

<br>
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
http://127.0.0.1:8001/
```
