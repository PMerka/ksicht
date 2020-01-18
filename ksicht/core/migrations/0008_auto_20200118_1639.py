# Generated by Django 2.2.8 on 2020-01-18 16:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_tasksolutionsubmission_stickers'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='task',
            options={'ordering': ('series', 'id'), 'permissions': (('solution_export', 'Export odevzdaných úloh'),), 'verbose_name': 'Úloha', 'verbose_name_plural': 'Úlohy'},
        ),
        migrations.AlterUniqueTogether(
            name='task',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='task',
            name='nr',
        ),
    ]
