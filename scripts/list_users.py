#!/usr/bin/env python3
"""Listar usuários da coleção Firestore usando firebase/firebase_init.py

Execute com o Python do virtualenv:
"/home/sabrina/Área de trabalho/ValletWeb/AmbienteVirtual/bin/python" scripts/list_users.py
"""
from pathlib import Path
import sys

# Garantir que o diretório do projeto esteja no sys.path quando executado a partir de qualquer lugar
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import firebase.firebase_init as fi


def main():
    try:
        usuarios = fi.fetch_collection("usuario")
        if not usuarios:
            print("Nenhum documento encontrado na coleção 'usuario'.")
            return
        print(f"{len(usuarios)} documentos encontrados:")
        for u in usuarios:
            print(f"- ID: {u.get('_id')}, Dados: {u}")
    except Exception as e:
        print("Erro ao listar usuários:", type(e).__name__, e)


if __name__ == "__main__":
    main()
