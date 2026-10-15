from django.contrib import admin

from .models import CropRecord, Farm

admin.site.register(Farm)
admin.site.register(CropRecord)