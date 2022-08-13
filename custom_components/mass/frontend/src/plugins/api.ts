import { store } from './store';
/* eslint-disable no-constant-condition */
/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  type Connection,
  createConnection,
  ERR_HASS_HOST_REQUIRED,
  getAuth,
} from 'home-assistant-js-websocket';
import { reactive, ref } from 'vue';

export enum MediaType {
  ARTIST = 'artist',
  ALBUM = 'album',
  TRACK = 'track',
  PLAYLIST = 'playlist',
  RADIO = 'radio',
  FOLDER = 'folder',
  UNKNOWN = 'unknown',
}

export enum MediaQuality {
  UNKNOWN = 0,
  LOSSY_MP3 = 1,
  LOSSY_OGG = 2,
  LOSSY_AAC = 3,
  LOSSY_M4A = 4,
  LOSSLESS = 10, // 44.1/48khz 16 bits
  LOSSLESS_HI_RES_1 = 20, // 44.1/48khz 24 bits HI-RES
  LOSSLESS_HI_RES_2 = 21, // 88.2/96khz 24 bits HI-RES
  LOSSLESS_HI_RES_3 = 22, // 176/192khz 24 bits HI-RES
  LOSSLESS_HI_RES_4 = 23, // above 192khz 24 bits HI-RES
}

export enum ProviderType {
  FILESYSTEM_LOCAL = 'file',
  FILESYSTEM_SMB = 'smb',
  FILESYSTEM_GOOGLE_DRIVE = 'gdrive',
  FILESYSTEM_ONEDRIVE = 'onedrive',
  SPOTIFY = 'spotify',
  QOBUZ = 'qobuz',
  TUNEIN = 'tunein',
  YTMUSIC = 'ytmusic',
  DATABASE = 'database',
  URL = 'url',
}
export interface MediaItemProviderId {
  item_id: string;
  prov_type: ProviderType;
  prov_id: string;
  available: boolean;
  quality?: MediaQuality;
  details?: string;
  url?: string;
}

export enum LinkType {
  WEBSITE = 'website',
  FACEBOOK = 'facebook',
  TWITTER = 'twitter',
  LASTFM = 'lastfm',
  YOUTUBE = 'youtube',
  INSTAGRAM = 'instagram',
  SNAPCHAT = 'snapchat',
  TIKTOK = 'tiktok',
  DISCOGS = 'discogs',
  WIKIPEDIA = 'wikipedia',
  ALLMUSIC = 'allmusic',
}

export enum ImageType {
  THUMB = 'thumb',
  WIDE_THUMB = 'wide_thumb',
  FANART = 'fanart',
  LOGO = 'logo',
  CLEARART = 'clearart',
  BANNER = 'banner',
  CUTOUT = 'cutout',
  BACK = 'back',
  CDART = 'cdart',
  EMBEDDED_THUMB = 'embedded_thumb',
  OTHER = 'other',
}

export interface MediaItemLink {
  type: LinkType;
  url: string;
}

export interface MediaItemImage {
  type: ImageType;
  url: string;
  is_file: boolean;
}

export interface MediaItemMetadata {
  description?: string;
  review?: string;
  explicit?: boolean;
  images?: MediaItemImage[];
  genres?: string[];
  mood?: string;
  style?: string;
  copyright?: string;
  lyrics?: string;
  label?: string;
  links?: MediaItemLink[];
  performers?: string[];
  preview?: string;
  replaygain?: number;
  popularity?: number;
}

export interface ItemMapping {
  item_id: string;
  provider: ProviderType;
  name: string;
  media_type: MediaType;
  uri: string;
}

export interface MediaItem {
  [x: string]: any;
  item_id: string;
  provider: ProviderType;
  name: string;
  sort_name?: string;
  metadata: MediaItemMetadata;
  provider_ids: MediaItemProviderId[];
  in_library: boolean;
  media_type: MediaType;
  uri: string;
  timestamp: number;
}

export interface Artist extends MediaItem {
  musicbrainz_id: string;
}

export enum AlbumType {
  ALBUM = 'album',
  SINGLE = 'single',
  COMPILATION = 'compilation',
  UNKNOWN = 'unknown',
}

export interface Album extends MediaItem {
  version: string;
  year?: number;
  artist: ItemMapping | Artist;
  album_type: AlbumType;
  upc?: string;
  musicbrainz_id?: string;
}

export interface Track extends MediaItem {
  duration: number;
  version: string;
  isrc: string;
  musicbrainz_id?: string;
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

export interface BrowseFolder extends MediaItem {
  path?: string;
  label: string;
  items?: MediaItemType[];
}

export type MediaItemType =
  | Artist
  | Album
  | Track
  | Playlist
  | Radio
  | BrowseFolder;

export enum ContentType {
  OGG = 'ogg',
  FLAC = 'flac',
  MP3 = 'mp3',
  AAC = 'aac',
  MPEG = 'mpeg',
  ALAC = 'alac',
  WAV = 'wav',
  AIFF = 'aiff',
  WMA = 'wma',
  M4A = 'm4a',
  DSF = 'dsf',
  WAVPACK = 'wv',
  PCM_S16LE = 's16le', // PCM signed 16-bit little-endian
  PCM_S24LE = 's24le', // PCM signed 24-bit little-endian
  PCM_S32LE = 's32le', // PCM signed 32-bit little-endian
  PCM_F32LE = 'f32le', // PCM 32-bit floating-point little-endian
  PCM_F64LE = 'f64le', // PCM 64-bit floating-point little-endian
  UNKNOWN = '?',
}

export interface StreamDetails {
  provider: ProviderType;
  item_id: string;
  content_type: ContentType;
  media_type: MediaType;
  sample_rate: number;
  bit_depth: number;
  channels: number;
  stream_title?: string;
  duration?: number;
  size?: number;
  queue_id?: string;
  seconds_streamed: number;
  seconds_skipped: number;
  gain_correct: number;
  loudness?: number;
}

export enum PlayerState {
  IDLE = 'idle',
  PAUSED = 'paused',
  PLAYING = 'playing',
  OFF = 'off',
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
  volume_level: number;
  is_group: boolean;
  group_members: string[];
  is_passive: boolean;
  is_group_leader: boolean;
  group_name: string;
  group_powered: boolean;
  group_volume_level: number;
  group_leader: string;
  device_info: DeviceInfo;
  active_queue: string;
}

export interface QueueItem {
  name: string;
  duration: number;
  item_id: string;
  sort_index: number;
  streamdetails?: StreamDetails;
  image?: MediaItemImage;
  media_item?: Track | Radio;
}

export enum CrossFadeMode {
  DISABLED = 'disabled', // no crossfading at all
  STRICT = 'strict', // do not crossfade tracks of same album
  SMART = 'smart', // crossfade if possible (do not crossfade different sample rates)
  ALWAYS = 'always', // all tracks - resample to fixed sample rate
}

export enum RepeatMode {
  OFF = 'off', // no repeat at all
  ONE = 'one', // repeat current/single track
  ALL = 'all', // repeat entire queue
}

export enum MetadataMode {
  DISABLED = 'disabled', // do not notify icy support
  DEFAULT = 'default', // enable icy if player requests it, default chunksize
  LEGACY = 'legacy', // enable icy but with legacy 8kb chunksize, requires mp3
}

export interface QueueSettings {
  repeat_mode: RepeatMode;
  shuffle_enabled: boolean;
  crossfade_mode: CrossFadeMode;
  crossfade_duration: number;
  volume_normalization_enabled: boolean;
  volume_normalization_target: number;
  stream_type: ContentType;
  max_sample_rate: number;
  announce_volume_increase: number;
  metadata_mode: MetadataMode;
}

export type QueueSettingsUpdate = Partial<QueueSettings>;

export interface PlayerQueue {
  queue_id: string;
  player: string;
  name: string;
  active: string;
  elapsed_time: number;
  state: PlayerState;
  available: boolean;
  current_index?: number;
  index_in_buffer?: number;
  current_item?: QueueItem;
  next_item?: QueueItem;
  items: number;
  settings: QueueSettings;
  radio_source: MediaItemType[];
}

export enum QueueCommand {
  PLAY = 'play',
  PAUSE = 'pause',
  PLAY_PAUSE = 'play_pause',
  NEXT = 'next',
  PREVIOUS = 'previous',
  STOP = 'stop',
  SEEK = 'seek',
  SKIP_AHEAD = 'skip_ahead',
  SKIP_BACK = 'skip_back',
  POWER = 'power',
  POWER_TOGGLE = 'power_toggle',
  VOLUME = 'volume',
  VOLUME_UP = 'volume_up',
  VOLUME_DOWN = 'volume_down',
  CLEAR = 'clear',
  PLAY_INDEX = 'play_index',
  MOVE_UP = 'move_up',
  MOVE_DOWN = 'move_down',
  MOVE_NEXT = 'move_next',
  DELETE = 'delete',
  GROUP_POWER = 'group_power',
  GROUP_VOLUME = 'group_volume',
}

export enum MassEventType {
  PLAYER_ADDED = 'player_added',
  PLAYER_UPDATED = 'player_updated',
  STREAM_STARTED = 'streaming_started',
  STREAM_ENDED = 'streaming_ended',
  QUEUE_ADDED = 'queue_added',
  QUEUE_UPDATED = 'queue_updated',
  QUEUE_ITEMS_UPDATED = 'queue_items_updated',
  QUEUE_TIME_UPDATED = 'queue_time_updated',
  SHUTDOWN = 'application_shutdown',
  BACKGROUND_JOB_UPDATED = 'background_job_updated',
  BACKGROUND_JOB_FINISHED = 'background_job_finished',
  MEDIA_ITEM_ADDED = 'media_item_added',
  MEDIA_ITEM_UPDATED = 'media_item_updated',
  MEDIA_ITEM_DELETED = 'media_item_deleted',
  // special types for local subscriptions only
  ALL = '*',
}

export enum QueueOption {
  PLAY = 'play',
  REPLACE = 'replace',
  NEXT = 'next',
  ADD = 'add',
  REPLACE_NEXT = 'replace_next',
}

export type MassEvent = {
  type: MassEventType;
  object_id?: string;
  data?: Record<string, any>;
};

export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  CANCELLED = 'cancelled',
  FINISHED = 'success',
  ERROR = 'error',
}

export type BackgroundJob = {
  id: string;
  name: string;
  timestamp: number;
  status: JobStatus;
};

export enum MusicProviderFeature {
  // browse/explore/recommendations
  BROWSE = 'browse',
  SEARCH = 'search',
  RECOMMENDATIONS = 'recommendations',
  // library feature per mediatype
  LIBRARY_ARTISTS = 'library_artists',
  LIBRARY_ALBUMS = 'library_albums',
  LIBRARY_TRACKS = 'library_tracks',
  LIBRARY_PLAYLISTS = 'library_playlists',
  LIBRARY_RADIOS = 'library_radios',
  // additional library features
  ARTIST_ALBUMS = 'artist_albums',
  ARTIST_TOPTRACKS = 'artist_toptracks',
  // library edit (=add/remove) feature per mediatype
  LIBRARY_ARTISTS_EDIT = 'library_artists_edit',
  LIBRARY_ALBUMS_EDIT = 'library_albums_edit',
  LIBRARY_TRACKS_EDIT = 'library_tracks_edit',
  LIBRARY_PLAYLISTS_EDIT = 'library_playlists_edit',
  LIBRARY_RADIOS_EDIT = 'library_radios_edit',
  // bonus features
  SIMILAR_TRACKS = 'similar_tracks',
  // playlist-specific features
  PLAYLIST_TRACKS_EDIT = 'playlist_tracks_edit',
  PLAYLIST_CREATE = 'playlist_create',
}

export interface MusicProvider {
  type: ProviderType;
  name: string;
  id: string;
  supported_features: MusicProviderFeature[];
}

export interface Library {
  artists: Artist[];
  albums: Album[];
  tracks: Track[];
  radios: Radio[];
  playlists: Playlist[];
  artistsFetched: boolean;
  albumsFetched: boolean;
  tracksFetched: boolean;
  radiosFetched: boolean;
  playlistsFetched: boolean;
}

export interface PagedItems {
  items: MediaItemType[];
  count: number;
  limit: number;
  offset: number;
  total?: number;
}

export class MusicAssistantApi {
  // eslint-disable-next-line prettier/prettier
  private _conn?: Connection;
  private _lastId: number;
  private _throttleId?: any;
  public players = reactive<{ [player_id: string]: Player }>({});
  public queues = reactive<{ [queue_id: string]: PlayerQueue }>({});
  public providers = reactive<{ [provider_id: string]: MusicProvider }>({});
  public jobs = ref<BackgroundJob[]>([]);
  private _wsEventCallbacks: Array<[string, CallableFunction]>;

  constructor(conn?: Connection) {
    this._conn = conn;
    this._lastId = 0;
    this._wsEventCallbacks = [];
  }

  public async initialize(conn?: Connection) {
    if (this._conn) throw 'already connected';
    if (conn) this._conn = conn;
    else if (!this._conn) {
      this._conn = await this.connectHassStandalone();
    }
    if (this._conn?.socket?.url) {
      store.apiBaseUrl = this._conn?.socket?.url
        .replace('ws://', 'http://')
        .replace('wss://', 'https://')
        .replace('/websocket', '');
    }
    console.log('store.apiBaseUrl', store.apiBaseUrl);

    store.apiInitialized = true;
    console.log('conn', this._conn);

    // load initial data from api
    this._fetchState();
    // subscribe to mass events
    this._conn?.subscribeEvents((x) => this.handleHassEvent(x), 'mass_event');
  }

  public subscribe(eventFilter: MassEventType, callback: CallableFunction) {
    // subscribe a listener for events
    // returns handle to remove the listener
    const listener: [MassEventType, CallableFunction] = [eventFilter, callback];
    this._wsEventCallbacks.push(listener);
    const removeCallback = () => {
      const index = this._wsEventCallbacks.indexOf(listener);
      if (index > -1) {
        this._wsEventCallbacks.splice(index, 1);
      }
    };
    return removeCallback;
  }

  public subscribe_multi(
    eventFilters: MassEventType[],
    callback: CallableFunction
  ) {
    // subscribe a listener for multiple events
    // returns handle to remove the listener
    const removeCallbacks: CallableFunction[] = [];
    for (const eventFilter of eventFilters) {
      removeCallbacks.push(this.subscribe(eventFilter, callback));
    }
    const removeCallback = () => {
      for (const cb of removeCallbacks) {
        cb();
      }
    };
    return removeCallback;
  }

  private async _fetchState() {
    // fetch full initial state
    for (const player of await this.getPlayers()) {
      this.players[player.player_id] = player;
    }
    for (const queue of await this.getPlayerQueues()) {
      this.queues[queue.queue_id] = queue;
    }

    const providers = await this.getData<{
      [provider_id: string]: MusicProvider;
    }>('providers');
    Object.assign(this.providers, providers);

    this.jobs.value = await this.getData('jobs');
  }

  public getTracks(
    offset?: number,
    limit?: number,
    sort?: string,
    library?: boolean,
    search?: string
  ): Promise<PagedItems> {
    return this.getData('tracks', { offset, limit, sort, library, search });
  }

  public getTrack(
    provider: ProviderType,
    item_id: string,
    lazy = true,
    refresh = false,
    force_provider_version = false
  ): Promise<Track> {
    return this.getData('track', {
      provider,
      item_id,
      lazy,
      refresh,
      force_provider_version,
    });
  }

  public getTrackVersions(
    provider: ProviderType,
    item_id: string
  ): Promise<Track[]> {
    return this.getData('track/versions', { provider, item_id });
  }

  public getTrackPreviewUrl(
    provider: ProviderType,
    item_id: string
  ): Promise<string> {
    return this.getData('track/preview', {
      provider,
      item_id,
    });
  }

  public getArtists(
    offset?: number,
    limit?: number,
    sort?: string,
    library?: boolean,
    search?: string,
    albumArtistsOnly?: boolean
  ): Promise<PagedItems> {
    return this.getData('artists', {
      offset,
      sort,
      limit,
      library,
      search,
      album_artists_only: albumArtistsOnly,
    });
  }

  public getArtist(
    provider: ProviderType,
    item_id: string,
    lazy = true,
    refresh = false
  ): Promise<Artist> {
    return this.getData('artist', { provider, item_id, lazy, refresh });
  }

  public getArtistTracks(
    provider: ProviderType,
    item_id: string
  ): Promise<Track[]> {
    return this.getData('artist/tracks', { provider, item_id });
  }

  public getArtistAlbums(
    provider: ProviderType,
    item_id: string
  ): Promise<Album[]> {
    return this.getData('artist/albums', { provider, item_id });
  }

  public getAlbums(
    offset?: number,
    limit?: number,
    sort?: string,
    library?: boolean,
    search?: string
  ): Promise<PagedItems> {
    return this.getData('albums', { offset, limit, sort, library, search });
  }

  public getAlbum(
    provider: ProviderType,
    item_id: string,
    lazy = true,
    refresh = false,
    force_provider_version = false
  ): Promise<Album> {
    return this.getData('album', {
      provider,
      item_id,
      lazy,
      refresh,
      force_provider_version,
    });
  }

  public getAlbumTracks(
    provider: ProviderType,
    item_id: string
  ): Promise<Track[]> {
    return this.getData('album/tracks', { provider, item_id });
  }

  public getAlbumVersions(
    provider: ProviderType,
    item_id: string
  ): Promise<Album[]> {
    return this.getData('album/versions', { provider, item_id });
  }

  public getPlaylists(
    offset?: number,
    limit?: number,
    sort?: string,
    library?: boolean,
    search?: string
  ): Promise<PagedItems> {
    return this.getData('playlists', { offset, limit, sort, library, search });
  }

  public getPlaylist(
    provider: ProviderType,
    item_id: string,
    lazy = true,
    refresh = false
  ): Promise<Playlist> {
    return this.getData('playlist', { provider, item_id, lazy, refresh });
  }

  public getPlaylistTracks(
    provider: ProviderType,
    item_id: string
  ): Promise<Track[]> {
    return this.getData('playlist/tracks', { provider, item_id });
  }

  public addPlaylistTracks(item_id: string, uri: string | string[]) {
    this.executeCmd('playlist/tracks/add', { item_id, uri });
  }

  public removePlaylistTracks(item_id: string, position: number | number[]) {
    this.executeCmd('playlist/tracks/remove', { item_id, position });
  }

  public createPlaylist(name: string, provider_id?: string): Promise<Playlist> {
    return this.getData('playlist/create', { name, provider_id });
  }

  public getRadios(
    offset?: number,
    limit?: number,
    sort?: string,
    library?: boolean,
    search?: string
  ): Promise<PagedItems> {
    return this.getData('radios', { offset, limit, sort, library, search });
  }

  public getRadio(
    provider: ProviderType,
    item_id: string,
    lazy = true,
    refresh = false
  ): Promise<Radio> {
    return this.getData('radio', { provider, item_id, lazy, refresh });
  }

  public getRadioVersions(
    provider: ProviderType,
    item_id: string
  ): Promise<Radio[]> {
    return this.getData('radio/versions', { provider, item_id });
  }

  public getItem(
    uri: string,
    lazy = true,
    refresh = false
  ): Promise<MediaItemType> {
    return this.getData('item', { uri, lazy, refresh });
  }

  public async addToLibrary(items: MediaItemType[]) {
    for (const x of items) {
      this.executeCmd('library/add', { uri: x.uri });
    }
  }
  public async removeFromLibrary(items: MediaItemType[]) {
    for (const x of items) {
      this.executeCmd('library/remove', { uri: x.uri });
    }
  }
  public async toggleLibrary(item: MediaItemType) {
    if (item.in_library) return await this.removeFromLibrary([item]);
    return await this.addToLibrary([item]);
  }

  public async deleteDbItem(
    media_type: MediaType,
    db_id: string,
    recursive = false
  ) {
    this.executeCmd('delete_db_item', { media_type, db_id, recursive });
  }

  public browse(path?: string): Promise<BrowseFolder> {
    return this.getData('browse', { path });
  }

  public search(
    query: string,
    media_types?: MediaType[],
    limit?: number
  ): Promise<Track[]> {
    return this.getData('search', { query, media_types, limit });
  }

  public async getPlayers(): Promise<Player[]> {
    return this.getData('players');
  }

  public async getPlayerQueues(): Promise<PlayerQueue[]> {
    return this.getData('playerqueues');
  }

  public async getPlayerQueueItems(queue_id: string): Promise<QueueItem[]> {
    return this.getData('playerqueue/items', { queue_id });
  }

  public queueCommandPlay(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.PLAY);
  }
  public queueCommandPause(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.PAUSE);
  }
  public queueCommandPlayPause(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.PLAY_PAUSE);
  }
  public queueCommandStop(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.STOP);
  }
  public queueCommandPowerToggle(queueId: string) {
    this.playerQueueCommand(
      queueId,
      QueueCommand.POWER,
      !this.players[queueId].powered
    );
  }
  public queueCommandNext(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.NEXT);
  }
  public queueCommandPrevious(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.PREVIOUS);
  }

  public queueCommandVolume(queueId: string, newVolume: number) {
    this.playerQueueCommand(queueId, QueueCommand.VOLUME, newVolume);
    this.players[queueId].volume_level = newVolume;
  }
  public queueCommandVolumeUp(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.VOLUME_UP);
  }
  public queueCommandVolumeDown(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.VOLUME_DOWN);
  }
  public queueCommandClear(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.CLEAR);
  }
  public queueCommandPlayIndex(queueId: string, index: number | string) {
    this.playerQueueCommand(queueId, QueueCommand.PLAY_INDEX, index);
  }
  public queueCommandMoveUp(queueId: string, itemId: string) {
    this.playerQueueCommand(queueId, QueueCommand.MOVE_UP, itemId);
  }
  public queueCommandMoveDown(queueId: string, itemId: string) {
    this.playerQueueCommand(queueId, QueueCommand.MOVE_DOWN, itemId);
  }
  public queueCommandMoveNext(queueId: string, itemId: string) {
    this.playerQueueCommand(queueId, QueueCommand.MOVE_NEXT, itemId);
  }
  public queueCommandDelete(queueId: string, itemId: string) {
    this.playerQueueCommand(queueId, QueueCommand.DELETE, itemId);
  }

  public queueCommandSeek(queueId: string, position: number) {
    this.playerQueueCommand(queueId, QueueCommand.SEEK, position);
  }
  public queueCommandSkipAhead(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.SKIP_AHEAD);
  }
  public queueCommandSkipBack(queueId: string) {
    this.playerQueueCommand(queueId, QueueCommand.SKIP_BACK);
  }

  public queueCommandGroupVolume(queueId: string, newVolume: number) {
    this.playerQueueCommand(queueId, QueueCommand.GROUP_VOLUME, newVolume);
    this.players[queueId].group_volume_level = newVolume;
  }
  public queueCommandGroupPower(queueId: string, newPower: boolean) {
    this.playerQueueCommand(queueId, QueueCommand.GROUP_POWER, newPower);
    this.players[queueId].group_powered = newPower;
  }

  public playerQueueCommand(
    queue_id: string,
    command: QueueCommand,
    command_arg?: boolean | number | string
  ) {
    // apply a bit of throttling here (for the volume and seek sliders especially)
    clearTimeout(this._throttleId);
    this._throttleId = setTimeout(() => {
      this.executeCmd('playerqueue/command', {
        queue_id,
        command,
        command_arg,
      });
    }, 200);
  }

  public playerQueueSettings(queueId: string, settings: QueueSettingsUpdate) {
    this.executeCmd('playerqueue/settings', { queue_id: queueId, settings });
  }

  public playMedia(
    media: string | string[] | MediaItemType | MediaItemType[],
    option: QueueOption = QueueOption.PLAY,
    radio_mode = false,
    queue_id?: string
  ) {
    if (!queue_id) {
      queue_id = store.selectedPlayer?.active_queue;
    }
    this.executeCmd('play_media', { queue_id, option, media, radio_mode });
  }

  public async playPlaylistFromIndex(
    playlist: Playlist,
    startIndex: number,
    queue_id?: string
  ) {
    const tracks = await this.getPlaylistTracks(
      playlist.provider,
      playlist.item_id
    );
    // to account for shuffle, we play the first track and append the rest
    this.playMedia(
      tracks[startIndex],
      QueueOption.REPLACE,
      undefined,
      queue_id
    );
    this.playMedia(
      tracks.slice(startIndex + 1),
      QueueOption.ADD,
      undefined,
      queue_id
    );
  }

  public async playAlbumFromItem(
    album: Album,
    startItem: Track,
    queue_id?: string
  ) {
    const tracks = await this.getAlbumTracks(album.provider, album.item_id);
    let startIndex = 0;
    tracks.forEach(function (track, i) {
      if (track.item_id == startItem.item_id) {
        startIndex = i;
      }
    });
    // to account for shuffle, we play the first track and append the rest
    this.playMedia(
      tracks[startIndex],
      QueueOption.REPLACE,
      undefined,
      queue_id
    );
    this.playMedia(
      tracks.slice(startIndex + 1),
      QueueOption.ADD,
      undefined,
      queue_id
    );
  }

  public startSync(
    media_type?: MediaType,
    prov_type?: ProviderType,
    clear_cache?: boolean
  ) {
    this.executeCmd('start_sync', { media_type, prov_type, clear_cache });
  }

  public getLocalThumb(path: string, size?: number): Promise<string> {
    return this.getData('thumb', { path, size });
  }

  private async connectHassStandalone() {
    let auth;
    const storeAuth = true;
    const authOptions = storeAuth
      ? {
        async loadTokens() {
          try {
            return JSON.parse(localStorage.hassTokens);
          } catch (err) {
            return undefined;
          }
        },
        saveTokens: (tokens: any) => {
          localStorage.hassTokens = JSON.stringify(tokens);
        },
      }
      : {};
    try {
      auth = await getAuth(authOptions);
    } catch (err) {
      if (err === ERR_HASS_HOST_REQUIRED) {
        authOptions.hassUrl = prompt(
          'Please enter the URL to Home Assistant',
          'http://localhost:8123'
        );
        if (!authOptions.hassUrl) return;
        auth = await getAuth(authOptions);
      } else {
        alert(`Unknown error: ${err}`);
        return;
      }
    }
    const connection = await createConnection({ auth });
    connection.addEventListener('ready', () => window.history.back());
    return connection;
  }

  private handleHassEvent(msg: { event_type: string; data: MassEvent }) {
    const massEvent: MassEvent = msg.data;
    if (massEvent.type == MassEventType.QUEUE_ADDED) {
      const queue = massEvent.data as PlayerQueue;
      this.queues[queue.queue_id] = queue;
    } else if (massEvent.type == MassEventType.QUEUE_UPDATED) {
      const queue = massEvent.data as PlayerQueue;
      if (queue.queue_id in this.queues)
        Object.assign(this.queues[queue.queue_id], queue);
      else this.queues[queue.queue_id] = queue;
    } else if (massEvent.type == MassEventType.QUEUE_TIME_UPDATED) {
      const queueId = massEvent.object_id as string;
      if (queueId in this.queues)
        this.queues[queueId].elapsed_time = massEvent.data as unknown as number;
    } else if (massEvent.type == MassEventType.PLAYER_ADDED) {
      const player = massEvent.data as Player;
      this.players[player.player_id] = player;
    } else if (massEvent.type == MassEventType.PLAYER_UPDATED) {
      const player = massEvent.data as Player;
      if (player.player_id in this.players)
        Object.assign(this.players[player.player_id], player);
      else this.players[player.player_id] = player;
    } else if (
      massEvent.type ==
        (MassEventType.BACKGROUND_JOB_UPDATED ||
          MassEventType.BACKGROUND_JOB_FINISHED) &&
      massEvent.data
    ) {
      this.jobs.value = this.jobs.value.filter(
        (x) => x.id !== massEvent.data?.id
      );
      this.jobs.value.push(massEvent.data as BackgroundJob);
    }
    // signal + log all events
    if (massEvent.type !== MassEventType.QUEUE_TIME_UPDATED) {
      console.log('[event]', massEvent);
    }
    this.signalEvent(massEvent);
  }

  private signalEvent(massEvent: MassEvent) {
    // signal event to all listeners
    for (const listener of this._wsEventCallbacks) {
      if (listener[0] === MassEventType.ALL || listener[0] === massEvent.type) {
        listener[1](massEvent);
      }
    }
  }

  private getData<T>(endpoint: string, args?: Record<string, any>): Promise<T> {
    this._lastId++;
    console.log(`[getData] ${endpoint}`, args || '');
    return (this._conn as Connection).sendMessagePromise({
      id: this._lastId,
      type: `mass/${endpoint}`,
      ...args,
    });
  }

  private executeCmd(endpoint: string, args?: Record<string, any>) {
    this._lastId++;
    console.log(`[executeCmd] ${endpoint}`, args || '');
    (this._conn as Connection).sendMessage({
      id: this._lastId,
      type: `mass/${endpoint}`,
      ...args,
    });
  }
}

export const api = new MusicAssistantApi();
export default api;
