# Generated by Django 4.2.11 on 2024-05-07 11:43

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        (
            "application_projects",
            "0083_rename_projectapprovalform_projectform_and_more",
        ),
        ("funds", "0118_labbaseprojectreportform_and_more"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="ApplicationBaseProjectApprovalForm",
            new_name="ApplicationBaseProjectForm",
        ),
        migrations.RenameModel(
            old_name="LabBaseProjectApprovalForm",
            new_name="LabBaseProjectForm",
        ),
    ]
