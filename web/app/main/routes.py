import pandas as pd
from pathlib import Path

import os
import logging
LOGGINGLEVEL = os.environ.get('LOGGINGLEVEL', 'WARNING')
logging.basicConfig(level=LOGGINGLEVEL, format=' %(asctime)s - %(levelname)s - %(message)s')

base_path = Path(__file__).parent
file_path = (
    base_path / "../static/csv/SECan_R2-recurrence-April-2019-RR.csv"
).resolve()
eq_zones = pd.read_csv(file_path, engine="python").set_index("SRC_NAME")


zone_names = {
    "ADR2    - NORTHERN ADIRONDACKS": "Northern Adirondacks",
    "AOB2   - ATLANTIC OFFSHORE BACKGROUND (R2 model)": "Atlantic Offshore Background",
    "CMF2    - COASTAL MAINE FUNDY": "Coastal Maine Fundy",
    "COC2    - COCHRANE": "Cochrane",
    "ECM - EASTERN CONTINENTAL MARGIN": "Eastern Continental Margin",
    "GAT2    - GATINEAU": "Gatineau",
    "IRB2    - Iapetan Rift Background": "Iapetan Rift Background",
    "IRM2    - Iapetan Rift Margin": "Iapetan Rift Margin",
    "JMS    - JAMES BAY": "James Bay",
    "LAB2    - SOUTHERN LABRADOR": "Southern Labrador",
    "LFN    - LAURENTIAN FAN": "Laurentian Fan",
    "NAI2    - NORTHERN APPALACHIANS INTERIOR": "Northern Appalachians Interior",
    "OBG2   - ONTARIO BACKGROUND (R MODEL)": "Ontario Background",
    "SGL2    - SOUTHERN GREAT LAKES": "Southern Great Lakes",
    "SVH    - SEVERN HIGHLANDS": "Seven Highlands",
    "SCCECR Stable Cratonic Core Eastern Canada R  (area 4.8407M km^2) simplified magnitude recurrence pa": "Stable Cratonic Core Eastern Canada",
    "SCCERGSP Stable Cratonic Core Eastern Gulf of St Lawrence PEI (area 0.0649M km^2) simplified magnitu": "Stable Cratonic Core Eastern Gulf of St Lawrence PEI",
}

import functools
import os
from flask import (
    render_template,
    current_app,
    g,
    flash,
    redirect,
    url_for,
    request,
    session,
    current_app,
    send_from_directory,
)

from app.db import get_db
from app.main import bp


def login_required(view):
    """View decorator that redirects anonymous users to the login page."""

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("main.login", next=request.path.replace('/','')))

        return view(**kwargs)

    return wrapped_view



@bp.route("/form/<hazard>")
def generate_form(hazard):

    form_data = {
        "x": str(round(float(request.args.get("x")), 3)),
        "y": str(round(float(request.args.get("y")), 3)),
    }

    if hazard.lower() == "flood":
        return render_template("flood/form.html", form_data=form_data)

    if hazard.lower() == "seismic" or hazard.lower() == "seisme":
        if request.args.get("mw") is not None:
            form_data.update(
                {
                    "depth": str(request.args.get("depth_df")),
                    "long": str(request.args.get("longitude")),
                    "lat": str(request.args.get("latitude")),
                    "mag": str(request.args.get("mw")),
                    "day": str(request.args.get("day")),
                    "month": str(request.args.get("month")),
                    "year": str(request.args.get("year")),
                    "historical_earthquake": "true",
                }
            )
            form_data["mag_rounded"] = round(float(form_data["mag"]) * 4) / 4
            form_data["depth_rounded"] = 5 * round(float(form_data["depth"]) / 5)
        if request.args.get("src_name") is not None:
            zone = request.args.get("src_name")
            frequency_values = eq_zones.loc[zone].values

            risk_profile = {}

            magnitude = 5.00
            for frequency in frequency_values:
                if frequency < 10:
                    risk_profile[
                        "{:.2f}".format(magnitude)
                    ] = "High (>10% probability per year)"
                elif frequency > 10 and frequency < 100:
                    risk_profile[
                        "{:.2f}".format(magnitude)
                    ] = "Moderate (1-10% probability per year)"
                elif frequency > 100 and frequency < 1000:
                    risk_profile[
                        "{:.2f}".format(magnitude)
                    ] = "Low (0.1-1% probability per year)"
                else:
                    risk_profile[
                        "{:.2f}".format(magnitude)
                    ] = "Very low (<0.1% probability per year)"
                magnitude += 0.25
                magnitude = float(format(magnitude, ".2f"))

            form_data.update(
                {
                    "src_name": zone_names[str(request.args.get("src_name"))],
                    "seismic_zone": "true",
                    "risk_profile": risk_profile,
                }
            )

        return render_template("seismic/form.html", form_data=form_data)



@bp.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html", title="ER2")


@bp.route("/gettext", methods=["GET"])
def get_text():
    hazard = request.args.get('hazard')
    text_requested = request.args.get('text_requested')
    return render_template("{hazard}/get-text.html".format(hazard=hazard), text_requested=text_requested)


@bp.route("/earthquake")
@login_required
def earthquake():
    session["language"] = "en"
    title = "ER2 Earthquake"
    return render_template(
        "risk.html",
        title=title,
        module="seismic",
        lang=session["language"],
    )


@bp.route("/seisme")
@login_required
def seisme():
    session["language"] = "fr"
    title = "ER2 Seisme"
    return render_template(
        "risk.html",
        title=title,
        module="seismic",
        lang=session["language"],
    )


@bp.route("/inondation")
@login_required
def inondation():
    title = "ER2 Inondation"
    session["language"] = "fr"
    return render_template(
        "risk.html",
        title=title,
        lang=session["language"],
        module="flood",
    )

@bp.route("/flood")
@login_required
def flood():
    session["language"] = "en"
    title = "ER2 Flood"
    next_url = url_for('main.flood')
    return render_template(
        "risk.html", title=title, lang=session["language"], module="flood", next_url=next_url
    )


@bp.route("/togglelanguage")
def set_language():

    redirect_link = request.referrer
    if session["language"] == "fr":
        session["language"] = "en"
        redirect_link = redirect_link.replace("inondation", "flood")
        redirect_link = redirect_link.replace("seisme", "earthquake")
    else:
        session["language"] = "fr"
        redirect_link = redirect_link.replace("flood", "inondation")
        redirect_link = redirect_link.replace("earthquake", "seisme")

    return redirect(redirect_link)


@bp.route("/feedback")
@login_required
def feedback():
    return redirect("http://www.google.com", code=302)