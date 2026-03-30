from django.apps import AppConfig


class EmployerappConfig(AppConfig):
    name = 'employerapp'

    def ready(self):
        import employerapp.signals
