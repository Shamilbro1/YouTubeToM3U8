#!/usr/bin/python3

import os
import sys
import yt_dlp
from datetime import datetime, timedelta

import pytz
from lxml import etree


tz = pytz.timezone("Europe/London")
channels = []


def generate_times(curr_dt: datetime):
    last_hour = curr_dt.replace(
        microsecond=0,
        second=0,
        minute=0
    )

    last_hour = tz.localize(last_hour)

    start_dates = [last_hour]

    for _ in range(7):
        last_hour += timedelta(hours=3)
        start_dates.append(last_hour)

    end_dates = start_dates[1:]
    end_dates.append(start_dates[-1] + timedelta(hours=3))

    return start_dates, end_dates


def build_xml_tv(streams: list) -> bytes:

    data = etree.Element("tv")

    data.set(
        "generator-info-name",
        "youtube-live-epg"
    )

    data.set(
        "generator-info-url",
        "https://github.com/dp247/YouTubeToM3U8"
    )

    for stream in streams:

        channel = etree.SubElement(
            data,
            "channel"
        )

        channel.set(
            "id",
            stream[1]
        )

        name = etree.SubElement(
            channel,
            "display-name"
        )

        name.set(
            "lang",
            "en"
        )

        name.text = stream[0]

        dt_format = "%Y%m%d%H%M%S %z"

        start_dates, end_dates = generate_times(
            datetime.now()
        )

        for idx, val in enumerate(start_dates):

            programme = etree.SubElement(
                data,
                "programme"
            )

            programme.set(
                "channel",
                stream[1]
            )

            programme.set(
                "start",
                val.strftime(dt_format)
            )

            programme.set(
                "stop",
                end_dates[idx].strftime(dt_format)
            )

            title = etree.SubElement(
                programme,
                "title"
            )

            title.set(
                "lang",
                "en"
            )

            title.text = (
                stream[3]
                if stream[3]
                else f"LIVE: {stream[0]}"
            )

            description = etree.SubElement(
                programme,
                "desc"
            )

            description.set(
                "lang",
                "en"
            )

            description.text = (
                stream[4]
                if stream[4]
                else "No description provided"
            )

            icon = etree.SubElement(
                programme,
                "icon"
            )

            icon.set(
                "src",
                stream[5]
            )

    return etree.tostring(
        data,
        pretty_print=True,
        encoding="utf-8"
    )


def grab(url: str):

    global channels

    if "&" in url:
        url = url.split("&")[0]

    print(
        f"# Getting YouTube stream: {url}",
        file=sys.stderr
    )

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,

        # We need HLS / M3U8.
        "format": (
            "best[protocol^=m3u8]"
            "/best[protocol=m3u8_native]"
            "/best"
        ),

        # Try clients that can expose live formats.
        "extractor_args": {
            "youtube": {
                "player_client": [
                    "android",
                    "web"
                ]
            }
        },
    }

    try:

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        if not info:
            print(
                "ERROR: yt-dlp returned no information",
                file=sys.stderr
            )
            return

        title = (
            info.get("title")
            or channel_name
        )

        description = (
            info.get("description")
            or ""
        )

        thumbnail = (
            info.get("thumbnail")
            or ""
        )

        formats = info.get("formats") or []

        # Find HLS formats first.
        hls_formats = [
            f
            for f in formats
            if f.get("protocol") in (
                "m3u8",
                "m3u8_native"
            )
            and f.get("url")
        ]

        # Prefer formats containing both video and audio.
        combined = [
            f
            for f in hls_formats
            if f.get("vcodec") not in (
                None,
                "none"
            )
            and f.get("acodec") not in (
                None,
                "none"
            )
        ]

        if combined:
            selected = max(
                combined,
                key=lambda f: (
                    f.get("height") or 0,
                    f.get("tbr") or 0
                )
            )

        elif hls_formats:
            selected = max(
                hls_formats,
                key=lambda f: (
                    f.get("height") or 0,
                    f.get("tbr") or 0
                )
            )

        else:
            # Last fallback: use yt-dlp's selected format.
            selected = None

            selected_url = info.get("url")

            if not selected_url:
                print(
                    "ERROR: No playable stream URL found",
                    file=sys.stderr
                )
                return

        if selected:
            stream_url = selected.get("url")

        else:
            stream_url = selected_url

        if not stream_url:
            print(
                "ERROR: Empty stream URL",
                file=sys.stderr
            )
            return

        # Make sure we actually received an HLS URL.
        if ".m3u8" not in stream_url:
            print(
                "WARNING: yt-dlp returned a non-M3U8 URL",
                file=sys.stderr
            )

        channels.append(
            (
                channel_name,
                channel_id,
                category,
                title,
                description,
                thumbnail
            )
        )

        print(
            stream_url
        )

    except Exception as e:

        print(
            f"ERROR: yt-dlp failed: {e}",
            file=sys.stderr
        )


channel_name = ""
channel_id = ""
category = ""


# Read youtubeLink.txt
with open(
    "./youtubeLink.txt",
    encoding="utf-8"
) as f:

    print("#EXTM3U")

    for line in f:

        line = line.strip()

        if not line:
            continue

        if line.startswith("##"):
            continue

        if not line.startswith("https:"):

            parts = line.split("||")

            if len(parts) < 3:
                print(
                    f"ERROR: Invalid channel line: {line}",
                    file=sys.stderr
                )
                continue

            channel_name = parts[0].strip()
            channel_id = parts[1].strip()
            category = parts[2].strip().title()

            print(
                f'\n#EXTINF:-1 '
                f'tvg-id="{channel_id}" '
                f'tvg-name="{channel_name}" '
                f'group-title="{category}",'
                f'{channel_name}'
            )

        else:

            grab(line)


# Build EPG
channel_xml = build_xml_tv(channels)

with open(
    "epg.xml",
    "wb"
) as f:

    f.write(channel_xml)


# Remove temporary files
if "temp.txt" in os.listdir():

    os.system("rm -f temp.txt")

os.system("rm -f watch*")
