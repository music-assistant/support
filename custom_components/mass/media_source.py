"""Media Source Implementation."""
from __future__ import annotations

import asyncio

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_TRACK,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
)
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from music_assistant import MusicAssistant
from music_assistant.models.media_items import MediaItemType

from .const import DOMAIN
from .player_controls import async_register_player_control

MEDIA_TYPE_RADIO = "radio"

PLAYABLE_MEDIA_TYPES = [
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_RADIO,
    MEDIA_TYPE_TRACK,
]

LIBRARY_ARTISTS = "artists"
LIBRARY_ALBUMS = "albums"
LIBRARY_TRACKS = "tracks"
LIBRARY_PLAYLISTS = "playlists"
LIBRARY_RADIO = "radio"


LIBRARY_TITLE_MAP = {
    # TODO: How to localize this ?
    LIBRARY_ARTISTS: "Artists",
    LIBRARY_ALBUMS: "Albums",
    LIBRARY_TRACKS: "Tracks",
    LIBRARY_PLAYLISTS: "Playlists",
    LIBRARY_RADIO: "Radio stations",
}

LIBRARY_MEDIA_CLASS_MAP = {
    LIBRARY_ARTISTS: MEDIA_CLASS_ARTIST,
    LIBRARY_ALBUMS: MEDIA_CLASS_ALBUM,
    LIBRARY_TRACKS: MEDIA_CLASS_TRACK,
    LIBRARY_PLAYLISTS: MEDIA_CLASS_PLAYLIST,
    LIBRARY_RADIO: MEDIA_CLASS_MUSIC,  # radio is not accepted by HA
}

MEDIA_CONTENT_TYPE_FLAC = "audio/flac"
THUMB_SIZE = 200


async def async_get_media_source(hass: HomeAssistant) -> MusicAssistentSource:
    """Set up Music Assistant media source."""
    # Music Assistant supports only a single config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    return MusicAssistentSource(hass, entry)


class MusicAssistentSource(MediaSource):
    """Provide Music Assistent Media Items as media sources."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize CameraMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry
        self.name = entry.title

    def get_mass(self) -> MusicAssistant | None:
        """Return the Music Assistant instance."""
        return self.hass.data.get(DOMAIN)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        mass = self.get_mass()

        if mass is None:
            raise Unresolvable("MusicAssistant is not initialized")

        if item.target_media_player is None:
            # TODO: How to intercept a play request for the 'webbrowser' player
            # or at least hide our source for the webbrowser player ?
            raise Unresolvable("Playback not supported on the device.")

        # get/create mass player instance attached to this entity id
        player = await async_register_player_control(
            self.hass, mass, item.target_media_player
        )
        if not player:
            return PlayMedia(item.identifier, MEDIA_TYPE_MUSIC)

        # send the mass library uri to the player(queue)
        await player.active_queue.play_media(item.identifier, passive=True)
        # tell the actual player to play the stream url
        content_type = player.active_queue.settings.stream_type.value
        return PlayMedia(player.active_queue.stream.url, f"audio/{content_type}")

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return library media for Music Assistent instance."""
        mass = self.get_mass()

        if mass is None:
            raise Unresolvable("MusicAssistant is not initialized")

        if item is None or item.identifier is None:
            return self._build_main_listing()
        if item.identifier == LIBRARY_ARTISTS:
            return await self._build_artists_listing(mass)
        if item.identifier == LIBRARY_ALBUMS:
            return await self._build_albums_listing(mass)
        if item.identifier == LIBRARY_TRACKS:
            return await self._build_tracks_listing(mass)
        if item.identifier == LIBRARY_PLAYLISTS:
            return await self._build_playlists_listing(mass)
        if item.identifier == LIBRARY_RADIO:
            return await self._build_radio_listing(mass)
        if "artist" in item.identifier:
            return await self._build_artist_items_listing(mass, item.identifier)
        if "album" in item.identifier:
            return await self._build_album_items_listing(mass, item.identifier)
        if "playlist" in item.identifier:
            return await self._build_playlist_items_listing(mass, item.identifier)

        raise Unresolvable(f"Unknown identifier: {item.identifier}")

    @callback
    def _build_main_listing(self):
        """Build main browse listing."""
        parent_source = BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            title=self.entry.title,
            media_class=MEDIA_CLASS_CHANNEL,
            media_content_type=MEDIA_TYPE_MUSIC,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_DIRECTORY,
            children=[],
        )
        for library, media_class in LIBRARY_MEDIA_CLASS_MAP.items():
            child_source = BrowseMediaSource(
                domain=DOMAIN,
                identifier=library,
                title=LIBRARY_TITLE_MAP[library],
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type=MEDIA_TYPE_MUSIC,
                children_media_class=media_class,
                can_play=False,
                can_expand=True,
            )
            parent_source.children.append(child_source)
        return parent_source

    async def _build_playlists_listing(self, mass: MusicAssistant):
        """Build Playlists browse listing."""
        media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_PLAYLISTS]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=LIBRARY_PLAYLISTS,
            title=LIBRARY_TITLE_MAP[LIBRARY_PLAYLISTS],
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=MEDIA_TYPE_PLAYLIST,
            can_play=False,
            can_expand=True,
            children_media_class=media_class,
            children=sorted(
                await asyncio.gather(
                    *[
                        self._build_item(mass, item, can_expand=True)
                        # we only grab the first page here becaus ethe HA media browser does not support paging
                        for item in (await mass.music.playlists.db_items(True)).items
                    ],
                ),
                key=lambda x: x.title,
            ),
        )

    async def _build_playlist_items_listing(
        self, mass: MusicAssistant, identifier: str
    ):
        """Build Playlist items browse listing."""
        playlist = await mass.music.get_item_by_uri(identifier)
        tracks = await mass.music.playlists.tracks(playlist.item_id, playlist.provider)

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=playlist.uri,
            title=playlist.name,
            media_class=MEDIA_CLASS_PLAYLIST,
            media_content_type=MEDIA_TYPE_PLAYLIST,
            can_play=True,
            can_expand=True,
            children_media_class=MEDIA_CLASS_TRACK,
            children=await asyncio.gather(
                *[self._build_item(mass, track, can_expand=False) for track in tracks],
            ),
        )

    async def _build_artists_listing(self, mass: MusicAssistant):
        """Build Albums browse listing."""
        media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_ARTISTS]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=LIBRARY_ARTISTS,
            title=LIBRARY_TITLE_MAP[LIBRARY_ARTISTS],
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=MEDIA_TYPE_ARTIST,
            can_play=False,
            can_expand=True,
            children_media_class=media_class,
            children=sorted(
                await asyncio.gather(
                    *[
                        self._build_item(mass, artist, can_expand=True)
                        # we only grab the first page here becaus ethe HA media browser does not support paging
                        for artist in (await mass.music.artists.db_items(True)).items
                    ],
                ),
                key=lambda x: x.title,
            ),
        )

    async def _build_artist_items_listing(self, mass: MusicAssistant, identifier: str):
        """Build Artist items browse listing."""
        artist = await mass.music.get_item_by_uri(identifier)
        albums = await mass.music.artists.albums(artist.item_id, artist.provider)

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=artist.uri,
            title=artist.name,
            media_class=MEDIA_TYPE_ARTIST,
            media_content_type=MEDIA_TYPE_ARTIST,
            can_play=True,
            can_expand=True,
            children_media_class=MEDIA_CLASS_ALBUM,
            children=await asyncio.gather(
                *[self._build_item(mass, album, can_expand=True) for album in albums],
            ),
        )

    async def _build_albums_listing(self, mass: MusicAssistant):
        """Build Albums browse listing."""
        media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_ALBUMS]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=LIBRARY_ALBUMS,
            title=LIBRARY_TITLE_MAP[LIBRARY_ALBUMS],
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=MEDIA_TYPE_ALBUM,
            can_play=False,
            can_expand=True,
            children_media_class=media_class,
            children=sorted(
                await asyncio.gather(
                    *[
                        self._build_item(mass, album, can_expand=True)
                        # we only grab the first page here becaus ethe HA media browser does not support paging
                        for album in (await mass.music.albums.db_items(True)).items
                    ],
                ),
                key=lambda x: x.title,
            ),
        )

    async def _build_album_items_listing(self, mass: MusicAssistant, identifier: str):
        """Build Album items browse listing."""
        album = await mass.music.get_item_by_uri(identifier)
        tracks = await mass.music.albums.tracks(album.item_id, album.provider)

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=album.uri,
            title=album.name,
            media_class=MEDIA_TYPE_ALBUM,
            media_content_type=MEDIA_TYPE_ALBUM,
            can_play=True,
            can_expand=True,
            children_media_class=MEDIA_CLASS_TRACK,
            children=await asyncio.gather(
                *[self._build_item(mass, track, False) for track in tracks],
            ),
        )

    async def _build_tracks_listing(self, mass: MusicAssistant):
        """Build Tracks browse listing."""
        media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_TRACKS]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=LIBRARY_ALBUMS,
            title=LIBRARY_TITLE_MAP[LIBRARY_TRACKS],
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=MEDIA_TYPE_TRACK,
            can_play=False,
            can_expand=True,
            children_media_class=media_class,
            children=sorted(
                await asyncio.gather(
                    *[
                        self._build_item(mass, track, can_expand=False)
                        # we only grab the first page here becaus ethe HA media browser does not support paging
                        for track in (await mass.music.tracks.db_items(True)).items
                    ],
                ),
                key=lambda x: x.title,
            ),
        )

    async def _build_radio_listing(self, mass: MusicAssistant):
        """Build Radio browse listing."""
        media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_RADIO]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=LIBRARY_ALBUMS,
            title=LIBRARY_TITLE_MAP[LIBRARY_RADIO],
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=MEDIA_TYPE_MUSIC,
            can_play=False,
            can_expand=True,
            children_media_class=media_class,
            children=await asyncio.gather(
                *[
                    self._build_item(
                        mass, track, can_expand=False, media_class=media_class
                    )
                    # we only grab the first page here becaus ethe HA media browser does not support paging
                    for track in (await mass.music.radio.db_items(True)).items
                ],
            ),
        )

    @staticmethod
    async def _build_item(
        mass: MusicAssistant, item: MediaItemType, can_expand=True, media_class=None
    ):
        """Return BrowseMediaSource for MediaItem."""
        if hasattr(item, "artists"):
            title = f"{item.artists[0].name} - {item.name}"
        else:
            title = item.name
        url = await mass.metadata.get_image_url_for_item(
            item, allow_local=False, local_as_base64=False
        )
        if url and url.startswith("http"):
            url = f"https://images.weserv.nl/?w={THUMB_SIZE}&url={url}"
        # disable image proxy due to 'authSig' bug in HA frontend
        # elif url:
        #     url = f"/api/mass/image_proxy?size={THUMB_SIZE}&url={url}"

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=item.uri,
            title=title,
            media_class=media_class or item.media_type.value,
            media_content_type=MEDIA_CONTENT_TYPE_FLAC,
            can_play=True,
            can_expand=can_expand,
            thumbnail=url,
        )
