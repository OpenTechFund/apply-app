# Generated by Django 4.2.7 on 2023-11-09 05:24

from django.db import migrations
import wagtail.images.models


class Migration(migrations.Migration):
    dependencies = [
        ("images", "0005_auto_20230214_0658"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rendition",
            name="file",
            field=wagtail.images.models.WagtailImageField(
                height_field="height",
                storage=wagtail.images.models.get_rendition_storage,
                upload_to=wagtail.images.models.get_rendition_upload_to,
                width_field="width",
            ),
        ),
    ]