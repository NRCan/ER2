import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config(object):
    """Base config"""
    SECRET_KEY = os.environ.get("SECRET_KEY")
    LANGUAGES = ["en", "fr"]
    FLOOD_MAP_SERVICE = os.environ.get("FLOOD_MAP_SERVICE")
    EQ_MAP_SERVICE = os.environ.get("EQ_MAP_SERVICE")
    MAPSERV_URL = os.environ.get("MAPSERV_URL")
    ER2_API=os.environ.get("ER2_API")
    TIFF_VALUE_URL=os.environ.get("TIFF_VALUE_URL")
    FLASK_ENV=os.environ.get("FLASK_ENV")
    DEBUG=os.environ.get("DEBUG")
    LOGGINGLEVEL=os.environ.get("LOGGINGLEVEL")
    REGISTER_SECURITY_KEY=os.environ.get("REGISTER_SECURITY_KEY")