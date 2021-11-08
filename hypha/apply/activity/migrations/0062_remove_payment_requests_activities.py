# Generated by Django 2.2.24 on 2021-11-02 10:48

from django.db import migrations


def remove_payment_request_activities(apps, schema_editor):
    Activity = apps.get_model('activity', 'Activity')
    Activity.objects.filter(related_content_type__model='paymentrequest').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0061_payment_requests_cleanup'),
    ]

    operations = [
        migrations.RunPython(remove_payment_request_activities),
    ]
