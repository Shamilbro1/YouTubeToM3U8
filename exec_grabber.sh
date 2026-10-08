#!/bin/bash
set -e

python3 -m pip install -r requirements.txt

python3 YouTubeLinkGrabber.py > ./youtube.m3u8

echo "M3U update complete."
