"""Constants for Music Assistant Component."""
import logging

DOMAIN = "mass"
DOMAIN_EVENT = f"{DOMAIN}_event"

DEFAULT_NAME = "Music Assistant"

ATTR_IS_GROUP = "is_group"
ATTR_GROUP_MEMBERS = "group_members"
ATTR_GROUP_PARENTS = "group_parents"
ATTR_ACTIVE_QUEUE = "active_queue"
ATTR_QUEUE_ITEMS = "items_in_queue"
ATTR_QUEUE_INDEX = "queue_index"
ATTR_GROUP_LEADER = "group_leader"
ATTR_MASS_PLAYER_ID = "mass_player_id"
ATTR_MASS_PLAYER_TYPE = "mass_player_type"
ATTR_STREAM_TITLE = "stream_title"

ADDON_SLUG = "d5369777_music_assistant_beta"
ADDON_HOSTNAME = "d5369777-music-assistant-beta"
ADDON_REPOSITORY = "https://github.com/music-assistant/home-assistant-addon"

CONF_INTEGRATION_CREATED_ADDON = "integration_created_addon"
CONF_USE_ADDON = "use_addon"
CONF_OPENAI_AGENT_ID = "openai_agent_id"
CONF_ASSIST_AUTO_EXPOSE_PLAYERS = "expose_players_assist"

LOGGER = logging.getLogger(__package__)
