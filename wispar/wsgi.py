"""
WSGI config for wispar project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
import sys
sys.path.append("alignment")
import forced_alignment_worker

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wispar.settings')

application = get_wsgi_application()

forced_alignment_worker.start_worker()