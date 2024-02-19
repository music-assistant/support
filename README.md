# Music Assistant

[![latest version](https://img.shields.io/github/release/music-assistant/hass-music-assistant?display_name=tag&include_prereleases&label=latest%20version)](https://github.com/music-assistant/hass-music-assistant/releases)
[![discord](https://img.shields.io/discord/753947050995089438?label=Chat&logo=discord)](https://discord.gg/kaVm8hGpne)
[![hacs](https://img.shields.io/badge/HACS-Default-41BDF5?label=HACS)](https://github.com/hacs/integration)
[![sponsor](https://img.shields.io/github/sponsors/music-assistant?label=sponsors)](https://github.com/sponsors/music-assistant)



Turn your Home Assistant instance into a jukebox, hassle free streaming of your favourite media to Home Assistant media players.

## Introduction

Music Assistant is a music library manager for your offline and online music sources, combined with the power of Home Assistant to easily stream your favourite music to a wide range of supported players.

Music Assistant consists of multiple building blocks:

- Music Assistant Server (2.0):  the core part that runs the Music Assistant engine and keeps track of your Music sources. This will be installed automatically as an addon in HAOS when installing the Integration. Alternatively, you can manually install the addon in HAOS or install the server in a separate docker container.
- Music Assistant integration for Home Assistant: Connects Home Assistant to your Music Assistant Server to automate your music!
- Home Assistant Plugin for Music Assistant: Import Home Assistant media players into the Music Assistant engine to use as targets for playback.

---

### Documentation

See here https://music-assistant.io

## Installation of the Music Assistant Server

MA requires a 64bit Operating System and a minimum of 2GB of RAM on the physical device or the container (physical devices are recommended to have 4GB+ if they are running anything else)

Installation instructions are here https://music-assistant.io/installation/

## Installation of the Home Assistant integration

See here https://music-assistant.io/integration/installation/

## OpenAI features

During [Chapter 5 of "Year of the Voice"](https://www.youtube.com/live/djEkgoS5dDQ?si=pt8-qYH3PTpsnOq9&t=3699), [JLo](https://blog.jlpouffier.fr/chatgpt-powered-music-search-engine-on-a-local-voice-assistant/) showed something he had been working on to use the OpenAI integration along with Music Assistant. We now have this feature baked in to the integration code directly, although some extra setup is still required.

See the instructions here https://music-assistant.io/integration/installation/#openai-features

## I need help, I have feedback

- [Documentation](https://music-assistant.io)
- [Issue tracker](https://github.com/music-assistant/hass-music-assistant/issues) to create bug reports, please include detailed info and logfiles. Please check if your issue has already been reported.
- [Feature requests](https://github.com/music-assistant/hass-music-assistant/discussions/categories/feature-requests-and-ideas): Give your vote to an existing request, join the discussion or add a new request.
- [Q&A section](https://github.com/music-assistant/hass-music-assistant/discussions/categories/q-a-faq) Frequently asked questions and tutorials
- [Discord community](https://discord.gg/kaVm8hGpne) Join the community and get support!

## I want to help

See here https://music-assistant.io/help/
