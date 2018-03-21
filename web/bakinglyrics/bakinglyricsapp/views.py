# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import HttpResponse
import json

# Create your views here.
from .models import Bands


def index(request):
	if request.method == 'GET':
		bands = Bands.objects.all().order_by('bandName')
		context = {'bands':bands}
		return render(request, 'bakinglyricsapp/index.html',context)

@csrf_exempt
def sendParametersToServer(request):

	if request.method == 'POST':
		selected_band_id = request.POST['selected_band_id']
		selected_decade = request.POST['selected_decade']
		data = {}
		selectedband = Bands.objects.get(auto_increment_id = selected_band_id)
		data['selected_band'] = selectedband.bandName
		data['selected_decade'] = selected_decade
		data['band_image'] = selectedband.image
	return HttpResponse(json.dumps(data))

