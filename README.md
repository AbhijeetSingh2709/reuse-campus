# ReUse Campus 🌿

A peer-to-peer marketplace for college students to buy and rent resources.

## Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py migrate

# 4. Create superuser (for admin panel)
python manage.py createsuperuser

# 5. Run the development server
python manage.py runserver
```

Then visit: http://127.0.0.1:8000  
Admin panel: http://127.0.0.1:8000/admin/
