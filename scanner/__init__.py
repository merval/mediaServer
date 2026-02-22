import datetime
import json
import os
import subprocess

from config import ENGINE, SCANNER_MEDIA_ROOT, SessionLocal
from models import Base, MediaFile

MEDIA_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mp3'}

Base.metadata.create_all(ENGINE)


def scan_media(directory=SCANNER_MEDIA_ROOT):
    session = SessionLocal()
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in MEDIA_EXTENSIONS:
                    full_path = os.path.join(root, file)
                    stat = os.stat(full_path)
                    file_size = stat.st_size
                    last_modified = datetime.datetime.fromtimestamp(stat.st_mtime)
                    duration = get_media_duration(full_path)

                    existing = session.query(MediaFile).filter_by(file_path=full_path).first()
                    if existing:
                        continue

                    media = MediaFile(
                        title=os.path.splitext(file)[0],
                        file_path=full_path,
                        file_size=file_size,
                        last_modified=last_modified,
                        media_type=guess_media_type(full_path),
                        duration=duration,
                    )
                    session.add(media)

        session.commit()
    finally:
        session.close()


def guess_media_type(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in {'.mp4', '.mkv', '.avi'}:
        return 'movie'
    elif ext in {'.mp3'}:
        return 'music'
    return 'unknown'


def get_media_duration(file_path):
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'format=duration',
            '-of', 'json',
            file_path,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            return None

        output = json.loads(result.stdout)
        duration = float(output['format']['duration'])
        return duration

    except Exception as e:
        print(f"Error getting duration for {file_path}: {e}")
        return None
