# Generated by Django 4.2.9 on 2024-01-10 08:24

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("people", "0016_remove_personindexpage_social_image_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="fundreviewers",
            name="page",
        ),
        migrations.RemoveField(
            model_name="fundreviewers",
            name="reviewer",
        ),
        migrations.RemoveField(
            model_name="personcontactinfomation",
            name="page",
        ),
        migrations.RemoveField(
            model_name="personindexpage",
            name="header_image",
        ),
        migrations.RemoveField(
            model_name="personindexpage",
            name="listing_image",
        ),
        migrations.RemoveField(
            model_name="personindexpage",
            name="page_ptr",
        ),
        migrations.RemoveField(
            model_name="personpage",
            name="header_image",
        ),
        migrations.RemoveField(
            model_name="personpage",
            name="listing_image",
        ),
        migrations.RemoveField(
            model_name="personpage",
            name="page_ptr",
        ),
        migrations.RemoveField(
            model_name="personpage",
            name="photo",
        ),
        migrations.RemoveField(
            model_name="personpagepersontype",
            name="page",
        ),
        migrations.RemoveField(
            model_name="personpagepersontype",
            name="person_type",
        ),
        migrations.RemoveField(
            model_name="socialmediaprofile",
            name="person_page",
        ),
        migrations.DeleteModel(
            name="Funding",
        ),
        migrations.DeleteModel(
            name="FundReviewers",
        ),
        migrations.DeleteModel(
            name="PersonContactInfomation",
        ),
        migrations.DeleteModel(
            name="PersonIndexPage",
        ),
        migrations.DeleteModel(
            name="PersonPage",
        ),
        migrations.DeleteModel(
            name="PersonPagePersonType",
        ),
        migrations.DeleteModel(
            name="PersonType",
        ),
        migrations.DeleteModel(
            name="SocialMediaProfile",
        ),
    ]