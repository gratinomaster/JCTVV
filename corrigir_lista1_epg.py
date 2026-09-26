#!/usr/bin/env python3
"""Corrige o lista1.m3u: header url-tvg e tvg-ids validos contra as 3 fontes EPG."""
import datetime
import os
import re
import shutil
import ssl
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

M3U = "lista1.m3u"
BASE = "https://github.com/limaalef/BrazilTVEPG/raw/refs/heads/main/"
EPG_URLS = [BASE + "globo.xml", BASE + "claro.xml", BASE + "vivoplay.xml"]
CACHE = "/tmp/opencode/epg_cache"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
