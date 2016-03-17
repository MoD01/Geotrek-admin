# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import mapentity.models
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_insert', models.DateTimeField(auto_now_add=True, verbose_name='Insertion date', db_column=b'date_insert')),
                ('date_update', models.DateTimeField(auto_now=True, verbose_name='Update date', db_column=b'date_update')),
                ('name', models.CharField(max_length=256, verbose_name='Name')),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('comment', models.TextField(default=b'', verbose_name='Comment', blank=True)),
                ('geom', django.contrib.gis.db.models.fields.PointField(default=None, srid=2154, null=True, verbose_name='Location', blank=True)),
                ('context_object_id', models.PositiveIntegerField(null=True, editable=False, blank=True)),
            ],
            options={
                'ordering': ['-date_insert'],
                'db_table': 'f_t_signalement',
                'verbose_name': 'Report',
                'verbose_name_plural': 'Reports',
            },
            bases=(mapentity.models.MapEntityMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ReportCategory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('category', models.CharField(max_length=128, verbose_name='Category')),
                ('category_en', models.CharField(max_length=128, null=True, verbose_name='Category')),
                ('category_es', models.CharField(max_length=128, null=True, verbose_name='Category')),
                ('category_fr', models.CharField(max_length=128, null=True, verbose_name='Category')),
                ('category_it', models.CharField(max_length=128, null=True, verbose_name='Category')),
            ],
            options={
                'db_table': 'f_b_categorie',
                'verbose_name': 'Category',
                'verbose_name_plural': 'Categories',
            },
        ),
        migrations.CreateModel(
            name='ReportStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.CharField(max_length=128, verbose_name='Status')),
            ],
            options={
                'db_table': 'f_b_status',
                'verbose_name': 'Status',
                'verbose_name_plural': 'Status',
            },
        ),
        migrations.AddField(
            model_name='report',
            name='category',
            field=models.ForeignKey(default=None, blank=True, to='feedback.ReportCategory', null=True, verbose_name='Category'),
        ),
        migrations.AddField(
            model_name='report',
            name='context_content_type',
            field=models.ForeignKey(blank=True, editable=False, to='contenttypes.ContentType', null=True),
        ),
        migrations.AddField(
            model_name='report',
            name='status',
            field=models.ForeignKey(default=None, blank=True, to='feedback.ReportStatus', null=True, verbose_name='Status'),
        ),
    ]
