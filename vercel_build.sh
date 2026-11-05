#!/bin/bash
set -e # Stop on any error

echo "Building project packages..."
# --break-system-packages: Vercel's build image's Python is managed by uv
# (PEP 668), which blocks a bare `pip install` outside a virtualenv. This
# build container is thrown away after the build step, so there's no real
# "system" to protect here.
python3 -m pip install --break-system-packages -r requirements.txt

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