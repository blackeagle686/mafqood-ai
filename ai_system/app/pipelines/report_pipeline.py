from infra.celery.tasks import process_image_task

class ReportPipeline:
    def execute(self, image_path: str, metadata: dict):
        # Application layer orchestration: could include logging, 
        # additional validation, or multiple task dispatches.
        process_image_task.delay(image_path, metadata)
