import os
import logging
LOGGINGLEVEL = os.environ.get('LOGGINGLEVEL', 'WARNING')
logging.basicConfig(level=LOGGINGLEVEL, format=' %(asctime)s - %(levelname)s - %(message)s')
logging.debug('Start of program')

from flask import Flask, url_for, request, jsonify, session
from worker import celery
import celery.states as states
from flask_cors import CORS
import psycopg2
import json
import math
import re
import requests
import locale
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import sys
from flask_babel import Babel, lazy_gettext as _l
from babel.numbers import format_number, format_decimal, format_percent, format_currency
from time import sleep

app = Flask(__name__)
CORS(app)

app.config["SECRET_KEY"] = os.environ.get('SECRET_KEY')
app.config["LANGUAGES"] = ["en", "fr"]
babel = Babel(app)

DB = os.environ.get('DB')
DB_SEISMIC = os.environ.get('DB_SEISMIC')

DB_USER = os.environ.get('DB_USER')
DB_HOST = os.environ.get('DB_HOST')
DB_PASSWORD = os.environ.get('DB_PASSWORD')

db_conn_str_flood = "dbname=%s user=%s password=%s host=%s" % (
    DB, DB_USER, DB_PASSWORD, DB_HOST)
db_conn_str_eq = "dbname=%s user=%s password=%s host=%s" % (
    DB_SEISMIC, DB_USER, DB_PASSWORD, DB_HOST)


WPS_EQ_URL = os.environ.get('WPS_EQ_URL')
EQ_MAP_SERVICE = os.environ.get('EQ_MAP_SERVICE')
EQ_LEGEND_BASE = "{EQ_MAP_SERVICE}&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic&FORMAT=image/png&sld_version=1.1.0&map=/map/er2/eq.map&layer=".format(
    EQ_MAP_SERVICE=EQ_MAP_SERVICE)
WPS_JOB_STATUS = os.environ.get("WPS_JOB_STATUS")


def get_legend_urls():
    getCapUrl = '{EQ_MAP_SERVICE}&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities'.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE)
    response = requests.get(getCapUrl)

    root = ET.fromstring(response.content)

    legendURLs = {}
    for layer in root.iter('{http://www.opengis.net/wms}Layer'):
        name = layer.find('{http://www.opengis.net/wms}Name').text
        if name != 'eq':
            for legend in layer.iter('{http://www.opengis.net/wms}LegendURL'):
                for legendOnlineResource in legend.iter('{http://www.opengis.net/wms}OnlineResource'):
                    legendURLs[name] = legendOnlineResource.attrib['{http://www.w3.org/1999/xlink}href']
    return legendURLs

try:
    legendURLs = get_legend_urls()
except Exception as e:
    logging.warning("Legends failed to be obtained from getCapabilities request.")
    logging.warning(e)
    legendURLs = {
        'fatal_2am': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=fatal_2am&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'fatal_2pm': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=fatal_2pm&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'fatal_5pm': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=fatal_5pm&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'injuries_2am': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=injuries_2am&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'injuries_2pm': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=injuries_2pm&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'injuries_5pm': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=injuries_5pm&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'economic_loss': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=economic_loss&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'pga': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=pga&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'sa1': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=sa1&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'sa03': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=sa03&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'soil': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=soil&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'historical_earthquakes': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=historical_earthquakes&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'hz_tract': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=hz_tract&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE),
        'secan_r2': '{EQ_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=secan_r2&format=image/png&STYLE='.format(EQ_MAP_SERVICE=EQ_MAP_SERVICE)
    }

@babel.localeselector
def get_locale():
    try:
        return session["language"]
    except KeyError:
        session["language"] = request.accept_languages.best_match(app.config["LANGUAGES"])
        return session["language"]


@app.before_request
def do_something_whenever_a_request_comes_in():
    session["language"] = request.args.get("lang", default="en")


@app.route("/eq/initiate", methods=["POST"])
def initiate_earthquake():

    postedData = request.form.to_dict()

    yCoord = str(postedData["x"])
    xCoord = str(postedData["y"])
    depth = str(postedData["d"])
    magnitude = str(postedData["m"])
    return_period = str(postedData["r"])
    srsName = str(postedData["srsName"])

    substitutions = {
        'xCoord': xCoord,
        'yCoord': yCoord,
        'depth': depth,
        'magnitude': magnitude,
        'return_period': return_period,
        'srsName': srsName
    }

    xmlstring = open("eq_initiate_sim.xml", 'r').read()

    pattern = re.compile(r'%([^%]+)%')
    xmlstring_replaced_values = re.sub(
        pattern, lambda m: substitutions[m.group(1)], xmlstring)

    # set what your server accepts
    head = {'Content-Type': 'application/xml'}
    xml_submit_returned = requests.post(
        WPS_EQ_URL, data=xmlstring_replaced_values, headers=head).text

    soup = BeautifulSoup(xml_submit_returned, 'xml')

    progress_url = soup.find_all(('wps:Data'))[0].get_text()

    task_id = re.search(r'fetch_(.*?)_evarisk.report', progress_url).group(1)

    actions = [
        {
            "action": "add",
            "geometry": {
                "coordinates": [postedData["x"],postedData["y"]],
                "type": "Point"
            },
            "srs": "4326",
            "type": "marker"
        }
    ]

    response = {
        "actions": actions,
        "taskid": task_id,
        "task_status_url": url_for('eq_task_status', task_id=task_id, external=True),
        "progress": "0",
        "status": "not-started",
        "type": "epicenter-task-status"
    }
    return jsonify(response)


@app.route("/tiffValue")
def getTiffValue():
    # example: /tiffValue?x=-75.67502975&y=45.46843792
    x = float(request.args.get("x"))
    y = float(request.args.get("y"))
    task = celery.send_task('tasks.get_hand_value', args=[x, y], kwargs={})
    app.logger.info("Sent worker to fetch HAND value.")
    response = url_for('check_task', task_id=task.id, external=True)
    return response


@app.route('/tiffValue_status/<string:task_id>')
def check_task(task_id: str) -> str:
    app.logger.info("HAND value requested.")
    res = celery.AsyncResult(task_id)
    if res.state == states.PENDING:
        return res.state
    else:
        return str(res.result)


@app.route("/initiate", methods=["POST"])
def initiate():
    postedData = request.form.to_dict()
    waterLevel = float(postedData["waterLevel"])
    x = float(postedData["x"])
    y = float(postedData["y"])
    app.logger.info(f"Client request to initiate simulation at x={x}, y={y}, and waterLevel={waterLevel}.")
    app.logger.info("Sending Celery task.")
    task = celery.send_task('tasks.calculate_damages', args=[x, y, waterLevel])
    response = {
        "type": "flood-task-status",
        "taskid": task.id,
        "task_status_url": url_for('task_status', task_id=task.id, external=True),
        "progress": "0",
        "status": "not-started",
    }
    return jsonify(response)


@app.route("/eq/status/<task_id>", methods=["GET"])
def eq_task_status(task_id):
    job_status_url = WPS_JOB_STATUS.replace("JOB", task_id)

    # Sometimes there is a lag when the simulation starts
    num_retries = 4 # Retry a few times
    sleep_time = 0.25 # Wait before retrying

    for x in range(0, num_retries):
        # Try to get the status from the XML
        try:
            progress_xml = requests.get(job_status_url).text
            soup = BeautifulSoup(progress_xml, 'xml')
            progress = soup.find_all(('gin:status'))[0]["percent-completed"]
            status = soup.find_all(('gin:status'))[0]["status"]
            key_error = None
        except KeyError as key_error:
            pass
        if key_error:
            app.logger.warning(f"XML status request failed! Trying again in {sleep_time} seconds...")
            sleep(sleep_time) # wait before trying to fetch the data again
            sleep_time *=2  # Implement your backoff algorithm here i.e. exponential backoff
        else:
            app.logger.info("XML status request succeeded.")
            break

    query_info_url = os.environ.get("ER2_API")+"/seismic/query?id=" + task_id

    actions = [
        {
            "type": "load-layer",
            "source": [
                {
                    "legend_name": _l("Economic Loss"),
                    "id": task_id + "_economic_loss",
                    "name": "economic_loss",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["economic_loss"]
                },
                {
                    "legend_name": _l("Fatal 2 AM"),
                    "id": task_id + "_fatal_2am",
                    "name": "fatal_2am",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["fatal_2am"]
                },
                {
                    "legend_name": _l("Fatal 2 PM"),
                    "id": task_id + "_fatal_2pm",
                    "name": "fatal_2pm",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["fatal_2pm"]
                },
                {
                    "legend_name": _l("Fatal 5 PM"),
                    "id": task_id + "_fatal_5pm",
                    "name": "fatal_5pm",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["fatal_5pm"]
                },
                {
                    "legend_name": _l("Injuries 2 AM"),
                    "id": task_id + "_injuries_2am",
                    "name": "injuries_2am",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["injuries_2am"]
                },
                {
                    "legend_name": _l("Injuries 2 PM"),
                    "id": task_id + "_injuries_2pm",
                    "name": "injuries_2pm",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["injuries_2pm"]
                },
                {
                    "legend_name": _l("Injuries 5 PM"),
                    "id": task_id + "_injuries_5pm",
                    "name": "injuries_5pm",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["injuries_5pm"]
                },
                {
                    "legend_name": _l("PGA"),
                    "id": task_id + "_pga",
                    "name": "pga",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["pga"]
                },
                {
                    "legend_name": _l("Sa @ 0.3 s"),
                    "id": task_id + "_sa03",
                    "name": "sa03",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["sa03"],
                },
                {
                    "legend_name": _l("Sa @ 1.0 s"),
                    "id": task_id + "_sa1",
                    "name": "sa1",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["sa1"],
                },
                {
                    "legend_name": _l("Soil type"),
                    "id": task_id + "_soil",
                    "name": "soil",
                    "simId": task_id,
                    "serverType": "mapserver",
                    "service": EQ_MAP_SERVICE,
                    "styles": "",
                    "type": "wms-layer",
                    "query_info_url": query_info_url,
                    "legend_url": legendURLs["soil"],
                },
            ],
        }
    ]


    if progress == '100':
        # Try to parse XML for the link to HTML report
        try:
            html_report = soup.find_all(('gin:result'))[0].get_text()
        # If XML doesn't yet contain the link, the URL format is the same as the status URL, except with .html
        except:
            html_report = job_status_url.replace(".report", ".html")
        app.logger.info(f"Simulation complete. HTML report available at: {html_report}")
        html_report = {
            "id": task_id,
            'link': html_report,
            'name': "Statistics",
            "type": "load-page"
        }
        actions.append(html_report)

    response = {
        "actions": actions,
        "progress": progress,
        "status": status,
        "task_status_url": request.endpoint,
        "taskid": task_id
    }

    return jsonify(response)


@app.route("/status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = celery.AsyncResult(task_id)
    app.logger.info(f"Client requesting status (task_id: {task_id}). Current state: {task.state}.")
    if task.state == "PENDING":
        # job did not start yet
        response = {
            "state": task.state,
            "actions": None,
            "current": 0,
            "total": 1,
            "progress": 0,
            "status": "not-started",
        }
    else:

        # Need to translate legend names
        actions = task.info.get("actions", None)
        if actions is not None:
            if "source" in actions[0].keys():
                for i, val in enumerate(actions[0]["source"]):
                    legend_name = val.get("legend_name", None)
                    app.logger.info(f"Legend name: {legend_name}")
                    if legend_name is not None:
                        app.logger.info(f"Changing legend to: {flood_labels[legend_name]}")
                        actions[0]["source"][i]["legend_name"] = flood_labels[legend_name]

        response = {
            "state": task.state,
            "actions": actions,
            "current": task.info.get("current", 0),
            "total": task.info.get("total", 0),
            "progress": int(
                (task.info.get("current", 0) / task.info.get("total", 0)) * 100
            ),
            "status": task.info.get("status", 0),
        }
    return jsonify(response)

def money_formatter(number_to_be_formmatted):
    app.logger.debug(f'Number to be formatted: {number_to_be_formmatted}')
    number_to_be_formmatted = int(number_to_be_formmatted)
    rounding_digits = -1 * int(len(str(number_to_be_formmatted)))+2
    formmatted = round(number_to_be_formmatted, rounding_digits)

    # Place dollar sign before
    formatted_currency = format_currency(formmatted, 'USD', locale='en_US')
    # Remove cents
    formatted_currency = re.sub('\.00$', '', formatted_currency)
    app.logger.debug(f'Formatted: {formatted_currency}')
    return formatted_currency

labels = {
    "indoors_2am": _l("People indoors 2 AM"),
    "ser_injuries_2am": _l("Life-threatening injuries 2 AM"),
    "hospit_2am": _l("People hospitalized 2 AM"),
    "med_att_2am": _l("People requiring medical attention 2 AM"),
    "fatal_2am": _l("Fatalities 2 AM"),
    "indoors_2pm": _l("People indoors 2 PM"),
    "med_att_2pm": _l("People requiring medical attention 2 PM"),
    "hospit_2pm": _l("People hospitalized 2 PM"),
    "ser_injuries_2pm": _l("Life-threatening injuries 2 PM"),
    "fatal_2pm": _l("Fatalities 2 PM"),
    "indoors_5pm": _l("People indoors 5 PM"),
    "med_att_5pm": _l("People requiring medical attention 5 PM"),
    "hospit_5pm": _l("People hospitalized 5 PM"),
    "ser_injuries_5pm": _l("Life-threatening injuries 5 PM"),
    "fatal_5pm": _l("Fatalities 5 PM"),
    "pga": _l("Peak ground acceleration"),
    "norm_econ": _l("Normalized economic loss"),
    "loss_ratio": _l("Earthquake loss ratio"),
    "econ_loss": _l("Total economic loss"),
    "exposure": _l("Exposure"),
    "site": _l("Soil class"),
    "s1fv": _l("Sa @ 1.0 s"),
    "ssfa": _l("Sa @ 0.3 s"),
    "num_bldgs": _l("Buildings"),
    "no_damage": _l("Undamaged buildings"),
    "slight_damage": _l("Slightly damaged buildings"),
    "mod_damage": _l("Moderately damaged buildings"),
    "ext_damage": _l("Extensively damaged buildings"),
    "comp_damage": _l("Completely destroyed buildings")
}

flood_labels = {
    "total_exposure": _l("Structural exposure"),
    "struct_dmg": _l("Structural damage"),
    "cont_dmg": _l("Content damage"),
    "total_dmg": _l("Total damage"),
    "bldg_count": _l("Building count"),
    "bldgs_affected": _l("Buildings affected"),
    "population": _l("Population"),
    "affected_population": _l("Affected population")
}

seismic_headers = {
    "injuries_fatal_2am": ["indoors_2am", "ser_injuries_2am", "hospit_2am", "med_att_2am", "fatal_2am"],
    "injuries_fatal_2pm": ["indoors_2pm", "med_att_2pm", "hospit_2pm", "ser_injuries_2pm", "fatal_2pm"],
    "injuries_fatal_5pm": ["indoors_5pm", "med_att_5pm", "hospit_5pm", "ser_injuries_5pm", "fatal_5pm"],
    "ground_motion": ["pga", "site", "s1fv", "ssfa"],
    "economic": ["loss_ratio", "norm_econ", "econ_loss", "exposure"],
    "buildings": ["num_bldgs", "no_damage", "slight_damage", "mod_damage", "ext_damage", "comp_damage"],
}

flood_headers = {
    "economic": ["total_exposure", "struct_dmg", "cont_dmg", "total_dmg"],
    "pop": ["bldg_count", "bldgs_affected", "population", "affected_population"]
}

header_names = {
    "ground_motion": _l("Ground Motion Intensity"),
    "economic": _l("Economic"),
    "buildings": _l("Buildings"),
    "injuries_fatal_2am": _l("Injuries and Fatalities - 2 AM"),
    "injuries_fatal_2pm": _l("Injuries and Fatalities - 2 PM"),
    "injuries_fatal_5pm": _l("Injuries and Fatalities - 5 PM"),
    "pop": _l("Population and Buildings"),
    "economic": _l("Economic")
}

units_after = {
    "norm_econ": "/building",
    "loss_ratio": "%",
    "pga": " g",
    "s1fv": " g",
    "s1fv": " g",
    "ssfa": " g",
}

@app.route("/<module>/query", methods=["GET"])
def query(module):
    id = request.args.get("id")
    xCoord = float(request.args.get("wx"))
    yCoord = float(request.args.get("wy"))
    srs = int(request.args.get("srs"))
    app.logger.info(f"Client querying results for polygon capturing x={xCoord}, y={yCoord}")
    if module == 'seismic':
        conn = psycopg2.connect(db_conn_str_eq)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tract, injuries_5pm, injuries_2pm, injuries_2am, fatal_5pm, ser_injuries_5pm, hospit_5pm, med_att_5pm, indoors_5pm, fatal_2pm, ser_injuries_2pm, hospit_2pm, med_att_2pm, indoors_2pm, fatal_2am, ser_injuries_2am, hospit_2am, med_att_2am, indoors_2am, loss_ratio, econ_loss_norm, econ_loss, exposure, comp_damage, ext_damage, mod_damage, slight_damage, no_damage, num_bldgs, pga, s1fv, ssfa, site, ST_AsText(geom), ST_AsGeoJSON(geom) FROM "er2wps_view"
            WHERE job_id = %s
            AND (ST_Contains(geom,
            st_transform(ST_SetSRID(ST_MakePoint(%s, %s), %s),4269)))
            """,
            (
                id,
                xCoord,
                yCoord,
                srs
            )
        )
    if module == 'flood':
        conn = psycopg2.connect(db_conn_str_flood)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT censusbloc, bldg_count, bldg_exposure, cont_exposure, total_exposure, struct_dmg, cont_dmg, total_dmg, bldgs_affected, population, affected_population, ST_AsText(geom), ST_AsGeoJSON(geom) FROM "flood_result_view_2"
            WHERE sim_id = %s
            AND (ST_Contains(geom,
            st_transform(ST_SetSRID(ST_MakePoint(%s, %s), %s),4269)))
            """,
            (
                id,
                xCoord,
                yCoord,
                srs
            )
        )

    queriedBlock = None
    for row in cur.fetchall():
        queriedBlock = dict(zip([column[0]
                                 for column in cur.description], row))
    # queriedBlock = json.dumps(queriedBlock)
    cur.close()
    vector = queriedBlock["st_asgeojson"]

    results = []
    headers = []
    tract_id = ""
    if module == 'seismic':
        tract_id = queriedBlock["tract"]
        norm_econ = int(int(queriedBlock["econ_loss"])/queriedBlock["num_bldgs"])
        norm_econ = money_formatter(norm_econ)
        econ_loss = money_formatter(queriedBlock["econ_loss"])
        exposure = money_formatter(queriedBlock["exposure"])
        seismic_values = {
            "indoors_2am": queriedBlock["indoors_2am"],
            "ser_injuries_2am": queriedBlock["ser_injuries_2am"],
            "hospit_2am": queriedBlock["hospit_2am"],
            "med_att_2am": queriedBlock["med_att_2am"],
            "fatal_2am": queriedBlock["fatal_2am"],
            "indoors_2pm": queriedBlock["indoors_2pm"],
            "med_att_2pm": queriedBlock["med_att_2pm"],
            "hospit_2pm": queriedBlock["hospit_2pm"],
            "ser_injuries_2pm": queriedBlock["ser_injuries_2pm"],
            "fatal_2pm": queriedBlock["fatal_2pm"],
            "indoors_5pm": queriedBlock["indoors_5pm"],
            "med_att_5pm":queriedBlock["med_att_5pm"],
            "hospit_5pm": queriedBlock["hospit_5pm"],
            "ser_injuries_5pm": queriedBlock["ser_injuries_5pm"],
            "fatal_5pm": queriedBlock["fatal_5pm"],
            "pga": str(queriedBlock["pga"]),
            "norm_econ": norm_econ,
            "loss_ratio": str(queriedBlock["loss_ratio"]),
            "econ_loss": econ_loss,
            "exposure": exposure,
            "site": queriedBlock["site"],
            "s1fv": str(queriedBlock["s1fv"]),
            "ssfa": str(queriedBlock["ssfa"]),
            "num_bldgs": queriedBlock["num_bldgs"],
            "no_damage": queriedBlock["no_damage"],
            "slight_damage": queriedBlock["slight_damage"],
            "mod_damage": queriedBlock["mod_damage"],
            "ext_damage": queriedBlock["ext_damage"],
            "comp_damage": queriedBlock["comp_damage"]
        }

        for identifier in seismic_values.keys():
            result = {
                "label": labels[identifier],
                "value": seismic_values[identifier],
                "unitAfter": units_after.get(identifier, ''),
                "unitBefore": "",
                "header": [i for i in seismic_headers if identifier in seismic_headers[i]][0]
            }
            results.append(result)

        for header in seismic_headers.keys():
            headers.append({"name": header_names[header], "id": header})

    if module == 'flood':
        app.logger.info("Exposures")
        app.logger.info(queriedBlock["total_exposure"])
        app.logger.info(queriedBlock["cont_exposure"])
        app.logger.info(queriedBlock["bldg_exposure"])

        tract_id = queriedBlock["censusbloc"]
        flood_values = {
            "bldg_count": queriedBlock["bldg_count"],
            "bldgs_affected": math.ceil(queriedBlock["bldgs_affected"]),
            "total_exposure": money_formatter(queriedBlock["total_exposure"]*1000),
            "struct_dmg": money_formatter(queriedBlock["struct_dmg"]*1000),
            "cont_dmg": money_formatter(queriedBlock["cont_dmg"]*1000),
            "total_dmg": money_formatter(queriedBlock["total_dmg"]*1000),
            "population": queriedBlock["population"],
            "affected_population": math.ceil(queriedBlock["affected_population"])
        }
        for identifier in flood_values.keys():
            result = {
                "label": flood_labels[identifier],
                "value": flood_values[identifier],
                "unitAfter": "",
                "unitBefore": "",
                "header": [i for i in flood_headers if identifier in flood_headers[i]][0]
            }
            results.append(result)

        for header in flood_headers.keys():
            headers.append({"name": header_names[header], "id": header})

    returnedObj = {
        "featureInfo": {
            "context": {
                "job_id": id,
                "x": xCoord,
                "y": yCoord,
                "srs": srs,
                "tract_id": tract_id
            },
            "headers": headers,
            "results": results,
            "geojson": vector
        }
    }

    return returnedObj
