"""A script to continuously poll Blink for a video created in the last 60
seconds (OFFSET_SECONDS). Once found, the video is downloaded and sent as an
iOS notification using the Home Assitant API.

This script relises on the following entries in the secrets.yaml file.

    blinkHassApiBaseURL - e.g. "https://www.myhass.com:8123"
    blinkHassApiToken - a Home Assistant long live access token.
    blinkUsername - Your Blink username
    blinkPassword - Your blink password

The SAVE_PATH and SECRETS_FILE constants below may also need to be changed
depending on the setup.
"""
import json
import os
import time
from datetime import datetime, timedelta

from requests import post

import yaml
from blinkpy import api, blinkpy

SAVE_PATH = "/config/www"
SECRETS_FILE = "/config/secrets.yaml"

VIDEO_FILENAME = "BlinkVideo.mp4"
IMAGE_FILENAME = "BlinkImage.png"
OFFSET_SECONDS = 3660  # Currently offset by 1hr 1m due to daylight savings.
TIMEOUT_SECONDS = 60
NOTIFY_ENTITY_NAMES = ["ios_adams_iphone", "ios_leannes_iphone"]

VIDEO_FILE = os.path.join(SAVE_PATH, VIDEO_FILENAME)
IMAGE_FILE = os.path.join(SAVE_PATH, IMAGE_FILENAME)

with open(SECRETS_FILE, "r") as secrets_file:
    secrets = yaml.load(secrets_file)

blink = blinkpy.Blink(
    username=secrets["blinkUsername"], password=secrets["blinkPassword"]
)
blink.start()

from_time = time.time() - OFFSET_SECONDS
loop_start = datetime.today()
while True:
    videos = api.request_videos(blink, from_time)["videos"]

    if len(videos) >= 1:
        break

    if datetime.today() >= (loop_start + timedelta(seconds=TIMEOUT_SECONDS)):
        break

    time.sleep(1)

if len(videos) >= 1:
    video = videos[0]  # Use the first video in the list.
    video_address = "{}{}".format(blink.urls.base_url, video["address"])

    response = api.http_get(blink, url=video_address, stream=True, json=False)

    with open(VIDEO_FILE, "wb") as video_file_content:
        video_file_content.write(response.content)

    # Extract a still image from the frame at 4s and save that to disk
    os.system(
        "ffmpeg -y -ss 00:00:04 -i {} -vf 'crop=720:720:280:0' -vframes 1 -vcodec png {}".format(
            VIDEO_FILE, IMAGE_FILE
        )
    )

    # Build the notification data
    data = {
        "message": "Doorbell",
        "data": {
            "attachment": {
                "url": "{}/local/{}?1=1".format(
                    secrets["blinkHassApiBaseURL"], VIDEO_FILENAME
                ),
                "content-type": "mp4",
            }
        },
    }
else:
    # If we don"t have a video, just send a message.
    data = {"message": "Doorbell"}

# Send the notification(s)
header = {
    "content-type": "application/json",
    "Authorization": "Bearer {}".format(secrets["blinkHassApiToken"]),
}

for entity_name in NOTIFY_ENTITY_NAMES:
    post(
        "{}/api/services/notify/{}".format(
            secrets["blinkHassApiBaseURL"], entity_name
        ),
        headers=header,
        data=json.dumps(data),
    )
