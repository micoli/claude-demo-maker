# Docker

Docker sert à la synthèse vocale Kokoro. Démarre Docker avant de lancer une narration à partir d'un texte. Les scripts démarrent le conteneur `kokoro-demo-maker` à partir de l'image `ghcr.io/remsky/kokoro-fastapi-cpu:v0.10.0` si le service est indisponible sur `127.0.0.1:8880`.

Le rendu Blender s'exécute sur la machine hôte. Suis les [instructions d'installation des outils de rendu](../README.md#installer-les-dépendances-de-rendu).
