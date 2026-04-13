from django.apps import AppConfig


class WorkerappConfig(AppConfig):
    name = 'workerapp'

    def ready(self):
        # This import is what actually activates the signals
        import workerapp.signals