# Music Assistant

[![latest version](https://img.shields.io/github/release/music-assistant/hass-music-assistant?display_name=tag&include_prereleases&label=latest%20version)](https://github.com/music-assistant/hass-music-assistant/releases) 
[![discord](https://img.shields.io/discord/753947050995089438?label=Chat&logo=discord)](https://discord.gg/kaVm8hGpne) 
[![hacs](https://img.shields.io/badge/HACS-Default-41BDF5?label=HACS)](https://github.com/hacs/integration) 
[![sponsor](https://img.shields.io/github/sponsors/music-assistant?label=sponsors)](https://github.com/sponsors/music-assistant)



Turn your Home Assistant instance into a jukebox, hassle free streaming of your favourite media to Home Assistant media players.


## Introduction

Music Assistant is a music library manager for your offline and online music sources, combined with the power of Home Assistant to easily stream your favourite music to a wide range of supported players.

Music Assistant consists of multiple building blocks:

- Music Assistant integration in Home Assistant - the core part that runs the Music Assistant engine and keeps track of your Music sources.
- Import Home Assistant media players into the Music Assistant engine to use as target for playback.
- Optionally export Music Assistant media players back to Home Assistant (for rich metadata etc.)
- Music Assistant 'Media Source' integration, allows browsing of your favourite media from Home Assistant's 'Media' panel.
- Music Assistant panel: A rich user interface with more advanced features than the standard Media panel.

---

### Features

- Supports multiple music sources through a provider implementation.
- Currently implemented music providers are Spotify, Qobuz, Tune-In Radio and local filesystem.
- More music providers can be easily added, soon available: Tidal and Deezer.
- Auto matches music on different providers (track linking).
- Fetches metadata for extended artist information.
- Keeps track of the entire music library in a compact database
- All media players available in Home Assistant that support streaming from an url are supported, which is basically almost all targets.
- Gapless, crossfade and volume normalization support for all players.
- Truly hassle free streaming of your favourite music to players, no advanced knowledge required.
- Rich User interface (Progressive Web App) hosted as panel directly in the Home Assistant user interface.

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

## Installation & initial configuration

- Make sure that you have the [Home Assistant Community Store](https://hacs.xyz/) installed.
- In the HACS panel, go to integrations.
- Search for `Music Assistant` and click `Download this repository with HACS`
- Restart Home Assistant.
- Go to Configuration -> Integrations and click the big `+` button.
- Look for Music Assistant and click to add it.
- If Home Assistant does not show, refresh your brower (cache).
- Follow the steps for initial configuration, like what players you want to use and music providers.
- The Music Assistant integration is ready for use.
- You can find the panel in the menu on the left for the rich user interface or use the default Home Assistant Media panel to quickly browse your music.
- All configuration options can be adjusted later with the `configure` button on the integration's card.
- To change the name of the panel, simply rename the integration from the integrations page.

## Usage and notes

- Music from your music sources will be automatically loaded into the Music Assistant library. If you have multiple sources, they will be merged as one library.
- In this first implementation there's only support for "Library items", so your favourited artists, albums and playlists. In a later release we'll provide options to browse the recommendations of the various streaming providers.
- Items on disk are not favourited by default. You can see all items if you deselect the "in library" filter (the heart) and decide for yourself what you want in your favourites.
- Note that at the first startup it can take a while before data is available (first sync), the Music Assistant UI will notify you about tasks that are in progress.
- Music sources are synced at integration (re)load and every 3 hours.
- If a song is available on multiple providers (e.g. Spotify and a flac file on disk), the file/stream with the highest quality is always preferred when starting a stream.
- Music Assistant uses a custom stream port (TCP 8095 by default) to stream audio to players. Players must be able to reach the Home Assistant instance and this port. If you're running one of the recommended Home Assistant installation methods, this is all handled for you, otherwise you will have to make sure you're running HA in HOST network mode. Note: If the default port 8095 is occupied, the next port will be tried, and so on.

## Spotify, Youtube Music and Tune-In Radio specific notes

- When using Spotify or Youtube Music as a music source please note that **only Premium accounts** are supported, free accounts will not work.
- For Tune-In radio, make sure to fill in your username and not your email address. Be aware that only favourites in your Tune-In library will be visible in Music Assistant.

## File System specific notes

- When using the file system provider, make sure that your audio files can be reached from Home Assistant, for example /media/music. 
- There is not (yet) direct support for remote file locations such as SMB, cloud drives etc however SMB shares can be mounted via the OS and then will be accessible. See here for the details https://github.com/music-assistant/hass-music-assistant/discussions/452
- It is very important that all of your audio files contain proper ID3 tag information. The more comprehensive the tagging the better the results will be when using MA. For this reason it is strongly recommended that all files are tagged with MusicBrainz Picard. It is also important that the audio files are stored in a folder structure that is typical of other audio library applications. To minimise the chance of problems with MA you should follow the Kodi guidelines here https://kodi.wiki/view/Music_tagging Just about all the tips, tricks and suggestions on that page are applicable to MA and if you follow it all to the letter you will have a much better experience.
- If you have local artwork then it is important that album names match exactly the tagged album name except characters that are not allowed in folder names are not parsed. Therefore, "The Big Chill: Soundtrack" will match "The Big Chill Soundtrack" but "Vika and Linda" will not match "Vika & Linda"

## Supported Media players

In theory every Home Assistant media player that accepts "play from url" should be supported.
In reality this is a bit more difficult because not every media player integration has implemented the play_media service the same way.
In some cases it just works out of the box and in some cases it will need a few code workarounds to get it going. Media players that do not support 'play by url' will not/never work. See the below table for confirmed working media player integrations. Please report if you find a player not on the list and either work with us to get it compatible or report that you've tested it and it works ;-)

### Confirmed working

- [Google Cast players](https://www.home-assistant.io/integrations/cast/)
- [Slimproto Squeezebox players](https://www.home-assistant.io/integrations/slimproto/)
- [Sonos](https://www.home-assistant.io/integrations/sonos/)
- [Linkplay](https://github.com/nagyrobi/home-assistant-custom-components-linkplay)
- [Bose Soundtouch](https://www.home-assistant.io/integrations/soundtouch/)
- [All players supporting DLNA](https://www.home-assistant.io/integrations/dlna_dmr/)

### Confirmed NOT working (or under investigation)

- Alexa / Amazon Echo devices, see here: https://github.com/music-assistant/hass-music-assistant/issues/101
- Apple TV / Homepod / Airplay, see feature request here: https://github.com/music-assistant/hass-music-assistant/discussions/438
- [Kodi/OSMC](https://www.home-assistant.io/integrations/kodi/), issues reported, [see here](https://github.com/music-assistant/hass-music-assistant/issues/358)

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
- Just like [Erik](https://github.com/erkr) help out as a moderator on discord and Github with the load of incoming reports, request and questions. Thanks Erik!
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
