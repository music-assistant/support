"""Constants for Music Assistant Component."""


DOMAIN = "mass"
DOMAIN_EVENT = f"{DOMAIN}_event"

DEFAULT_NAME = "Music Assistant"

CONF_PLAYER_ENTITIES = "player_entities"
CONF_HIDE_SOURCE_PLAYERS = "hide_source_players"
CONF_CREATE_MASS_PLAYERS = "create_mass_players"

CONF_SPOTIFY_ENABLED = "spotify_enabled"
CONF_SPOTIFY_USERNAME = "spotify_username"
CONF_SPOTIFY_PASSWORD = "spotify_password"

CONF_QOBUZ_ENABLED = "qobuz_enabled"
CONF_QOBUZ_USERNAME = "qobuz_username"
CONF_QOBUZ_PASSWORD = "qobuz_password"

CONF_TUNEIN_ENABLED = "tunein_enabled"
CONF_TUNEIN_USERNAME = "tunein_username"

CONF_YTMUSIC_ENABLED = "ytmusic_enabled"
CONF_YTMUSIC_USERNAME = "ytmusic_username"
CONF_YTMUSIC_PASSWORD = "ytmusic_password"

CONF_FILE_ENABLED = "filesystem_enabled"
CONF_FILE_DIRECTORY = "filesystem_directory"
CONF_PLAYLISTS_DIRECTORY = "playlists_directory"

CONF_MUTE_POWER_PLAYERS = "mute_power_players"


ATTR_SOURCE_ENTITY_ID = "source_entity_id"
ATTR_IS_GROUP = "is_group"
ATTR_GROUP_MEMBERS = "group_members"
ATTR_GROUP_PARENTS = "group_parents"
ATTR_ACTIVE_QUEUE = "active_queue"
ATTR_QUEUE_ITEMS = "items_in_queue"
ATTR_QUEUE_INDEX = "queue_index"
ATTR_GROUP_LEADER = "group_leader"

SLIMPROTO_DOMAIN = "slimproto"
SLIMPROTO_EVENT = "slimproto_event"

ESPHOME_DOMAIN = "esphome"
SONOS_DOMAIN = "sonos"
DLNA_DOMAIN = "dlna_dmr"
ATV_DOMAIN = "apple_tv"
KODI_DOMAIN = "kodi"
GROUP_DOMAIN = "group"
ALEXA_DOMAIN = "alexa_media"
VOLUMIO_DOMAIN = "volumio"
UNIVERSAL_DOMAIN = "universal"
SPOTIFY_DOMAIN = "spotify"

BLACKLIST_DOMAINS = (ATV_DOMAIN, ALEXA_DOMAIN, UNIVERSAL_DOMAIN, SPOTIFY_DOMAIN)
