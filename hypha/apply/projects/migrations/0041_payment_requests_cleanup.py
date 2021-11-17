# Generated by Django 2.2.24 on 2021-10-27 10:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('application_projects', '0040_remove_deliverable_invoice_quantity'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='paymentreceipt',
            name='payment_request',
        ),
        migrations.RemoveField(
            model_name='paymentrequest',
            name='by',
        ),
        migrations.RemoveField(
            model_name='paymentrequest',
            name='project',
        ),
        migrations.DeleteModel(
            name='PaymentApproval',
        ),
        migrations.DeleteModel(
            name='PaymentReceipt',
        ),
        migrations.DeleteModel(
            name='PaymentRequest',
        ),
    ]