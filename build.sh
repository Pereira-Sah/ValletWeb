#!/usr/bin/env bash
# Sai imediatamente se um comando falhar
set -o errexit

# Instala as dependências
pip install -r requirements.txt

# Roda as migrações do banco de dados
python manage.py migrate

# Coleta os arquivos estáticos
python manage.py collectstatic --no-input