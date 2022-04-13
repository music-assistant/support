/* eslint-disable @typescript-eslint/no-explicit-any */
import type {
  HassEntities,
  MessageBase,
  Connection,
  HassServices,
  HassConfig,
  HassServiceTarget,
  HassUser
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
  metadata: Record<string, unknown>;
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

export type HassPanel = {
  config: {
    title: string;
  };
};
export type HassRoute = {
  prefix: string;
  path: string;
};

type Context = {
  id: string;
  parent_id?: string;
  user_id?: string | null;
};

type ServiceCallResponse = {
  context: Context;
};

type ServiceCallRequest = {
  domain: string;
  service: string;
  serviceData?: Record<string, any>;
  target?: HassServiceTarget;
};

export type HomeAssistant = {
  connection: Connection;
  connected: boolean;
  states: HassEntities;
  services: HassServices;
  config: HassConfig;
  themes: {
    darkMode: boolean;
  };
  language: string;
  user?: HassUser;
  hassUrl(path?: string): string;
  callService(
    domain: ServiceCallRequest["domain"],
    service: ServiceCallRequest["service"],
    serviceData?: ServiceCallRequest["serviceData"],
    target?: ServiceCallRequest["target"]
  ): Promise<ServiceCallResponse>;
  sendWS(msg: MessageBase): void;
  callWS<T>(msg: MessageBase): Promise<T>;
};

export class MusicAssistantApi {
  // eslint-disable-next-line prettier/prettier
  private _hass: HomeAssistant | undefined;
  private _lastId: number;
  private _players: { [player_id: string]: Player };

  constructor(hass?: HomeAssistant) {
    this._hass = hass;
    this._lastId = 0;
    this._players = {};
    this.setup();
  }

  public get hass() {
    return this._hass;
  }

  public get players() {
    return reactive(this._players);
  }

  private async setup() {
    for (const player of await this.getPlayers()) {
      this._players[player.player_id] = player;
      console.log(player);
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

  public getTrack(uri: string, lazy = true): Promise<Track> {
    return this.getData("tracks", { object_id: uri, lazy });
  }

  public getLibraryArtists(): Promise<Artist[]> {
    return this.getData("artists");
  }

  public getArtist(uri: string, lazy = true): Promise<Artist> {
    return this.getData("artists", { object_id: uri, lazy });
  }

  public getLibraryAlbums(): Promise<Album[]> {
    return this.getData("albums");
  }

  public getAlbum(uri: string, lazy = true): Promise<Album> {
    return this.getData("albums", { object_id: uri, lazy });
  }

  public getLibraryPlaylists(): Promise<Playlist[]> {
    return this.getData("playlists");
  }

  public getPlaylist(uri: string, lazy = true): Promise<Playlist> {
    return this.getData("playlists", { object_id: uri, lazy });
  }

  public getLibraryRadio(): Promise<Radio[]> {
    return this.getData("radio");
  }

  public getRadio(uri: string, lazy = true): Promise<Radio> {
    return this.getData("radio", { object_id: uri, lazy });
  }

  private getData<T>(endpoint: string, args?: Record<string, any>): Promise<T> {
    this._lastId++;
    return (this._hass as HomeAssistant).callWS({
      id: this._lastId,
      type: `mass/${endpoint}`,
      ...args
    });
  }
}
