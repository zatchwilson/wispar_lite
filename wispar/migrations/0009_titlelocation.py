# Generated by Django 5.1.3 on 2025-01-23 15:29

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wispar', '0008_alter_book_filefield_alter_book_title'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TitleLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('audio_location', models.TimeField()),
                ('vtt_location', models.IntegerField()),
                ('text_location', models.CharField(max_length=255)),
                ('bookmark_type', models.CharField(choices=[('custom_bookmark', 'custom_bookmark'), ('last_read_position', 'last_read_position')], max_length=18)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'bookmarks',
            },
        ),
    ]
