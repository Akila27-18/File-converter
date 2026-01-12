# PDFSAAS

Production-grade Django SaaS starter inspired by iLovePDF.

## Features
- User authentication
- PDF merge (working)
- Async-ready architecture
- Shareable links (model-ready)
- Tailwind-based SaaS UI (starter)

## Run
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
