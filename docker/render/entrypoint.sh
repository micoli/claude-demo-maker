#!/bin/sh
# Blender's Eevee needs a GL context even in background mode: provide a virtual display.
Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp >/dev/null 2>&1 &
export DISPLAY=:99
for _ in $(seq 1 50); do
  [ -e /tmp/.X11-unix/X99 ] && break
  sleep 0.2
done
exec "$@"
