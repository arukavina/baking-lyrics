# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models

class Bands(models.Model):
	auto_increment_id = models.AutoField(primary_key=True)
	bandName = models.CharField(max_length = 200)
	decade = models.IntegerField()
	image = models.CharField(max_length = 200)

	def __str__(self):
		return self.bandName
	
	
