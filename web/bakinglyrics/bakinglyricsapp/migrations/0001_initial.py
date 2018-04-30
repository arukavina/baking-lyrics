# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-03-21 18:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Bands',
            fields=[
                ('auto_increment_id', models.AutoField(primary_key=True, serialize=False)),
                ('bandName', models.CharField(max_length=200)),
                ('decade', models.IntegerField()),
                ('image', models.CharField(max_length=200)),
            ],
        ),
    ]
