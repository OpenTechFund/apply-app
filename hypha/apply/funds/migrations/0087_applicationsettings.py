# Generated by Django 2.2.19 on 2021-03-17 10:31

from django.db import migrations, models
import django.db.models.deletion
import wagtail.core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('wagtailcore', '0059_apply_collection_ordering'),
        ('funds', '0086_applicationsubmission_summary'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApplicationSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('extra_text_round', wagtail.core.fields.RichTextField(blank=True)),
                ('extra_text_lab', wagtail.core.fields.RichTextField(blank=True)),
                ('site', models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, to='wagtailcore.Site')),
            ],
            options={
                'verbose_name': 'application settings',
            },
        ),
    ]