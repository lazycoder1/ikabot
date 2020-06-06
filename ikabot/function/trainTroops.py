#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.varios import addDot
from ikabot.helpers.getJson import getCiudad
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.recursos import getRecursosDisponibles

t = gettext.translation('trainTroops',
                        localedir,
                        languages=idiomas,
                        fallback=True)
_ = t.gettext

def getCuartelInfo(s, ciudad):
	params = {'view': 'barracks', 'cityId': ciudad['id'], 'position': ciudad['pos'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'actionRequest': s.token(), 'ajax': '1'}
	data = s.post(params=params)
	return json.loads(data, strict=False)

def entrenar(s, ciudad, entrenamiento):
	payload = {'action': 'CityScreen', 'function': 'buildUnits', 'actionRequest': s.token(), 'cityId': ciudad['id'], 'position': ciudad['pos'], 'backgroundView': 'city', 'currentCityId': ciudad['id'], 'templateView': 'barracks', 'ajax': '1'}
	for tropa in entrenamiento:
		payload[ tropa['unit_type_id'] ] = tropa['entrenar']
	s.post(payloadPost=payload)

def esperarEntrenamiento(s, ciudad):
	data = getCuartelInfo(s, ciudad)
	html = data[1][1][1]
	segundos = re.search(r'\'buildProgress\', (\d+),', html)
	if segundos:
		segundos = segundos.group(1)
		segundos = int(segundos) - data[0][1]['time']
		wait(segundos + 5)

def planearEntrenamientos(s, ciudad, entrenamientos):
	while True:
		total = 0
		for entrenamiento in entrenamientos:
			for tropa in entrenamiento:
				total += tropa['cantidad']
		if total == 0:
			return

		for entrenamiento in entrenamientos:
			esperarEntrenamiento(s, ciudad)
			html = s.get(urlCiudad + ciudad['id'])
			city = getCiudad(html)
			ciudadanosDisp = city['ciudadanosDisp']
			recursos = city['recursos']
			maderaDisp  = recursos[0]
			vinoDisp    = recursos[1]
			marmolDisp  = recursos[2]
			cristalDisp = recursos[3]
			azufreDisp  = recursos[4]

			for tropa in entrenamiento:

				tropa['entrenar'] = tropa['cantidad']

				if 'wood' in tropa['costs']:
					limitante = maderaDisp // tropa['costs']['wood']
					if limitante < tropa['entrenar']:
						tropa['entrenar'] = limitante
				if 'wine' in tropa['costs']:
					limitante = vinoDisp // tropa['costs']['wine']
					if limitante < tropa['entrenar']:
						tropa['entrenar'] = limitante
				if 'marble' in ['costs']:
					limitante = marmolDisp // tropa['costs']['marble']
					if limitante < tropa['entrenar']:
						tropa['entrenar'] = limitante
				if 'cristal' in ['costs']:
					limitante = cristalDisp // tropa['costs']['cristal']
					if limitante < tropa['entrenar']:
						tropa['entrenar'] = limitante
				if 'sulfur' in tropa['costs']:
					limitante = azufreDisp // tropa['costs']['sulfur']
					if limitante < tropa['entrenar']:
						tropa['entrenar'] = limitante
				if 'citizens' in tropa['costs']:
					limitante = ciudadanosDisp // tropa['costs']['citizens']
					if limitante < tropa['entrenar']:
						tropa['entrenar'] = limitante

				if 'wood' in tropa['costs']:
					maderaDisp -= tropa['costs']['wood'] * tropa['entrenar']
				if 'wine' in tropa['costs']:
					vinoDisp -= tropa['costs']['wine'] * tropa['entrenar']
				if 'marble' in tropa['costs']:
					marmolDisp -= tropa['costs']['marble'] * tropa['entrenar']
				if 'cristal' in ['costs']:
					cristalDisp -= tropa['costs']['cristal'] * tropa['entrenar']
				if 'sulfur' in tropa['costs']:
					azufreDisp -= tropa['costs']['sulfur'] * tropa['entrenar']
				if 'citizens' in tropa['costs']:
					ciudadanosDisp -= tropa['costs']['citizens'] * tropa['entrenar']

				tropa['cantidad'] -= tropa['entrenar']

			total = 0
			for tropa in entrenamiento:
				total += tropa['entrenar']
			if total == 0:
				msg = _('It was not possible to finish training troops due to lack of resources.')
				sendToBot(s, msg)
				return
			entrenar(s, ciudad, entrenamiento)

def generateTroops(unidades_info):
	i = 1
	unidades = []
	while 'js_barracksSlider{:d}'.format(i) in unidades_info:
		# {"identifier":"phalanx","unit_type_id":303,"costs":{"citizens":1,"wood":27,"sulfur":30,"upkeep":3,"completiontime":71.169695412658},"local_name":"Hoplita"}
		info = unidades_info['js_barracksSlider{:d}'.format(i)]['slider']['control_data']
		info = json.loads(info, strict=False)
		unidades.append(info)
		i += 1
	return unidades

def trainTroops(s,e,fd):
	sys.stdin = os.fdopen(fd)
	try:
		banner()
		print(_('In what city do you want to train the troops?'))
		ciudad = chooseCity(s)
		banner()

		for i in range(len(ciudad['position'])):
			if ciudad['position'][i]['building'] == 'barracks':
				ciudad['pos'] = str(i)
				break
		else:
			print(_('Barracks not built.'))
			enter()
			e.set()
			return

		data = getCuartelInfo(s, ciudad)

		unidades_info = data[2][1]
		unidades = generateTroops(unidades_info)

		maxSize = 0
		for unidad in unidades:
			if maxSize < len(unidad['local_name']):
				maxSize = len(unidad['local_name'])

		entrenamientos = []
		while True:
			unidades = generateTroops(unidades_info)
			print(_('Train:'))
			for unidad in unidades:
				cantidad = read(msg='{}{}:'.format(' '*(maxSize-len(unidad['local_name'])), unidad['local_name']), min=0, empty=True)
				if cantidad == '':
					cantidad = 0
				unidad['cantidad'] = cantidad

			print(_('\nTotal cost:'))
			costo = {'madera': 0, 'vino': 0, 'marmol': 0, 'cristal': 0, 'azufre': 0, 'ciudadanos': 0, 'manuntencion': 0, 'tiempo': 0}
			for unidad in unidades:

				if 'wood' in unidad['costs']:
					costo['madera'] += unidad['costs']['wood'] * unidad['cantidad']
				if 'wine' in unidad['costs']:
					costo['vino'] += unidad['costs']['wine'] * unidad['cantidad']
				if 'marble' in unidad['costs']:
					costo['marmol'] += unidad['costs']['marble'] * unidad['cantidad']
				if 'cristal' in unidad['costs']:
					costo['cristal'] += unidad['costs']['cristal'] * unidad['cantidad']
				if 'sulfur' in unidad['costs']:
					costo['azufre'] += unidad['costs']['sulfur'] * unidad['cantidad']
				if 'citizens' in unidad['costs']:
					costo['ciudadanos'] += unidad['costs']['citizens'] * unidad['cantidad']
				if 'upkeep' in unidad['costs']:
					costo['manuntencion'] += unidad['costs']['upkeep'] * unidad['cantidad']
				if 'completiontime' in unidad['costs']:
					costo['tiempo'] += unidad['costs']['completiontime'] * unidad['cantidad']

			if costo['madera']:
				print(_('       Wood: {}').format(addDot(costo['madera'])))
			if costo['vino']:
				print(_('       Wine: {}').format(addDot(costo['vino'])))
			if costo['marmol']:
				print(_('     Marble: {}').format(addDot(costo['marmol'])))
			if costo['cristal']:
				print(_('    Cristal: {}').format(addDot(costo['cristal'])))
			if costo['azufre']:
				print(_('     Sulfur: {}').format(addDot(costo['azufre'])))
			if costo['ciudadanos']:
				print(_('   Citizens: {}').format(addDot(costo['ciudadanos'])))
			if costo['manuntencion']:
				print(_('Maintenance: {}').format(addDot(costo['manuntencion'])))
			if costo['tiempo']:
				print(_('   Duration: {}').format(daysHoursMinutes(int(costo['tiempo']))))

			print(_('\nProceed? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				e.set()
				return

			entrenamientos.append(unidades)

			print(_('\nDo you want to train more troops when you finish? [y/N]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'y':
				banner()
				continue
			else:
				break

		recursos   = ciudad['recursos']
		ciudadanos = ciudad['ciudadanosDisp']
		sobrante               = {}
		sobrante['madera']     = recursos[0]
		sobrante['vino']       = recursos[1]
		sobrante['marmol']     = recursos[2]
		sobrante['cristal']    = recursos[3]
		sobrante['azufre']     = recursos[4]
		sobrante['ciudadanos'] = ciudadanos

		for entrenamiento in entrenamientos:
			for unidad in entrenamiento:

				if 'wood' in unidad['costs']:
					sobrante['madera'] -= unidad['costs']['wood'] * unidad['cantidad']
				if 'wine' in unidad['costs']:
					sobrante['vino'] -= unidad['costs']['wine'] * unidad['cantidad']
				if 'marble' in unidad['costs']:
					sobrante['marmol'] -= unidad['costs']['marble'] * unidad['cantidad']
				if 'cristal' in unidad['costs']:
					sobrante['cristal'] -= unidad['costs']['cristal'] * unidad['cantidad']
				if 'sulfur' in unidad['costs']:
					sobrante['azufre'] -= unidad['costs']['sulfur'] * unidad['cantidad']
				if 'citizens' in unidad['costs']:
					sobrante['ciudadanos'] -= unidad['costs']['citizens'] * unidad['cantidad']

		falta = [ elem for elem in sobrante if sobrante[elem] < 0 ] != []

		if falta:
			print(_('\nThere are not enough resources:'))
			if sobrante['madera'] < 0:
				print(_('    Wood:{}').format(addDot(sobrante['madera']*-1)))
			if sobrante['vino'] < 0:
				print(_('    Wine:{}').format(addDot(sobrante['vino']*-1)))
			if sobrante['marmol'] < 0:
				print(_('  Marble:{}').format(addDot(sobrante['marmol']*-1)))
			if sobrante['cristal'] < 0:
				print(_(' Cristal:{}').format(addDot(sobrante['cristal']*-1)))
			if sobrante['azufre'] < 0:
				print(_('  Sulfur:{}').format(addDot(sobrante['azufre']*-1)))
			if sobrante['ciudadanos'] < 0:
				print(_('Citizens:{}').format(addDot(sobrante['ciudadanos']*-1)))

			print(_('\nProceed anyway? [Y/n]'))
			rta = read(values=['y', 'Y', 'n', 'N', ''])
			if rta.lower() == 'n':
				e.set()
				return

		print(_('\nThe selected troops will be trained.'))
		enter()
	except KeyboardInterrupt:
		e.set()
		return

	set_child_mode(s)
	e.set()

	info = _('\nI train troops in {}\n').format(ciudad['cityName'])
	setInfoSignal(s, info)
	try:
		planearEntrenamientos(s, ciudad, entrenamientos)
	except:
		msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
		sendToBot(s, msg)
	finally:
		s.logout()