"""Media Source Implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_TRACK,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
    MediaClass,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from music_assistant.common.models.media_items import MediaItemType

from .const import DEFAULT_NAME, DOMAIN

if TYPE_CHECKING:
    from music_assistant.client import MusicAssistantClient

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


def media_source_filter(item: BrowseMedia) -> bool:
    """Filter media sources."""
    return item.media_content_type.startswith("audio/")


async def async_browse_media(
    hass: HomeAssistant,
    mass: MusicAssistantClient,
    media_content_id: str | None,
    media_content_type: str | None,
) -> BrowseMedia:
    """Browse media."""
    # pylint: disable=too-many-return-statements
    if media_content_id is None:
        return await build_main_listing(hass)

    assert media_content_type is not None

    if media_source.is_media_source_id(media_content_id):
        return await media_source.async_browse_media(
            hass, media_content_id, content_filter=media_source_filter
        )

    if media_content_id == LIBRARY_ARTISTS:
        return await build_artists_listing(mass)
    if media_content_id == LIBRARY_ALBUMS:
        return await build_albums_listing(mass)
    if media_content_id == LIBRARY_TRACKS:
        return await build_tracks_listing(mass)
    if media_content_id == LIBRARY_PLAYLISTS:
        return await build_playlists_listing(mass)
    if media_content_id == LIBRARY_RADIO:
        return await build_radio_listing(mass)
    if "artist" in media_content_id:
        return await build_artist_items_listing(mass, media_content_id)
    if "album" in media_content_id:
        return await build_album_items_listing(mass, media_content_id)
    if "playlist" in media_content_id:
        return await build_playlist_items_listing(mass, media_content_id)

    raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")


@callback
async def build_main_listing(hass: HomeAssistant):
    """Build main browse listing."""
    parent_source = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type=DOMAIN,
        title=DEFAULT_NAME,
        can_play=False,
        can_expand=True,
        children=[],
    )
    for library, media_class in LIBRARY_MEDIA_CLASS_MAP.items():
        child_source = BrowseMedia(
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id=library,
            media_content_type=DOMAIN,
            title=LIBRARY_TITLE_MAP[library],
            children_media_class=media_class,
            can_play=False,
            can_expand=True,
        )
        parent_source.children.append(child_source)

    try:
        item = await media_source.async_browse_media(
            hass, None, content_filter=media_source_filter
        )
        # If domain is None, it's overview of available sources
        if item.domain is None and item.children is not None:
            parent_source.children.extend(item.children)
        else:
            parent_source.children.append(item)
    except media_source.BrowseError:
        pass
    return parent_source


async def build_playlists_listing(mass: MusicAssistantClient):
    """Build Playlists browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_PLAYLISTS]
    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=LIBRARY_PLAYLISTS,
        media_content_type=MEDIA_TYPE_PLAYLIST,
        title=LIBRARY_TITLE_MAP[LIBRARY_PLAYLISTS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=sorted(
            [
                build_item(mass, item, can_expand=True)
                # we only grab the first page here because the
                # HA media browser does not support paging
                for item in await mass.music.get_library_playlists(limit=500)
                if item.available
            ],
            key=lambda x: x.title,
        ),
    )


async def build_playlist_items_listing(mass: MusicAssistantClient, identifier: str):
    """Build Playlist items browse listing."""
    playlist = await mass.music.get_item_by_uri(identifier)

    return BrowseMedia(
        media_class=MEDIA_CLASS_PLAYLIST,
        media_content_id=playlist.uri,
        media_content_type=MEDIA_TYPE_PLAYLIST,
        title=playlist.name,
        can_play=True,
        can_expand=True,
        children_media_class=MEDIA_CLASS_TRACK,
        children=[
            build_item(mass, item, can_expand=False)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for item in await mass.music.get_playlist_tracks(
                playlist.item_id, playlist.provider
            )
            if item.available
        ],
    )


async def build_artists_listing(mass: MusicAssistantClient):
    """Build Albums browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_ARTISTS]

    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=LIBRARY_ARTISTS,
        media_content_type=MEDIA_TYPE_ARTIST,
        title=LIBRARY_TITLE_MAP[LIBRARY_ARTISTS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=sorted(
            [
                build_item(mass, artist, can_expand=True)
                # we only grab the first page here because the
                # HA media browser does not support paging
                for artist in await mass.music.get_library_artists(limit=500)
                if artist.available
            ],
            key=lambda x: x.title,
        ),
    )


async def build_artist_items_listing(mass: MusicAssistantClient, identifier: str):
    """Build Artist items browse listing."""
    artist = await mass.music.get_item_by_uri(identifier)
    albums = await mass.music.get_artist_albums(artist.item_id, artist.provider)

    return BrowseMedia(
        media_class=MEDIA_TYPE_ARTIST,
        media_content_id=artist.uri,
        media_content_type=MEDIA_TYPE_ARTIST,
        title=artist.name,
        can_play=True,
        can_expand=True,
        children_media_class=MEDIA_CLASS_ALBUM,
        children=[
            build_item(mass, album, can_expand=True)
            for album in albums
            if album.available
        ],
    )


async def build_albums_listing(mass: MusicAssistantClient):
    """Build Albums browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_ALBUMS]

    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=LIBRARY_ALBUMS,
        media_content_type=MEDIA_TYPE_ALBUM,
        title=LIBRARY_TITLE_MAP[LIBRARY_ALBUMS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=sorted(
            [
                build_item(mass, album, can_expand=True)
                # we only grab the first page here because the
                # HA media browser does not support paging
                for album in await mass.music.get_library_albums(limit=500)
                if album.available
            ],
            key=lambda x: x.title,
        ),
    )


async def build_album_items_listing(mass: MusicAssistantClient, identifier: str):
    """Build Album items browse listing."""
    album = await mass.music.get_item_by_uri(identifier)
    tracks = await mass.music.get_album_tracks(album.item_id, album.provider)

    return BrowseMedia(
        media_class=MEDIA_TYPE_ALBUM,
        media_content_id=album.uri,
        media_content_type=MEDIA_TYPE_ALBUM,
        title=album.name,
        can_play=True,
        can_expand=True,
        children_media_class=MEDIA_CLASS_TRACK,
        children=[
            build_item(mass, track, False) for track in tracks if track.available
        ],
    )


async def build_tracks_listing(mass: MusicAssistantClient):
    """Build Tracks browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_TRACKS]

    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=LIBRARY_ALBUMS,
        media_content_type=MEDIA_TYPE_TRACK,
        title=LIBRARY_TITLE_MAP[LIBRARY_TRACKS],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=sorted(
            [
                build_item(mass, track, can_expand=False)
                # we only grab the first page here because the
                # HA media browser does not support paging
                for track in await mass.music.get_library_tracks(limit=500)
                if track.available
            ],
            key=lambda x: x.title,
        ),
    )


async def build_radio_listing(mass: MusicAssistantClient):
    """Build Radio browse listing."""
    media_class = LIBRARY_MEDIA_CLASS_MAP[LIBRARY_RADIO]
    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=LIBRARY_ALBUMS,
        media_content_type=DOMAIN,
        title=LIBRARY_TITLE_MAP[LIBRARY_RADIO],
        can_play=False,
        can_expand=True,
        children_media_class=media_class,
        children=[
            build_item(mass, track, can_expand=False, media_class=media_class)
            # we only grab the first page here because the
            # HA media browser does not support paging
            for track in await mass.music.get_library_radios(limit=500)
            if track.available
        ],
    )


def build_item(
    mass: MusicAssistantClient,
    item: MediaItemType,
    can_expand=True,
    media_class=None,
) -> BrowseMedia:
    """Return BrowseMedia for MediaItem."""
    if artists := getattr(item, "artists", None):
        title = f"{artists[0].name} - {item.name}"
    else:
        title = item.name
    img_url = mass.get_media_item_image_url(item)

    return BrowseMedia(
        media_class=media_class or item.media_type.value,
        media_content_id=item.uri,
        media_content_type=MediaType.MUSIC,
        title=title,
        can_play=True,
        can_expand=can_expand,
        thumbnail=img_url,
    )
