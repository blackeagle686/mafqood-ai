#!/bin/bash
export CELERY_ALWAYS_EAGER=True
# Standardize PYTHONPATH to include project root and app folder
# export PYTHONPATH=:/home/tlk/Documents/Projects/Mafqood/mafqood-ai/ai_system:/home/tlk/Documents/Projects/Mafqood/mafqood-ai/ai_system/app
export PYTHONPATH=$PYTHONPATH:$(pwd):$(pwd)/app
cd app
python3 manage.py runserver 0.0.0.0:8000
