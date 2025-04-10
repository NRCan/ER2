import json
import numpy as np
import pandas as pd
import os
import time
from scipy import interpolate
import random
from datetime import datetime
import math
import uuid
from pprint import pprint
import logging
import csv
from pdb import set_trace as bp

logging.basicConfig(level=logging.DEBUG,
                    format=' %(asctime)s - %(levelname)s - %(message)s')
# logging.disable()

logging.info("Loading dependencies into memory")

DATA_ROOT = "/home/<username>/Desktop/hand/validation/Part I_ elevations/Dependencies/damage_calc/"

# Elevation profiles for each census tract
elevations = pd.read_csv(f'{DATA_ROOT}elevations_01percentiles.csv').values

CalculationsNotPossible = pd.read_csv(
    f'{DATA_ROOT}calculations-not-possible.csv')["CensusBloc"].values

ineligibleBlocks = elevations[np.isin(
    elevations[:, 0], CalculationsNotPossible, assume_unique=True)]

eligibleBlocks = elevations[np.isin(
    elevations[:, 0], CalculationsNotPossible, assume_unique=True, invert=True)]

# For each bldgType, variables like ba, ft, st, factor, ...
floodValues = pd.read_pickle(f'{DATA_ROOT}flood_values/floodValues.pkl')

# Convert to dictionary because it's faster
ftDict = floodValues["ft"].to_dict()
for key in ftDict.keys():
    ftDict[key] = str(ftDict[key])
boDict = floodValues["bo"].to_dict()
damageCurveDict = floodValues["numberCode"].to_dict()
structureDamageDF = pd.read_pickle(
    f'{DATA_ROOT}structure_damage/structureDamageDF.pkl')
structureDamageDict = structureDamageDF.T.to_dict()
structureDamageHeader = np.asarray(structureDamageDF.columns)

contentDamageDF = pd.read_pickle(
    f'{DATA_ROOT}content_damage/contentDamageDF.pkl')
contentDamageDict = contentDamageDF.T.to_dict()
contentDamageHeader = np.asarray(contentDamageDF.columns)
boValuesDF = pd.read_pickle(f'{DATA_ROOT}building_occupancy/boValuesDF.pkl')
contentsPercentageDict = boValuesDF["contentsPercentage"]

adjustedBuildingValues = pd.read_pickle(
    f'{DATA_ROOT}building_values/adjustedBuildingValues.pkl')

eligibleBlocksDF = pd.read_pickle(
    f'{DATA_ROOT}flood_values/eligibleBlocksDF.pkl')
eligibleBlocksDict = eligibleBlocksDF.to_dict()
logging.info("Dependencies loaded into memory")

# Here we will set the water level arbitarily (in m), but in the application the water level is specified by the user.
waterLevel = 5
simId = str(uuid.uuid4())
logging.info(f"Assigned simulation ID: {simId}")

logging.info("Determining hazard...")
logging.info("Identifying flooded eligible blocks...")
# Blocks are flooded if the water level exceeds the lowest elevation
# Determine the affected blocks - store their Ids and elevation profiles
eligibleBlocksFloodCriteria = eligibleBlocks[:, 1] < waterLevel
affectedCalcBlocks = eligibleBlocks[eligibleBlocksFloodCriteria]
affectedCalcBlocksIds = affectedCalcBlocks[:, 0].view().astype(np.int64)
affectedCalcBlocksElevations = affectedCalcBlocks[:, 1:].view()

# Check what ineligible blocks are flooded
logging.info("Identifying flooded ineligible blocks...")
ineligibleBlocksFloodCriteria = ineligibleBlocks[:, 1] < waterLevel
affectedButNotCalculatableBlocks = ineligibleBlocks[ineligibleBlocksFloodCriteria][:, 0]

# Get certain features
highestGroundElevation = affectedCalcBlocksElevations[:, -1]
lowestGroundElevation = affectedCalcBlocksElevations[:, 0]
highestFloodDepths = waterLevel - lowestGroundElevation
lowestFloodDepth = waterLevel - highestGroundElevation

interpolationStart = highestGroundElevation.copy()

# A negative flood depth implies the block is only PARTIALLY inundated
# For partially inundated, start interpolation at the water level
lowestFloodDepth[lowestFloodDepth < 0] = 0
interpolationStart[lowestFloodDepth == 0] = waterLevel

# Categories
oneFoot = 0.3048
intervalStep = -oneFoot
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
logging.debug(f"Number of blocks affected: {numBlocksAffected}")

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

# Just a more convenient way to structure hazard definition
hz = {}
for i in hazardDefinition:
    hz[i[0]] = list(zip(i[1], i[2]))

logging.info("Hazard defined.")

json.dump(hazardDefinition, open(
    "/home/<username>/Desktop/hand/validation_2/hazard/hazardDefinition.json", 'w'))

logging.info("Determining damages...")
start_time = datetime.now()
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

percentagesDF = pd.DataFrame(np.asarray(
    percentages), index=affectedCalcBlocksIds)
percentagesDict = dict(zip([i for i in affectedCalcBlocksIds], percentages))

completedBlocks = []

validation_data = []

hazards = {}


def computeDamages(bldgValue, progressOutOf):
    # For each block, make a record of all the building valuations and outputted damage estimations
    validation_item = {}

    # Store block ID
    blockId = str(bldgValue.name)

    # If there is no inventory present, move onto next block
    if (bldgValue.values == 0).all():
        return {
            "total": 0,
            "structure": 0,
            "content": 0
        }

    hazards[blockId] = hz[blockId]

    logging.debug(blockId)
    blockPopulation = eligibleBlocksDict['population'][blockId]
    buildingCount = eligibleBlocksDict['bc'][blockId]
    buildingValue = eligibleBlocksDict['bv'][blockId]
    blockOverallFlooded = overallFloodedDict[blockId]

    bldgs_affected = buildingCount * blockOverallFlooded / 100
    affected_population = blockPopulation * blockOverallFlooded / 100

    completedBlocks.append(blockId)
    ticker = len(completedBlocks)
    wp = percentagesDict[blockId]

    # Only want buldings with values > than zero
    affectedNamesList = [i[0] for i in bldgValue.index[bldgValue > 0].tolist()]

    totalStructural = 0
    totalContents = 0
    for bldgType in affectedNamesList:
        validation_item[bldgType] = {}
        damageCurve = damageCurveDict[bldgType]
        validation_item[bldgType]["Cost"] = bldgValue[bldgType].values[0]

        ft = ftDict[bldgType]

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
            structureInterpSet = np.append(
                structureInterpSet, structureDic[wd])
            contentInterpSet = np.append(contentInterpSet, contentDic[wd])

        structureSumOneBldgType = round(
            (
                ((np.multiply(structureInterpSet, wp).sum())
                 * bldgValue[bldgType])
                / 10000
            ).values[0],
            3,
        )

        totalStructural += structureSumOneBldgType

        validation_item[bldgType]['bo'] = boDict[bldgType]

        contentSumOneBldgType = round(
            (
                ((np.multiply(contentInterpSet, wp).sum())
                 * bldgValue[bldgType])
                / 10000
            ).values[0]
            * contentsPercentage,
            3,
        )

        totalContents += contentSumOneBldgType
        validation_item[bldgType]["NumStories"] = str(
            floodValues.loc[bldgType]["st"])
        foundationType = None
        if "Basement-Y" in bldgType:
            foundationType = "4"
        elif "Crawl" in bldgType:
            foundationType = "5"
        else:
            foundationType = "7"

        validation_item[bldgType]["FoundationType"] = foundationType
        validation_item[bldgType]["Area"] = "1"
        validation_item[bldgType]["FirstFloorHt"] = str(
            floodValues.loc[bldgType]["ft"])
        validation_item[bldgType]["blockId"] = str(blockId)

        if blockId in ['240818100550007', '240818101490001', '240818100590004', '240818101510007', '240818100590006']:
            df = pd.DataFrame(validation_item).T
            df.index.name = 'bldgType'
            df.reset_index()
            df.to_csv(f'{blockId}_input.csv')
    progress = (ticker / progressOutOf) * 100

    return {
        "total": int(totalStructural + totalContents),
        "structure": int(totalStructural),
        "content": int(totalContents),
    }


damages = adjInventory.apply(
    computeDamages, progressOutOf=progressOutOf, axis=1)

logging.info("Damages computed.")

end_time = datetime.now()
elapsed_time = end_time - start_time

logging.info(f'Damages calculated in {elapsed_time} seconds')
