# Generated by Django 5.1.3 on 2024-11-20 01:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wispar', '0003_remove_book_filepath_book_filefield'),
    ]

    operations = [
        migrations.AlterField(
            model_name='book',
            name='publication_date',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
