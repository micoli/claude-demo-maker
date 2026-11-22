# Render toolchain for avatar-narrator and demo-maker: Node, Blender (Eevee on Mesa), FFmpeg, Rhubarb, Pillow.
# Blender and Rhubarb only ship Linux x64 builds, so the image is pinned to amd64 (emulated on Apple Silicon).
FROM --platform=linux/amd64 node:22-bookworm-slim

ARG BLENDER_VERSION=5.2.2
ARG RHUBARB_VERSION=1.14.0

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip xz-utils \
      ffmpeg python3 python3-pil fonts-liberation \
      xvfb xauth libgl1 libegl1 libgl1-mesa-dri libglu1-mesa \
      libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libx11-6 libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
      | tar -xJ -C /opt \
    && mv "/opt/blender-${BLENDER_VERSION}-linux-x64" /opt/blender

RUN curl -fsSL -o /tmp/rhubarb.zip \
      "https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v${RHUBARB_VERSION}/Rhubarb-Lip-Sync-${RHUBARB_VERSION}-Linux.zip" \
    && unzip -q /tmp/rhubarb.zip -d /opt \
    && mv "/opt/Rhubarb-Lip-Sync-${RHUBARB_VERSION}-Linux" /opt/rhubarb \
    && chmod +x /opt/rhubarb/rhubarb \
    && rm /tmp/rhubarb.zip

COPY docker/render/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV BLENDER_EXE=/opt/blender/blender \
    RHUBARB_BIN=/opt/rhubarb/rhubarb \
    AVATAR_FONT=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf \
    LIBGL_ALWAYS_SOFTWARE=1

# The repository is mounted at /work: scripts resolve .scratch/ relative to their own location.
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["node", "--version"]
