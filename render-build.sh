#!/usr/bin/env bash
set -e

echo "=== Installing dependencies for Render ==="
STORAGE_DIR=/opt/render/project/.render

if [[ ! -d $STORAGE_DIR/chrome ]]; then
  echo "...Downloading Chrome for Render..."
  mkdir -p $STORAGE_DIR/chrome
  cd $STORAGE_DIR/chrome
  wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  dpkg -x google-chrome-stable_current_amd64.deb $STORAGE_DIR/chrome
  rm -f google-chrome-stable_current_amd64.deb
  cd /opt/render/project/src || true
else
  echo "...Using Chrome from cache..."
fi

export PATH="${STORAGE_DIR}/chrome/opt/google/chrome:${PATH}"

pip install --upgrade pip
pip install -r requirements.txt
