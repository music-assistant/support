# Music Assistant

[![latest version](https://img.shields.io/github/release/music-assistant/hass-music-assistant?display_name=tag&include_prereleases&label=latest%20version)](https://github.com/music-assistant/hass-music-assistant/releases)
[![discord](https://img.shields.io/discord/753947050995089438?label=Chat&logo=discord)](https://discord.gg/kaVm8hGpne)
[![hacs](https://img.shields.io/badge/HACS-Default-41BDF5?label=HACS)](https://github.com/hacs/integration)
[![sponsor](https://img.shields.io/github/sponsors/music-assistant?label=sponsors)](https://github.com/sponsors/music-assistant)



Turn your Home Assistant instance into a jukebox, hassle free streaming of your favourite media to Home Assistant media players.

## Attention: Running Home Assistant 2023.3 or later?
Make sure to install the BETA version of Music Assistant (2023.6.bx). Older versions of Music Assistant are not compatible with recent Home Assistant versions. We expect to end our beta stage soon.


## Introduction

Music Assistant is a music library manager for your offline and online music sources, combined with the power of Home Assistant to easily stream your favourite music to a wide range of supported players.

Music Assistant consists of multiple building blocks:

- Music Assistant Server (2.0):  the core part that runs the Music Assistant engine and keeps track of your Music sources.
- Music Assistant integration for Home Assistant: Connects Home Assistant to your Music Assistant Server to automate your music!
- Home Assistant Plugin for Music Assistant: Import Home Assistant media players into the Music Assistant engine to use as target for playback. (available soon).

---

### Features

- Supports multiple music sources through a provider implementation.
- All popular streaming services are supported, as well as local files.
- Auto matches music on different providers (track linking).
- Fetches metadata for extended artist information.
- Keeps track of the entire music library in a compact database
- Gapless, crossfade and volume normalization support for all players.
- Truly hassle free streaming of your favourite music to players, no advanced knowledge required.
- Rich User interface (Progressive Web App) powered by VueJS 3.

---

### Preview

![Preview image](https://raw.githubusercontent.com/music-assistant/hass-music-assistant/main/screenshots/screen1.png)

<details>
<summary>Click to show more screenshots</summary>

![Preview image](https://raw.githubusercontent.com/music-assistant/hass-music-assistant/main/screenshots/screen3.png)

![Preview image](https://raw.githubusercontent.com/music-assistant/hass-music-assistant/main/screenshots/screen2.png)

![Preview image](https://raw.githubusercontent.com/music-assistant/hass-music-assistant/main/screenshots/screen4.png)

![Preview image](https://raw.githubusercontent.com/music-assistant/hass-music-assistant/main/screenshots/screen5.png)

</details>

---

## Installation of the Music Assistant Server

You need the Music Assistant Server running in your network, which is docker based so easy to deploy.
If you are running Home Assistant OS or Home Assistant supervisor, you can skip this step as the Home Assistant integration will take care of installing the Music Assistant Server for you as add-on.

[See here for manual steps how to deploy the Music Assistant Server.](https://github.com/music-assistant/server)

MA requires a 64bit Operating System and a minimum of 2GB of RAM on the physical device or the container (physical devices are recommended to have 4GB+ if they are running anything else)

## Installation of the Home Assistant (beta) integration

- Make sure that you have the [Home Assistant Community Store](https://hacs.xyz/) installed.
- Within HACS, search for `Music Assistant` and click the entry in the search results.
- Click the big (blue) button at the bottom for `Download`.
- Click the button again and in the dialog make sure `Show beta versions` is selected.
- Download the latest (beta) version
- Restart Home Assistant.
- Go to Configuration -> Integrations and click the big `+` button.
- Look for Music Assistant and click to add it.
- If Music Assistant does not show, refresh your browser (cache).
- The Music Assistant integration is ready for use.

NOTE: You need to set-up the players and music sources within Music Assistant itself.
If you are running Music Assistant in docker, you need to access the webinterface at http://youripaddress:8095, when running the Home Assistant add-on, you can access the webinterface from the add-on (and even show that in the sidebar).

## Usage and notes

- Music from your music sources will be automatically loaded into the Music Assistant library. If you have multiple sources, they will be merged as one library.
- In this first implementation there's only support for "Library items", so your favourited artists, albums and playlists. In a later release we'll provide options to browse the recommendations of the various streaming providers.
- Items on disk are not favourited by default. You can see all items if you deselect the "in library" filter (the heart) and decide for yourself what you want in your favourites.
- Note that at the first startup it can take a while before data is available (first sync), the Music Assistant UI will notify you about tasks that are in progress.
- Music sources are synced at addon (re)start and every 3 hours.
- If a song is available on multiple providers (e.g. Spotify and a flac file on disk), the file/stream with the highest quality is always preferred when starting a stream.
- Music Assistant uses a custom stream port (TCP 8095 by default) to stream audio to players. Players must be able to reach the Home Assistant instance and this port. If you're running one of the recommended Home Assistant installation methods, this is all handled for you, otherwise you will have to make sure you're running HA in HOST network mode. Note: If the default port 8095 is occupied, the next port will be tried, and so on.
- The HA integration will create new media_player entities for those player types which are supported natively by MA. To see the names of those players then go to SETTINGS>>DEVICES&SERVICES>>INTEGRATIONS>>MUSIC ASSISTANT. It is these players that need to be targeted in your automations.
- See the [GitHub discussions](https://github.com/orgs/music-assistant/discussions) area for more detailed information

## I need help, I have feedback

- [issue tracker](https://github.com/music-assistant/hass-music-assistant/issues) to create bug reports, please include detailed info and logfiles. Please check if your issue has already been reported.
- [feature requests](https://github.com/music-assistant/hass-music-assistant/discussions/categories/feature-requests-and-ideas): Give your vote to an existing request, join the discussion or add a new request.
- [Q&A section](https://github.com/music-assistant/hass-music-assistant/discussions/categories/q-a-faq) Frequently asked questions and tutorials
- [discord community](https://discord.gg/kaVm8hGpne) Join the community and get support!

## I want to help

With a large project like this, there is always enough todo. Not only with actual writing of code but also in documentation, providing support, testing etc. Ofcourse you help me out greatly by donating me a few bucks but helping out can also be done in other ways:

- If you like to help with the development, e.g. implementing a new music provider or fix a player specific quirk, please reach out to me on discord in a PM. I did not have time to write extended development docs but once you get the grasp of the structure it is relatively straight forward.
- Help others out on discord or within the discussions part of Github.
- Help out with writing documentation and HOWTO's and the FAQ's.
- Just like [erkr](https://github.com/erkr) and [OzGav](https://github.com/OzGav) help out as a moderator on discord and Github with the load of incoming reports, request and questions. Thanks guys!
- Make sure to like this project by clicking the "star" button and share it with others!

### Donations

As explained above you can also show your appreciation in all kinds of ways. Besides that donations are great for me as a small fee back for all the free time I invest in this project. For buying some test hardware and streaming provider accounts and contributions to the metadata projects.

- [Github Sponsors](https://github.com/music-assistant)
- [Buy me a Coffee](https://www.buymeacoffee.com/marcelveldt)

A really big thank you in advance from me and my family!

___________________________________________

I hope you like my little pet project I've been working on for the last 3 years.
I'm sure that together with the really great HA community we can grow this project into something really great. Thanks!

Kind regards,

Marcel
