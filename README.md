# Music Assistant

Turn your Home Assistant instance into a jukebox, hassle free streaming of your favorite media to Home Assistant media players.

## Introduction

Music Assistant is a music library manager for your offline and online music sources, combined with the power of Home assistant to easily stream your favourite music to a wide range of supported players.

Music Assistant consists of multiple building blocks:

- Music Assistant integration in Home Assistant - the core part that runs the Music Assistant engine and keeps track of your Music sources.
- Import Home Assistant media players into the Music Assistant engine to use as target for playback.
- Optionally export Music Assistant media players back to Home Assistant (for rich metadata etc.)
- Music Assistant 'Media Source' integration, allows browsing of your favorite media from Home Assistant's 'Media' panel.
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
- Truly hassle free streaming of your favorite music to players, no advanced knowledge required.
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

## Installation

In the HACS panel, go to integrations and click the big orange '+' button. Search for 'Music Assistant' and click \'Install this repository in HACS'.

### Using HACS

- In the HACS panel, go to integrations.
- Search for `Music Assistant` and click `Download this repository with HACS`
- Restart HA to load the integration into HA.

### Manually (not recommended)

- Download the [latest release](https://github.com/music-assistant/hass-music-assistant/releases) as a **zip file** and extract it into the `custom_components` folder in your HA installation.</li>
- Restart HA to load the integration into HA.

## Configuration

- Go to Configuration -> Integrations and click the big `+` button.
- Look for Music Assistant and click to add it.
- Follow the steps for initial configuration.
- The Music Assistant integration is ready for use.
- You can find the panel in the menu on the left for the rich user interface or use the default Home Assistant Media panel to quickly browse your music.
- All configuration options can be adjusted later with the `configure` button on the integration's card.
- To change the name of the panel, simply rename the integration from the integrations page.

## Usage and notes

- Music from your music sources will be automatically loaded into the Music Assistant library. If you have multiple sources, they will be merged as one library.
- In this first implementation there's only support for "Library items", so your favourited artists, albums and playlists. In a later release we'll provide options to browse the recommendations of the various streaming providers.
- Note that at the first startup it can take a while before data is available (first sync), the Music Assistant UI will notify you about tasks being in progress.
- Music sources are synced at integration (re)load and every 3 hours.
- If a song is available on multiple providers (e.g. Spotify and a flac file on disk), the file/stream with the highest quality is always preferred when starting a stream.
- While Music Assistant is built entirely in python, it requires the SoX and/or ffmpeg binaries to be present on your OS distribution for the audio processing. If will default to SoX if present but fallback to ffmpeg (which is installed by default on Home Assistant installations).

## Music provider specific notes

- When using Spotify as music source please note that **only Spotify Premium accounts** are supported, free accounts will not work.
- Tune-In Radio will only show your favourited items in the library.
- When using the file system provider, make sure that your audio files contain proper ID3 tag information.
