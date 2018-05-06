# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.shortcuts import render
from django.http import HttpResponse
import json
import urllib.request


class Band(object):

    def __init__(self, band_id,name, decades=None):

        self.band_id = band_id
        self.name = name
        if decades is None:
            self.decades = {}
        else:
            self.decades = decades

    def dump(self):
        return {"BandList": {'band_id': self.band_id,
                             'name': self.name,
                             'decades': self.decades}
                }


def index(request):
    if request.method == 'GET':
        return render(request, 'bakinglyricsapp/index.html')


def get_all_bands(request):
    if request.method == 'POST':
        bands_list = []
        with urllib.request.urlopen('http://127.0.0.1:5002/baking_api/bands') as url:
            data = json.loads(url.read().decode())
        i = 1
        for element in data['bands']:
            bands_list.append(Band(i, element['band']['name'], element['band']['decades']))
            i = i + 1
        sorted_bands_list = sorted(bands_list, key=lambda x: x.name, reverse=False)
        try:
            data = json.dumps([o.dump() for o in sorted_bands_list])
        except ValueError:
            print("error")
        return HttpResponse(data, content_type='application/json')


def send_parameters_to_server(request):
    """
    This method receives the selected band and the selected decade for the trained model to return a new song.
    :param request: selected_band_id,selected_decade
    :return: text of the new song.
    """
    if request.method == 'POST':
        selected_band_id = request.POST['selected_band_id']
        selected_decade = request.POST['selected_decade']
        data = {}
        data['selected_decade'] = selected_decade
        return HttpResponse(json.dumps(data))

