release: python manage.py migrate --noinput && python manage.py clear_cache --cache=default && python manage.py sync_roles
web: python manage.py install_languages fr_en ar_en es_en --noinput && gunicorn hypha.wsgi:application --log-file -
worker: celery --app=hypha.celery worker --autoscale=6,2 --events
