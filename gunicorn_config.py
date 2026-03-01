import os

workers = 1
worker_class = 'sync'
threads = 4
timeout = 120
keepalive = 75
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"

accesslog = '-'
errorlog = '-'
loglevel = 'info'

raw_env = [
    'PYTHONUNBUFFERED=1',
]
