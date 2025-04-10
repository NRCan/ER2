import json
import numpy as np
from pprint import pprint
import pandas as pd
import csv
import pickle

import logging
logging.basicConfig(level=logging.DEBUG,
                    format=' %(asctime)s - %(levelname)s - %(message)s')
logging.disable()
logging.info("Loading damage curves")
structure_damage_curves = pd.read_csv(
    "/home/<username>/Desktop/Hazus/FAST/Lookuptables/Building_DDF_Riverine_LUT_Hazus4p0.csv", index_col=["DDF_ID"])

content_damage_curves = pd.read_csv(
    "/home/<username>/Desktop/Hazus/FAST/Lookuptables/Content_DDF_Riverine_LUT_Hazus4p0.csv", index_col=["DDF_ID"])

column_list = ['Occupancy', 'SpecificOccupId', 'Source', 'Description', 'Stories',
               'Comment', '-4', '-3', '-2', '-1', '0', '1', '2', '3', '4', '5',
               '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16',
               '17', '18', '19', '20', '21', '22', '23', '24',
               'Basement', 'HazardRiverine', 'HazardCV', 'HazardCA', 'SortOrder']

structure_damage_curves.columns = column_list
content_damage_curves.columns = column_list


# Computed and saved by separate script
logging.info("Loading hazard definition")
hazardDefinition = json.load(open("hazard/hazardDefinition.json"))

logging.info("Pre-processing hazard definition")
# 0th element is block ID, 1st element is depths, 2nd is percentages
affectedCalcBlocksIds = [i[0] for i in hazardDefinition]
raw_depths = [i[1] for i in hazardDefinition]
percentages = [i[2] for i in hazardDefinition]
percentagesDict = dict(zip([i for i in affectedCalcBlocksIds], percentages))


def adjust_depths_by_ft(depths):
    # Do the ft subtraction now, for later lookup
    ft_adjusted_depths = {
        "0": [np.array([x for x in depthList]) for depthList in depths],
        "1": [np.array([x - 1 for x in depthList]) for depthList in depths],
        "3": [np.array([x - 3 for x in depthList]) for depthList in depths],
        "4": [np.array([x - 4 for x in depthList]) for depthList in depths],
    }
    return ft_adjusted_depths


def round_depth_values(ft_adjusted_depths):
    # Adjust values greater than 24 or less than -4
    # Also, round to integer
    # wdtf is what you'll go to damage curve with
    rounded_depths = ft_adjusted_depths.copy()
    for ftKey, ftAllValues in ft_adjusted_depths.items():
        for i, ftValue in enumerate(ftAllValues):
            rounded_depths[ftKey][i] = np.rint(ftValue)
            np.place(rounded_depths[ftKey][i],
                     rounded_depths[ftKey][i] > 23, 23)
            np.place(rounded_depths[ftKey][i],
                     rounded_depths[ftKey][i] < -4, -4)
        rounded_depths[ftKey] = dict(
            zip(affectedCalcBlocksIds, rounded_depths[ftKey]))
    return rounded_depths


def calculate_structure_damage(building_info):
    # Unpack arguments
    blockId = building_info["blockId"]
    ft = building_info["ft"]
    if ft=="0.01":
        ft="0"
    StructureCost = building_info["StructureCost"]
    ContentCost = building_info["ContentCost"]

    structure_damage_curve = building_info["structure_damage_curve"]
    content_damage_curve = building_info["content_damage_curve"]
    wp = building_info["wp"]
    logging.info(
        f'Determining damages for block {blockId}, ft={ft}, StructureCost={StructureCost}, structure_damage_curve={structure_damage_curve}')

    unadjusted_depths = [i[1]
                         for i in hazardDefinition if i[0] == blockId]
    ft_adjusted_depths = rounded_depths[ft][blockId]

    logging.info('Using pre-determined hazard')
    logging.info(f'Unadjusted depths: {unadjusted_depths}')
    logging.info(f'Adjusted depths for damage curve: {ft_adjusted_depths}')
    logging.info(f'Percentages: {wp}')

    # Values interpolated from the damage curves
    st_damage_curve_values = np.array([])
    ct_damage_curve_values = np.array([])

    # Go through adjusted depths, get the corresponding damage curve value
    for depth in ft_adjusted_depths:
        depth = str(int(depth))

        # If multiple, take only first one
        try:
            st_damage_curve_value = structure_damage_curves.loc[structure_damage_curve][depth].iloc[0]
            ct_damage_curve_value = content_damage_curves.loc[content_damage_curve][depth].iloc[0]
        except:
            st_damage_curve_value = structure_damage_curves.loc[structure_damage_curve][depth]
            ct_damage_curve_value = content_damage_curves.loc[content_damage_curve][depth]

        st_damage_curve_values = np.append(
            st_damage_curve_values, st_damage_curve_value)
        ct_damage_curve_values = np.append(
            ct_damage_curve_values, ct_damage_curve_value)
    logging.info(f'Structural damage curve values: {st_damage_curve_values}')
    logging.info(f'Structural damage curve values: {ct_damage_curve_values}')

    st_damage_by_depth = np.round(
        (np.multiply(st_damage_curve_values, wp)/10000)*StructureCost, 2)
    st_damage_total = st_damage_by_depth.sum()
    st_unscaled_by_wp = np.multiply(
        st_damage_by_depth, np.reciprocal(np.array(wp)))*100

    ct_damage_by_depth = np.round(
        (np.multiply(ct_damage_curve_values, wp)/10000)*ContentCost, 2)
    ct_damage_total = ct_damage_by_depth.sum()
    ct_unscaled_by_wp = np.multiply(
        ct_damage_by_depth, np.reciprocal(np.array(wp)))*100

    damages = {
        "ct_scaled_by_wp": np.round(ct_damage_by_depth, 1),
        "ct_unscaled_by_wp": np.round(ct_unscaled_by_wp, 1),
        "st_scaled_by_wp": np.round(st_damage_by_depth, 1),
        "st_unscaled_by_wp": np.round(st_unscaled_by_wp, 1),
        "wp": np.array(wp),
        "st_total": round(st_damage_total, 1),
        "ct_total": round(ct_damage_total, 1)
    }
    return damages


ft_adjusted_depths = adjust_depths_by_ft(raw_depths)
rounded_depths = round_depth_values(ft_adjusted_depths)

input_df_path = "/home/<username>/Desktop/hand/validation_2/nick_input.csv"
input_file = csv.DictReader(open(input_df_path))


results = {
    'scaled': {
        'FAST': {
            'ct': [],
            'st': []
        },
        'Nick': {
            'ct': [],
            'st': []
        }
    },
    'unscaled': {
        'FAST': {
            'ct': [],
            'st': []
        },
        'Nick': {
            'ct': [],
            'st': []
        }
    }
}
for row in input_file:
    
    if row['pass'] == '0':
        continue
    blockId = row['blockId']
    building_info = {
        "blockId": blockId,
        "ft": row['ft'],
        "StructureCost": float(row['StructureCost']),
        "ContentCost": float(row['ContentCost']),
        "structure_damage_curve": int(row['BDDF_ID']),
        "content_damage_curve": int(row['CDDF_ID']),
        "wp": np.array(percentagesDict[blockId]),
    }
    damages = calculate_structure_damage(building_info)

    results['unscaled']['Nick']['st'].append(
        damages['st_unscaled_by_wp'][int(row["element"])])
    results['unscaled']['Nick']['ct'].append(
        damages['ct_unscaled_by_wp'][int(row["element"])])
    results['scaled']['Nick']['st'].append(
        damages['st_scaled_by_wp'][int(row["element"])])
    results['scaled']['Nick']['ct'].append(
        damages['ct_scaled_by_wp'][int(row["element"])])

    scale_factor = float(damages['wp'][int(row["element"])]) / 100
    results['unscaled']['FAST']['ct'].append(float(row['FAST_content_loss']))
    results['scaled']['FAST']['ct'].append(
        float(row['FAST_content_loss']) * scale_factor)
    results['scaled']['FAST']['st'].append(
        float(row['FAST_bldg_loss']) * scale_factor)
    results['unscaled']['FAST']['st'].append(float(row['FAST_bldg_loss']))



scaledornot='unscaled'
x = results[scaledornot]['Nick']['st']
y = results[scaledornot]['FAST']['st']
x_content = results[scaledornot]['Nick']['ct']
y_content = results[scaledornot]['FAST']['ct']

with open("x.txt", "wb") as fp:
    pickle.dump(x, fp)
with open("y.txt", "wb") as fp:
    pickle.dump(y, fp)

with open("x_content.txt", "wb") as fp:
    pickle.dump(x_content, fp)
with open("y_content.txt", "wb") as fp:
    pickle.dump(y_content, fp)