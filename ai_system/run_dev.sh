#!/bin/bash
export CELERY_ALWAYS_EAGER=True
export PYTHONPATH=:/home/tlk/Documents/Projects/Mafqood/mafqood-ai/ai_system:/home/tlk/Documents/Projects/Mafqood/mafqood-ai/ai_system/app
cd app
python3 manage.py runserver 0.0.0.0:8000
