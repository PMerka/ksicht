# Generated by Django 2.2.8 on 2020-01-23 09:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_auto_20200121_1715"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="sticker",
            options={"verbose_name": "Nálepka", "verbose_name_plural": "Nálepky"},
        ),
        migrations.RemoveField(model_name="sticker", name="uses",),
    ]
