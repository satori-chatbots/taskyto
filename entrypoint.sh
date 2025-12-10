#!/bin/bash
# Este script maneja los permisos y ejecuta la aplicación

# Asegurar que el directorio de la aplicación tiene los permisos correctos
sudo chown -R $(id -u):$(id -g) /home/ubuntu/chatbot-llm

# Ejecutar el orchestrator
exec /.venv/bin/python taskyto/server/cb_orchestrator.py --port 5000