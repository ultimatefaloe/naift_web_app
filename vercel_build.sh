#!/bin/bash
set -e # Stop on any error

echo "Building project packages..."
python3 -m pip install -r requirements.txt

echo "Installing tailwindcss and dependencies..."
python3 manage.py tailwind install

echo "Building tailwindcss..."
python3 manage.py tailwind build

echo "Collecting static files..."
# --upload-unhashed-files: django-cloudinary-storage's own collectstatic
# override otherwise skips plain file copies entirely unless STATICFILES
# storage is StaticCloudinaryStorage (we deliberately keep static files on
# the filesystem and only route MEDIA uploads through Cloudinary).
python3 manage.py collectstatic --noinput --upload-unhashed-files

echo "Build process completed!"