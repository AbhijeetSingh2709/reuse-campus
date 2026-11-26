web: python manage.py collectstatic --no-input && python manage.py migrate --noinput && gunicorn reusecampus.wsgi:application --bind 0.0.0.0:$PORT
