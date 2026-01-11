"""
ASGI config for vibebank_erp project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibebank_erp.settings')

application = get_asgi_application()
