from django.apps import AppConfig

class ArvaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'arva'

    def ready(self):
        import arva.signals