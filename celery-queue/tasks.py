import os
import logging
LOGGINGLEVEL = os.environ.get('LOGGINGLEVEL', 'WARNING')
logging.basicConfig(level=LOGGINGLEVEL, format=' %(asctime)s - %(levelname)s - %(message)s')
import time
from celery import Celery
import rasterio
import pandas as pd
import numpy as np
import psycopg2
from scipy import interpolate
import random
from datetime import datetime
import math
import requests
import xml.etree.ElementTree as ET
import sys
import uuid


CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND')
logging.info("Creating Celery instance.")
celery = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

logging.info("Loading dependencies into memory")
GAT_RASTER = rasterio.open('./dependencies/dtmconditionedhandcropped_wgs841.tif')
elevations = pd.read_csv('./dependencies/elevations_01percentiles.csv').values
CalculationsNotPossible = pd.read_csv("./dependencies/calculations-not-possible.csv")["CensusBloc"].values
ineligibleBlocks = elevations[np.isin(elevations[:, 0], CalculationsNotPossible, assume_unique=True)]
eligibleBlocks = elevations[np.isin(elevations[:, 0], CalculationsNotPossible, assume_unique=True, invert=True)]


# calculate damages variables below
floodValues = pd.read_pickle("./dependencies/flood_values/floodValues.pkl")
ftDict = floodValues["ft"].to_dict()
boDict = floodValues["bo"].to_dict()
for key in ftDict.keys():
    ftDict[key] = str(ftDict[key])
damageCurveDict = floodValues["numberCode"].to_dict()
structureDamageDF = pd.read_pickle("./dependencies/structure_damage/structureDamageDF.pkl")
structureDamageDict = structureDamageDF.T.to_dict()
structureDamageHeader = np.asarray(structureDamageDF.columns)

contentDamageDF = pd.read_pickle("./dependencies/content_damage/contentDamageDF.pkl")
contentDamageDict = contentDamageDF.T.to_dict()
contentDamageHeader = np.asarray(contentDamageDF.columns)
boValuesDF = pd.read_pickle("./dependencies/building_occupancy/boValuesDF.pkl")
contentsPercentageDict = boValuesDF["contentsPercentage"]

adjustedBuildingValues = pd.read_pickle("./dependencies/building_values/adjustedBuildingValues.pkl")

eligibleBlocksDF = pd.read_pickle('./dependencies/flood_values/eligibleBlocksDF.pkl')
eligibleBlocksDict = eligibleBlocksDF.to_dict()

DB = os.environ.get('DB')
DB_USER = os.environ.get('DB_USER')
DB_HOST = os.environ.get('DB_HOST')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_PORT = os.environ.get('DB_PORT')

cs = "dbname=%s user=%s password=%s host=%s port=%s" % (DB,DB_USER,DB_PASSWORD,DB_HOST,DB_PORT)

FLOOD_MAP_SERVICE = os.environ.get('FLOOD_MAP_SERVICE')

def get_legend_urls():
    getCapUrl = '{FLOOD_MAP_SERVICE}&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities'.format(FLOOD_MAP_SERVICE=FLOOD_MAP_SERVICE)
    response = requests.get(getCapUrl)
    root = ET.fromstring(response.content)
    legendURLs = {}
    for layer in root.iter('{http://www.opengis.net/wms}Layer'):
        name = layer.find('{http://www.opengis.net/wms}Name').text
        if name != 'flood':
            for legend in layer.iter('{http://www.opengis.net/wms}LegendURL'):
                for legendOnlineResource in legend.iter('{http://www.opengis.net/wms}OnlineResource'):
                    legendURLs[name] = legendOnlineResource.attrib['{http://www.w3.org/1999/xlink}href']
    return legendURLs

try:
    legendURLs = get_legend_urls()
except:
    logging.error('Failed to fetch legend URLs from getCapabilities request. Falling back on default URLs.')
    legendURLs = {
        'affected_population': '{FLOOD_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=affected_population&format=image/png&STYLE='.format(FLOOD_MAP_SERVICE=FLOOD_MAP_SERVICE),
        'bldgs_affected': '{FLOOD_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=bldgs_affected&format=image/png&STYLE='.format(FLOOD_MAP_SERVICE=FLOOD_MAP_SERVICE),
        'gat_blocks': '{FLOOD_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=gat_blocks&format=image/png&STYLE='.format(FLOOD_MAP_SERVICE=FLOOD_MAP_SERVICE),
        'gat_boundary': '{FLOOD_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=gat_boundary&format=image/png&STYLE='.format(FLOOD_MAP_SERVICE=FLOOD_MAP_SERVICE),
        'population': '{FLOOD_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=population&format=image/png&STYLE='.format(FLOOD_MAP_SERVICE=FLOOD_MAP_SERVICE),
        'total_dmg': '{FLOOD_MAP_SERVICE}&version=1.3.0&service=WMS&request=GetLegendGraphic&sld_version=1.1.0&layer=total_dmg&format=image/png&STYLE='.format(FLOOD_MAP_SERVICE=FLOOD_MAP_SERVICE)
    }

@celery.task(name='tasks.get_hand_value')
def get_hand_value(x: float, y: float):
    # example: /tiffValue?x=-75.67502975&y=45.46843792
    tiff_value = None
    logging.info("Getting raster value")
    try:
        for val in GAT_RASTER.sample([(x,y)]):
            tiff_value = val[0]
            if round(tiff_value,2) < -3.30:
                return "Out of bounds"
            else:
                return str(tiff_value)
    except:
        return "Out of bounds"

@celery.task(name='tasks.calculate_damages', bind=True)
def calculate_damages(self, x, y, waterLevel):
    conn = psycopg2.connect(cs)
    cur = conn.cursor()
    simId = str(uuid.uuid4())
    siteCoordinates = {"long": x, "lat": y}
    simulationStatus = "ongoing"
    startTime = datetime.now()
    endTime = None
    simPercent = 0

    cur.execute(
        """
        INSERT INTO "flood_simulation" (sim_id, sim_status, sim_started,
        sim_completed, sim_percent_completed, sim_depth, sim_location_lat,
        sim_location_long, sim_site)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s),4269));
        """,
        (
            simId,
            simulationStatus,
            startTime,
            endTime,
            simPercent,
            waterLevel,
            siteCoordinates["lat"],
            siteCoordinates["long"],
            siteCoordinates["long"],
            siteCoordinates["lat"],
        ),
    )
    conn.commit()
    logging.info("Simulation record inserted into database")

    logging.info("Determining hazard...")

    eligibleBlocksFloodCriteria = eligibleBlocks[:, 1] < waterLevel
    affectedCalcBlocks = eligibleBlocks[eligibleBlocksFloodCriteria]
    affectedCalcBlocksIds = affectedCalcBlocks[:, 0].view().astype(np.int64)
    affectedCalcBlocksElevations = affectedCalcBlocks[:, 1:].view()

    ineligibleBlocksFloodCriteria = ineligibleBlocks[:, 1] < waterLevel
    affectedButNotCalculatableBlocks = ineligibleBlocks[ineligibleBlocksFloodCriteria][
        :, 0
    ]
    highestGroundElevation = affectedCalcBlocksElevations[:, -1]
    lowestGroundElevation = affectedCalcBlocksElevations[:, 0]
    highestFloodDepths = waterLevel - lowestGroundElevation
    lowestFloodDepth = waterLevel - highestGroundElevation

    lowestFloodDepth[lowestFloodDepth < 0] = 0

    interpolationStart = highestGroundElevation.copy()
    interpolationStart[lowestFloodDepth == 0] = waterLevel

    intervalStep = -0.3048
    interpolationPoints = []

    startStop = list(zip(interpolationStart, lowestGroundElevation))
    for start, stop in startStop:
        singleInterpSet = np.arange(start, stop, intervalStep)
        interpolationPoints.append(singleInterpSet)

    groundPercentY = np.arange(0, 100.011, 0.1)
    allCumCoverages = []
    allDepths = []

    for i, blockElevationProfile in enumerate(affectedCalcBlocksElevations):
        x = blockElevationProfile
        y = groundPercentY
        f = interpolate.interp1d(x, y)
        interpolationSet = interpolationPoints[i]
        cumulativeCoverage = f(interpolationSet)
        allCumCoverages.append(cumulativeCoverage)

        depths = waterLevel - interpolationSet - intervalStep

        highestFloodDepth = highestFloodDepths[i]
        if depths[-1] > highestFloodDepth:
            depths[-1] = highestFloodDepth

        meterFeetConversion = 3.28084
        depths = [round(i * meterFeetConversion, 3) for i in depths]
        allDepths.append(depths)

    numBlocksAffected = len(affectedCalcBlocksIds)
    overallFloodedArray = np.empty((0, numBlocksAffected))
    allCoverages = []

    for cumCoverageSet in allCumCoverages:
        coverages = []
        for inx, val in enumerate(cumCoverageSet):
            notLastIndex = inx < len(cumCoverageSet) - 1
            if notLastIndex:
                nextVal = cumCoverageSet[inx + 1]
                adjustedValue = round(val - nextVal, 3)
                coverages.append(adjustedValue)
            else:
                coverages.append(round(val, 3))

        percentSum = sum(coverages)
        if percentSum > 100.0:
            exceedingBy = percentSum - 100.0
            coverages[0] = round(coverages[0] - exceedingBy - 0.005, 2)

        allCoverages.append(coverages)

        totalFloodExtent = cumCoverageSet[0]
        overallFloodedArray = np.append(overallFloodedArray, totalFloodExtent)

    hazardDefinition = list(
        zip(
            [str(i) for i in affectedCalcBlocksIds.tolist()],
            allDepths,
            allCoverages,
            overallFloodedArray.round(3),
        )
    )

    logging.info("Hazard defined.")
    logging.info("Determining damages...")
    progressOutOf = len(affectedCalcBlocksIds)
    affectedCalcBlocksIds = [i[0] for i in hazardDefinition]
    depths = [i[1] for i in hazardDefinition]
    percentages = [i[2] for i in hazardDefinition]
    overallFlooded = [i[3] for i in hazardDefinition]
    overallFloodedDict = dict(zip(affectedCalcBlocksIds, overallFlooded))

    adjInventory = adjustedBuildingValues[
        adjustedBuildingValues.index.isin(affectedCalcBlocksIds)
    ]
    adjInventory.index = adjInventory.index.map(int)

    depthsDict = {
        "0": [np.array([x for x in depthList]) for depthList in depths],
        "1": [np.array([x - 1 for x in depthList]) for depthList in depths],
        "3": [np.array([x - 3 for x in depthList]) for depthList in depths],
        "4": [np.array([x - 4 for x in depthList]) for depthList in depths],
    }

    wdft = depthsDict.copy()

    for ftKey, ftAllValues in depthsDict.items():
        for i, ftValue in enumerate(ftAllValues):
            wdft[ftKey][i] = np.rint(ftValue)
            np.place(wdft[ftKey][i], wdft[ftKey][i] > 23, 23)
            np.place(wdft[ftKey][i], wdft[ftKey][i] < -4, -4)
        wdft[ftKey] = dict(zip(affectedCalcBlocksIds, wdft[ftKey]))

    percentagesDF = pd.DataFrame(np.asarray(percentages), index=affectedCalcBlocksIds)
    percentagesDict = dict(zip([i for i in affectedCalcBlocksIds], percentages))

    completedBlocks = []
    def computeDamages(bldgValue, progressOutOf):
        # Store block ID
        blockId = str(bldgValue.name)

        blockPopulation = eligibleBlocksDict['population'][blockId]
        buildingCount = eligibleBlocksDict['bc'][blockId]
        buildingValue = eligibleBlocksDict['bv'][blockId]
        blockOverallFlooded = overallFloodedDict[blockId]

        bldgs_affected = buildingCount * blockOverallFlooded / 100
        affected_population = blockPopulation * blockOverallFlooded / 100


        completedBlocks.append(blockId)
        ticker = len(completedBlocks)
        wp = percentagesDict[blockId]

        # Only some buldings have values > than zero
        affectedNamesList = [i[0] for i in bldgValue.index[bldgValue > 0].tolist()]

        totalStructural = 0
        totalContents = 0
        for bldgType in affectedNamesList:
            ft = ftDict[bldgType]

            damageCurve = damageCurveDict[bldgType]
            structureDamageValues = np.array(
                list(structureDamageDict[damageCurve].values())
            )
            contentDamageValues = np.array(
                list(contentDamageDict[damageCurve].values())
            )
            bldgTypeShort = boDict[bldgType]

            contentsPercentage = contentsPercentageDict[bldgTypeShort] / 100

            wdset = wdft[ft][blockId]

            structureDic = dict(zip(structureDamageHeader, structureDamageValues))
            contentDic = dict(zip(contentDamageHeader, contentDamageValues))

            structureInterpSet = np.array([])
            contentInterpSet = np.array([])

            for wd in wdset:
                structureInterpSet = np.append(structureInterpSet, structureDic[wd])
                contentInterpSet = np.append(contentInterpSet, contentDic[wd])

            structureSumOneBldgType = round(
                (
                    ((np.multiply(structureInterpSet, wp).sum()) * bldgValue[bldgType])
                    / 10000
                ).values[0],
                3,
            )
            totalStructural += structureSumOneBldgType

            contentSumOneBldgType = round(
                (
                    ((np.multiply(contentInterpSet, wp).sum()) * bldgValue[bldgType])
                    / 10000
                ).values[0]
                * contentsPercentage,
                3,
            )
            totalContents += contentSumOneBldgType

        progress = (ticker / progressOutOf) * 100
        cur.execute(
            """
            INSERT INTO "flood_sim_result" (sim_id, block_num, bldg_count, bldg_exposure, cont_exposure, total_exposure, struct_dmg, cont_dmg, total_dmg, bldgs_affected, population, affected_population)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                simId,
                blockId,
                buildingCount,
                0,
                0,
                buildingValue,
                int(totalStructural),
                int(totalContents),
                int(totalContents + totalStructural),
                bldgs_affected,
                blockPopulation,
                affected_population,
            ),
        )
        conn.commit()
        cur.execute(
            """
            UPDATE "flood_simulation"
            SET sim_percent_completed = (%s)
            WHERE sim_id = (%s)
            """,
            (progress, simId),
        )
        conn.commit()
        service = os.environ.get('FLOOD_MAP_SERVICE')

        legendBase = "{service}&SERVICE=WMS&VERSION=1.3.0&REQUEST=getlegendgraphic&FORMAT=image/png&sld_version=1.1.0&map=/map/er2/flood.map&layer=".format(service=service)
        query_info_url = os.environ.get("ER2_API")+"/flood/query?id=" + simId


        actions = [
            {
                "type": "load-layer",
                "source": [
                    {
                        "legend_name": "total_dmg",
                        "id": simId + "_total_dmg",
                        "name": "total_dmg",
                        "simId": simId,
                        "serverType": "mapserver",
                        "service": service,
                        "styles": "",
                        "type": "wms-layer",
                        "query_info_url": query_info_url,
                        "legend_url": legendURLs['total_dmg']
                    },
                    {
                        "legend_name": "bldgs_affected",
                        "id": simId + "_bldgs_affected",
                        "name": "bldgs_affected",
                        "simId": simId,
                        "serverType": "mapserver",
                        "service": service,
                        "styles": "",
                        "type": "wms-layer",
                        "query_info_url": query_info_url,
                        "legend_url": legendURLs['bldgs_affected']
                    },
                    {
                        "legend_name": "population",
                        "id": simId + "_population",
                        "name": "population",
                        "simId": simId,
                        "serverType": "mapserver",
                        "service": service,
                        "styles": "",
                        "type": "wms-layer",
                        "query_info_url": query_info_url,
                        "legend_url": legendURLs['population']
                    },
                    {
                        "legend_name": "affected_population",
                        "id": simId + "_affected_population",
                        "name": "affected_population",
                        "simId": simId,
                        "serverType": "mapserver",
                        "service": service,
                        "styles": "",
                        "type": "wms-layer",
                        "query_info_url": query_info_url,
                        "legend_url": legendURLs['affected_population']
                    },
                ],
            }
        ]
        self.update_state(
            state="PROGRESS",
            meta={
                "actions": actions,
                "current": ticker,
                "total": progressOutOf,
                "status": "ongoing",
                "progress": progress,
            },
        )

        return {
            "total": int(totalStructural + totalContents),
            "structure": int(totalStructural),
            "content": int(totalContents),
        }
    damages = adjInventory.apply(computeDamages, progressOutOf=progressOutOf, axis=1)

    logging.info("Damages computed.")

    self.update_state(
        state="PROGRESS",
        meta={
            "current": progressOutOf,
            "total": progressOutOf,
            "status": "done",
            "actions": None,
            "progress": 100,
        },
    )

    # Mark the simulation as complete in db
    end_time = datetime.now()
    simulationStatus = "completed"
    cur.execute(
        """
        UPDATE "flood_simulation"
        SET sim_completed = (%s), sim_status= (%s)
        WHERE sim_id = (%s)
        """,
        (end_time, simulationStatus, simId),
    )
    conn.commit()

    logging.info("Closing db connection.")
    cur.close()
    time.sleep(6)
    return "Simulation complete"

