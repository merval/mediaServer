import os
import datetime
from sqlalchemy.orm import sessionmaker
from models import Base, MediaFile
from sqlalchemy import create_engine
import subprocess
import json

MEDIA_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mp3'}

engine = create_engine('sqlite:///media_library.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def scan_media(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in MEDIA_EXTENSIONS:
                full_path = os.path.join(root, file)
                stat = os.stat(full_path)
                file_size = stat.st_size
                last_modified = datetime.datetime.fromtimestamp(stat.st_mtime)
                duration = get_media_duration(full_path)

                # Check if already in DB
                existing = session.query(MediaFile).filter_by(file_path=full_path).first()
                if existing:
                    continue  # Skip already indexed

                media = MediaFile(
                    title=os.path.splitext(file)[0],
                    file_path=full_path,
                    file_size=file_size,
                    last_modified=last_modified,
                    media_type=guess_media_type(full_path),
                    duration=duration
                )
                session.add(media)

    session.commit()

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
            '-select_streams', 'v:0',  # video stream only
            '-show_entries', 'format=duration',
            '-of', 'json',
            file_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            return None

        output = json.loads(result.stdout)
        duration = float(output['format']['duration'])
        return duration  # duration in seconds

    except Exception as e:
        print(f"Error getting duration for {file_path}: {e}")
        return None
