/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  type Connection,
  createLongLivedTokenAuth,
  createConnection,
  ERR_HASS_HOST_REQUIRED
} from "home-assistant-js-websocket";

import { reactive } from "vue";

export enum MediaType {
  ARTIST = "artist",
  ALBUM = "album",
  TRACK = "track",
  PLAYLIST = "playlist",
  RADIO = "radio",
  UNKNOWN = "unknown"
}

export enum MediaQuality {
  LOSSY_MP3 = 0,
  LOSSY_OGG = 1,
  LOSSY_AAC = 2,
  FLAC_LOSSLESS = 6, // 44.1/48khz 16 bits
  FLAC_LOSSLESS_HI_RES_1 = 7, // 44.1/48khz 24 bits HI-RES
  FLAC_LOSSLESS_HI_RES_2 = 8, // 88.2/96khz 24 bits HI-RES
  FLAC_LOSSLESS_HI_RES_3 = 9, // 176/192khz 24 bits HI-RES
  FLAC_LOSSLESS_HI_RES_4 = 10, // above 192khz 24 bits HI-RES
  UNKNOWN = 99
}

export interface MediaItemProviderId {
  provider: string;
  item_id: string;
  quality: MediaQuality;
  details?: string;
  available: boolean;
}

export interface MediaItem {
  item_id: string;
  provider: string;
  name: string;
  sort_name?: string;
  metadata: Record<string, string>;
  provider_ids: MediaItemProviderId[];
  in_library: boolean;
  media_type: MediaType;
  uri: string;
}

export interface ItemMapping {
  item_id: string;
  provider: string;
  name: string;
  media_type: MediaType;
  uri: string;
}

export interface Artist extends MediaItem {
  musicbrainz_id: string;
}

export enum AlbumType {
  ALBUM = "album",
  SINGLE = "single",
  COMPILATION = "compilation",
  UNKNOWN = "unknown"
}

export interface Album extends MediaItem {
  version: string;
  year?: number;
  artist: ItemMapping | Artist;
  album_type: AlbumType;
  upc?: string;
}

export interface Track extends MediaItem {
  duration: number;
  version: string;
  isrc: string;
  artists: Array<ItemMapping | Artist>;
  // album track only
  album: ItemMapping | Album;
  disc_number?: number;
  track_number?: number;
  // playlist track only
  position?: number;
}

export interface Playlist extends MediaItem {
  owner: string;
  checksum: string;
  is_editable: boolean;
}

export interface Radio extends MediaItem {
  duration?: number;
}

export type MediaItemType = Artist | Album | Track | Playlist | Radio;

export enum StreamType {
  EXECUTABLE = "executable",
  URL = "url",
  FILE = "file",
  CACHE = "cache"
}

export enum ContentType {
  OGG = "ogg",
  FLAC = "flac",
  MP3 = "mp3",
  AAC = "aac",
  MPEG = "mpeg",
  WAV = "wav",
  PCM_S16LE = "s16le", // PCM signed 16-bit little-endian
  PCM_S24LE = "s24le", // PCM signed 24-bit little-endian
  PCM_S32LE = "s32le", // PCM signed 32-bit little-endian
  PCM_F32LE = "f32le", // PCM 32-bit floating-point little-endian
  PCM_F64LE = "f64le," // PCM 64-bit floating-point little-endian
}

export interface StreamDetails {
  type: StreamType;
  provider: string;
  item_id: string;
  path: string;
  content_type: ContentType;
  player_id: string;
  details: Record<string, unknown>;
  seconds_played: number;
  gain_correct: number;
  loudness?: number;
  sample_rate: number;
  bit_depth: number;
  channels: number;
  media_type: MediaType;
  queue_id: string;
}

export enum PlayerState {
  IDLE = "idle",
  PAUSED = "paused",
  PLAYING = "playing",
  OFF = "off"
}

export interface DeviceInfo {
  model: string;
  address: string;
  manufacturer: string;
}

export interface Player {
  player_id: string;
  name: string;
  powered: boolean;
  elapsed_time: number;
  state: PlayerState;
  available: boolean;
  is_group: boolean;
  group_childs: string[];
  group_parents: string[];
  volume_level: number;
  device_info: DeviceInfo;
  active_queue: string;
}

export interface QueueItem {
  uri: string;
  name: string;
  duration: number;
  item_id: string;
  sort_index: number;
  streamdetails?: StreamDetails;
  media_type: MediaType;
  is_media_item: boolean;
}

export interface PlayerQueue {
  queue_id: string;
  player: string;
  name: string;
  active: string;
  elapsed_time: number;
  state: PlayerState;
  available: boolean;
  current_item?: QueueItem;
  next_item?: QueueItem;
  shuffle_enabled: boolean;
  repeat_enabled: boolean;
  volume_normalization_enabled: boolean;
  volume_normalization_target: number;
  crossfade_duration: number;
}

export enum QueueCommand {
  PLAY = "play",
  PAUSE = "pause",
  PLAY_PAUSE = "play_pause",
  NEXT = "next",
  PREVIOUS = "previous",
  STOP = "stop",
  POWER = "power",
  POWER_TOGGLE = "power_toggle",
  VOLUME = "volume",
  VOLUME_UP = "volume_up",
  VOLUME_DOWN = "volume_down",
  SHUFFLE = "shuffle",
  REPEAT = "repeat",
  CLEAR = "clear",
  PLAY_INDEX = "play_index"
}

export enum MassEventType {
  PLAYER_ADDED = "player added",
  PLAYER_REMOVED = "player removed",
  PLAYER_UPDATED = "player updated",
  STREAM_STARTED = "streaming started",
  STREAM_ENDED = "streaming ended",
  CONFIG_CHANGED = "config changed",
  MUSIC_SYNC_STATUS = "music sync status",
  QUEUE_ADDED = "queue_added",
  QUEUE_UPDATED = "queue updated",
  QUEUE_ITEMS_UPDATED = "queue items updated",
  SHUTDOWN = "application shutdown",
  ARTIST_ADDED = "artist added",
  ALBUM_ADDED = "album added",
  TRACK_ADDED = "track added",
  PLAYLIST_ADDED = "playlist added",
  RADIO_ADDED = "radio added",
  TASK_UPDATED = "task updated",
  PROVIDER_REGISTERED = "PROVIDER_REGISTERED"
}

export enum QueueOption {
  PLAY = "play",
  REPLACE = "replace",
  NEXT = "next",
  ADD = "add"
}

export type MassEvent = {
  event: MassEventType;
  object_id?: string;
  data?: Record<string, any>;
};

export class MusicAssistantApi {
  // eslint-disable-next-line prettier/prettier
  private _conn?: Connection;
  private _lastId: number;
  public players = reactive<{ [player_id: string]: Player }>({});
  public queues = reactive<{ [queue_id: string]: PlayerQueue }>({});

  constructor(conn?: Connection) {
    this._conn = conn;
    this._lastId = 0;
  }

  public async initialize(conn?: Connection) {
    console.log("initialize api");
    if (conn) this._conn = conn;
    else if (!this._conn) {
      this._conn = await this.connectHassDev();
    }
    // load initial data from api
    for (const player of await this.getPlayers()) {
      this.players[player.player_id] = player;
    }
    for (const queue of await this.getPlayerQueues()) {
      this.queues[queue.queue_id] = queue;
    }
    // subscribe to mass events
    this._conn?.subscribeMessage(
      (msg: MassEvent) => {
        this.handleMassEvent(msg);
      },
      {
        type: "mass/subscribe"
      }
    );
  }

  private async connectHassDev() {
    const auth = createLongLivedTokenAuth(
      "http://localhost:8123",
      "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiI5YzVmZmViNThjNzM0NDIwOGYwYzEyMDMzZjViZDA0NyIsImlhdCI6MTY1MDI4NTk2NiwiZXhwIjoxOTY1NjQ1OTY2fQ.wC6W3m_chT7HCNrSWImjgmhVhH1IacMpId2vOkScG2A"
    );
    return await createConnection({ auth });
  }

  private handleMassEvent(msg: MassEvent) {
    console.log(msg.event);
    if (msg.event == MassEventType.QUEUE_ADDED) {
      const queue = msg.data as PlayerQueue;
      this.queues[queue.queue_id] = queue;
    } else if (msg.event == MassEventType.QUEUE_UPDATED) {
      const queue = msg.data as PlayerQueue;
      Object.assign(this.queues[queue.queue_id], queue);
    } else if (msg.event == MassEventType.PLAYER_ADDED) {
      const player = msg.data as Player;
      this.players[player.player_id] = player;
    } else if (msg.event == MassEventType.PLAYER_UPDATED) {
      const player = msg.data as Player;
      Object.assign(this.players[player.player_id], player);
    }
  }

  public async getPlayers(): Promise<Player[]> {
    return this.getData("players");
  }

  public async getPlayerQueues(): Promise<PlayerQueue[]> {
    return this.getData("playerqueues");
  }

  public getLibraryTracks(): Promise<Track[]> {
    return this.getData("tracks");
  }

  public getTrack(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Track> {
    return this.getData("track", { provider, item_id, lazy });
  }

  public getTrackVersions(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Track[]> {
    return this.getData("track/versions", { provider, item_id, lazy });
  }

  public getLibraryArtists(): Promise<Artist[]> {
    return this.getData("artists");
  }

  public getArtist(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Artist> {
    return this.getData("artist", { provider, item_id, lazy });
  }

  public getArtistTracks(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Track[]> {
    return this.getData("artist/tracks", { provider, item_id, lazy });
  }

  public getArtistAlbums(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Album[]> {
    return this.getData("artist/albums", { provider, item_id, lazy });
  }

  public getLibraryAlbums(): Promise<Album[]> {
    return this.getData("albums");
  }

  public getAlbum(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Album> {
    return this.getData("album", { provider, item_id, lazy });
  }

  public getAlbumTracks(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Track[]> {
    return this.getData("album/tracks", { provider, item_id, lazy });
  }

  public getAlbumVersions(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Album[]> {
    return this.getData("album/versions", { provider, item_id, lazy });
  }

  public getLibraryPlaylists(): Promise<Playlist[]> {
    return this.getData("playlists");
  }

  public getPlaylist(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Playlist> {
    return this.getData("playlist", { provider, item_id, lazy });
  }

  public getPlaylistTracks(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Track[]> {
    return this.getData("playlist/tracks", { provider, item_id, lazy });
  }

  public addPlaylistTracks(
    provider: string,
    item_id: string,
    uri: string | string[],
  ) {
    this.executeCmd("playlist/tracks/add", { provider, item_id, uri });
  }

  public removePlaylistTracks(
    provider: string,
    item_id: string,
    uri: string | string[],
  ) {
    this.executeCmd("playlist/tracks/remove", { provider, item_id, uri });
  }

  public getLibraryRadios(): Promise<Radio[]> {
    return this.getData("radios");
  }

  public getRadio(
    provider: string,
    item_id: string,
    lazy = true
  ): Promise<Radio> {
    return this.getData("radio", { provider, item_id, lazy });
  }

  public getItem(uri: string, lazy = true): Promise<MediaItemType> {
    return this.getData("item", { uri, lazy });
  }

  public async addToLibrary(items: MediaItemType[]) {
    for (const x of items) {
      x.in_library = true;
    }
    // TODO
  }
  public async removeFromLibrary(items: MediaItemType[]) {
    for (const x of items) {
      x.in_library = false;
    }
    // TODO
  }
  public async toggleLibrary(item: MediaItemType) {
    // TODO
    if (item.in_library) return await this.removeFromLibrary([item]);
    return await this.addToLibrary([item]);
  }

  public queueCommandPlay(playerId: string) {
    this.playerQueueCommand(playerId, QueueCommand.PLAY);
  }
  public queueCommandPause(playerId: string) {
    this.playerQueueCommand(playerId, QueueCommand.PAUSE);
  }
  public queueCommandPlayPause(playerId: string) {
    this.playerQueueCommand(playerId, QueueCommand.PLAY_PAUSE);
  }
  public queueCommandStop(playerId: string) {
    this.playerQueueCommand(playerId, QueueCommand.STOP);
  }
  public queueCommandPowerToggle(playerId: string) {
    this.playerQueueCommand(playerId, QueueCommand.POWER_TOGGLE);
  }
  public queueCommandNext(playerId: string) {
    this.playerQueueCommand(playerId, QueueCommand.NEXT);
  }
  public queueCommandPrevious(playerId: string) {
    this.playerQueueCommand(playerId, QueueCommand.PREVIOUS);
  }
  public queueCommandVolume(playerId: string, newVolume: number) {
    this.playerQueueCommand(playerId, QueueCommand.VOLUME, newVolume);
    this.players[playerId].volume_level = newVolume;
  }
  public queueCommandVolumeUp(playerId: string) {
    this.playerQueueCommand(playerId, QueueCommand.VOLUME_UP);
  }
  public queueCommandVolumeDown(playerId: string) {
    this.playerQueueCommand(playerId, QueueCommand.VOLUME_DOWN);
  }

  public playerQueueCommand(
    queue_id: string,
    command: QueueCommand,
    command_arg?: boolean | number
  ) {
    this.executeCmd("queue_command", { queue_id, command, command_arg });
  }

  public playMedia(
    queue_id: string,
    uri: string | string[],
    command: QueueOption = QueueOption.PLAY
  ) {
    this.executeCmd("play_media", { queue_id, command });
  }

  public getImageUrl(mediaItem?: MediaItemType | ItemMapping, key = "image") {
    // get imageurl for mediaItem
    if (!mediaItem || !mediaItem.media_type) return "";
    if ("metadata" in mediaItem && mediaItem.metadata[key])
      return mediaItem.metadata[key];
    if (
      "album" in mediaItem &&
      mediaItem.album !== null &&
      "metadata" in mediaItem.album &&
      mediaItem.album.metadata &&
      mediaItem.album.metadata[key]
    )
      return mediaItem.album.metadata[key];
    if (
      "artist" in mediaItem &&
      "metadata" in mediaItem.artist &&
      mediaItem.artist.metadata &&
      mediaItem.artist.metadata[key]
    )
      return mediaItem.artist.metadata[key];
  }

  public getFanartUrl(mediaItem?: MediaItemType, fallbackToImage = true) {
    const fanartImage = this.getImageUrl(mediaItem, "fanart");
    if (fanartImage) return fanartImage;
    if (fallbackToImage) return this.getImageUrl(mediaItem);
  }

  public async getImageUrlForMediaItem(item: MediaItemType | ItemMapping) {
    const url = this.getImageUrl(item);
    if (url) return url;
    const fullItem = await this.getItem(item.uri);
    return this.getImageUrl(fullItem);
  }

  private getData<T>(endpoint: string, args?: Record<string, any>): Promise<T> {
    this._lastId++;
    return (this._conn as Connection).sendMessagePromise({
      id: this._lastId,
      type: `mass/${endpoint}`,
      ...args
    });
  }

  private executeCmd(endpoint: string, args?: Record<string, any>) {
    this._lastId++;
    (this._conn as Connection).sendMessage({
      id: this._lastId,
      type: `mass/${endpoint}`,
      ...args
    });
  }
}

export const api = new MusicAssistantApi();
export default api;
