# Generated by Django 4.2.9 on 2024-01-11 11:37

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0014_remove_homepage_social_image_and_more"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="promotedlabs",
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name="promotedlabs",
            name="page",
        ),
        migrations.RemoveField(
            model_name="promotedlabs",
            name="source_page",
        ),
        migrations.AlterUniqueTogether(
            name="promotedrfps",
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name="promotedrfps",
            name="page",
        ),
        migrations.RemoveField(
            model_name="promotedrfps",
            name="source_page",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="funds_intro",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="funds_link",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="funds_link_text",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="funds_title",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="labs_intro",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="labs_link",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="labs_link_text",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="labs_title",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="listing_image",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="listing_summary",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="listing_title",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="news_link",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="news_link_text",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="our_work",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="our_work_link",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="our_work_link_text",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="our_work_title",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="rfps_intro",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="rfps_title",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="strapline_link",
        ),
        migrations.RemoveField(
            model_name="homepage",
            name="strapline_link_text",
        ),
        migrations.DeleteModel(
            name="PromotedFunds",
        ),
        migrations.DeleteModel(
            name="PromotedLabs",
        ),
        migrations.DeleteModel(
            name="PromotedRFPs",
        ),
    ]