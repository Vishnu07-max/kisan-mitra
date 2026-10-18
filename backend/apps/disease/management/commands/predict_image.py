import json

from django.core.management.base import BaseCommand, CommandError

from apps.disease.inference import InvalidImage, ModelNotAvailable, predict


class Command(BaseCommand):
    help = "Run the Crop Doctor model on one image file and print the result."

    def add_arguments(self, parser):
        parser.add_argument("image", help="Path to a leaf photo (.jpg or .png)")

    def handle(self, *args, **options):
        try:
            result = predict(options["image"])
        except (ModelNotAvailable, InvalidImage) as exc:
            raise CommandError(str(exc))
        self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))