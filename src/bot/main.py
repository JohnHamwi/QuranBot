# =============================================================================
# QuranBot - Discord Audio Bot (Open Source Edition)
# =============================================================================
# This is an open source project provided AS-IS without official support.
# Feel free to use, modify, and learn from this code under the license terms.
#
# Core Features:
# - Voice channel audio playback of Quranic recitations
# - Automatic audio management and state persistence
# - Rich presence integration with Discord
# - Comprehensive logging and error handling
# - Control panel for bot management
#
# Technical Implementation:
# - Built on discord.py library
# - Asynchronous audio handling
# - Event-driven architecture
# - Modular component design
# =============================================================================

import asyncio
import glob
import os
import traceback
from pathlib import Path
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from aiohttp.client_exceptions import ClientConnectionResetError

# =============================================================================
# Environment Configuration
# =============================================================================
# Loads environment variables from .env file in config directory
# Required Variables:
# - DISCORD_TOKEN: Your bot's Discord token
# - GUILD_ID: Your Discord server ID
# - CONTROL_CHANNEL: Channel ID for bot control panel
# Optional Variables:
# - LOG_CHANNEL: Channel ID for logging (if not set, logs to console only)
# - BACKUP_INTERVAL: Interval in hours between backups (default: 24)
# =============================================================================
from dotenv import load_dotenv

# Load environment variables from the correct path
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env")
load_dotenv(env_path)

import os

# =============================================================================
# Import Tree Logging Functions
# =============================================================================
# Custom logging system that provides:
# - Hierarchical log organization
# - Multi-destination logging (console, file, Discord)
# - Structured error reporting
# - Activity tracking and statistics
# =============================================================================
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# =============================================================================
# Discord Logging Configuration
# =============================================================================
# Configures Discord's internal logging system to integrate with our tree logger
# Provides detailed tracking of:
# - Voice connection states
# - Gateway events
# - Client operations
# - Error conditions
# =============================================================================
import logging

# =============================================================================
# Import Daily Verses Manager
# =============================================================================
from src.utils.daily_verses import setup_daily_verses

# =============================================================================
# Import Quiz Manager
# =============================================================================
from src.utils.quiz_manager import setup_quiz_system

# =============================================================================
# Import Version Information
# =============================================================================
from src.version import BOT_NAME, BOT_VERSION

# =============================================================================
# Import Audio Manager
# =============================================================================
from utils.audio_manager import AudioManager

# =============================================================================
# Import Backup Manager
# =============================================================================
from utils.backup_manager import start_backup_scheduler

# =============================================================================
# Import Control Panel Manager
# =============================================================================
from utils.control_panel import setup_control_panel

# =============================================================================
# Import Discord Logger for VPS Monitoring
# =============================================================================
from utils.discord_logger import setup_discord_logger, get_discord_logger

# =============================================================================
# Import Listening Stats Manager
# =============================================================================
from utils.listening_stats import track_voice_join, track_voice_leave

# =============================================================================
# Import Rich Presence Manager
# =============================================================================
from utils.rich_presence import RichPresenceManager, validate_rich_presence_dependencies

# =============================================================================
# Import State Manager
# =============================================================================
from utils.state_manager import state_manager

# =============================================================================
# Import Surah Mapping Functions
# =============================================================================
from utils.surah_mapper import (
    format_now_playing,
    get_surah_display,
    get_surah_info,
    validate_surah_number,
)
from utils.tree_log import (
    get_timestamp,
    log_async_error,
    log_critical_error,
    log_discord_error,
    log_error_with_traceback,
    log_perfect_tree_section,
    log_progress,
    log_spacing,
    log_voice_activity_tree,
    log_warning_with_context,
    write_to_log_files,
)
from utils.discord_api_monitor import initialize_discord_monitor, get_discord_monitor

# =============================================================================
# Global Managers
# =============================================================================
rich_presence = None
audio_manager = None


class DiscordTreeHandler(logging.Handler):
    """
    Custom logging handler that formats Discord logs in tree-style format.

    This is an open source component that can be used as a reference for
    implementing custom Discord.py logging handlers.

    Key Features:
    - Converts Discord.py logs into hierarchical tree format
    - Filters unnecessary verbose messages
    - Categorizes logs by Discord subsystem
    - Provides consistent formatting across all log sources
    - Supports both console and file output

    Implementation Notes:
    - Extends logging.Handler for seamless Discord.py integration
    - Uses custom tree logging for visual consistency
    - Implements smart filtering to reduce log noise
    - Provides separate handlers for different Discord components

    Usage:
    1. Create an instance of DiscordTreeHandler
    2. Add it to your Discord client's logger
    3. Configure log levels as needed
    4. Logs will automatically format in tree style
    """

    def emit(self, record):
        """
        Handle a Discord log record by formatting it in tree style.

        Processes incoming Discord log records and converts them to tree-style
        logging with appropriate categorization and filtering. Skips verbose
        messages that would clutter the logs.

        Args:
            record: LogRecord object from Discord.py logging system
        """
        try:
            # Get the log message
            message = self.format(record)

            # Skip certain verbose messages to prevent log spam
            if any(
                skip in message.lower()
                for skip in [
                    "keeping websocket alive",
                    "sending heartbeat",
                    "received heartbeat",
                    "heartbeat acknowledged",
                ]
            ):
                return

            # Map Discord log levels to tree logging
            level_name = record.levelname
            logger_name = record.name

            # Import the file logging function for dual output
            from utils.tree_log import write_to_log_files

            # Format based on the Discord module for appropriate categorization
            if "voice_state" in logger_name:
                self._handle_voice_state_log(message, level_name)
            elif "gateway" in logger_name:
                self._handle_gateway_log(message, level_name)
            elif "client" in logger_name:
                self._handle_client_log(message, level_name)
            else:
                # Generic Discord log handling
                log_perfect_tree_section(
                    "Discord - Generic",
                    [
                        ("discord_info", f"📡 {message}"),
                    ],
                    "📡",
                )
                write_to_log_files(f"Discord: {message}", level_name, "discord_generic")

        except Exception as e:
            # Prevent logging errors from crashing the handler
            from utils.tree_log import log_error_with_traceback

            log_error_with_traceback("Error in DiscordTreeHandler.emit", e)

    def _handle_voice_state_log(self, message, level_name):
        """
        Handle voice state related log messages with appropriate categorization.

        Args:
            message: Log message content
            level_name: Original log level from Discord
        """
        from utils.tree_log import write_to_log_files

        if "connecting" in message.lower():
            log_perfect_tree_section(
                "Discord Voice State - Connecting",
                [
                    ("status", "🔄 Connecting to voice..."),
                    ("message", message),
                ],
                "🎵",
            )
            write_to_log_files(
                f"Discord Voice: Connecting to voice - {message}",
                level_name,
                "discord_voice",
            )
        elif "handshake" in message.lower():
            log_perfect_tree_section(
                "Discord Voice State - Handshake",
                [
                    ("status", "🤝 Voice handshake in progress"),
                    ("message", message),
                ],
                "🎵",
            )
            write_to_log_files(
                f"Discord Voice: Handshake in progress - {message}",
                level_name,
                "discord_voice",
            )
        elif "connection complete" in message.lower():
            log_perfect_tree_section(
                "Discord Voice State - Connected",
                [
                    ("status", "✅ Voice connection established"),
                    ("message", message),
                ],
                "🎵",
            )
            write_to_log_files(
                f"Discord Voice: Connection established - {message}",
                level_name,
                "discord_voice",
            )
        elif "disconnected" in message.lower():
            log_perfect_tree_section(
                "Discord Voice State - Disconnected",
                [
                    ("status", "⚠️ Voice disconnected - reconnecting..."),
                    ("message", message),
                ],
                "🎵",
            )
            write_to_log_files(
                f"Discord Voice: Disconnected - {message}",
                "WARNING",
                "discord_voice",
            )
        elif "terminated" in message.lower():
            log_perfect_tree_section(
                "Discord Voice State - Terminated",
                [
                    ("status", "🧹 Voice connection terminated"),
                    ("message", message),
                ],
                "🎵",
            )
            write_to_log_files(
                f"Discord Voice: Connection terminated - {message}",
                level_name,
                "discord_voice",
            )
        else:
            log_perfect_tree_section(
                "Discord Voice State - General",
                [
                    ("status", f"🎵 {message}"),
                ],
                "🎵",
            )
            write_to_log_files(f"Discord Voice: {message}", level_name, "discord_voice")

    def _handle_gateway_log(self, message, level_name):
        """
        Handle Discord gateway related log messages.

        Args:
            message: Log message content
            level_name: Original log level from Discord
        """
        from utils.tree_log import write_to_log_files

        if "connected" in message.lower():
            log_perfect_tree_section(
                "Discord Gateway - Connected",
                [
                    ("status", "✅ Connected to Discord Gateway"),
                    ("message", message),
                ],
                "📡",
            )
            write_to_log_files(
                f"Discord Gateway: Connected - {message}",
                level_name,
                "discord_gateway",
            )
        elif "session" in message.lower():
            log_perfect_tree_section(
                "Discord Gateway - Session",
                [
                    ("status", "🔑 Discord session established"),
                    ("message", message),
                ],
                "📡",
            )
            write_to_log_files(
                f"Discord Gateway: Session established - {message}",
                level_name,
                "discord_gateway",
            )
        else:
            log_perfect_tree_section(
                "Discord Gateway - General",
                [
                    ("status", f"📡 {message}"),
                ],
                "📡",
            )
            write_to_log_files(
                f"Discord Gateway: {message}", level_name, "discord_gateway"
            )

    def _handle_client_log(self, message, level_name):
        """
        Handle Discord client related log messages.

        Args:
            message: Log message content
            level_name: Original log level from Discord
        """
        from utils.tree_log import write_to_log_files

        if "logging in" in message.lower():
            log_perfect_tree_section(
                "Discord Client - Authentication",
                [
                    ("status", "🔐 Authenticating with Discord..."),
                    ("message", message),
                ],
                "🤖",
            )
            write_to_log_files(
                f"Discord Client: Authenticating - {message}",
                level_name,
                "discord_client",
            )
        else:
            log_perfect_tree_section(
                "Discord Client - General",
                [
                    ("status", f"🤖 {message}"),
                ],
                "🤖",
            )
            write_to_log_files(
                f"Discord Client: {message}", level_name, "discord_client"
            )


def setup_discord_logging():
    """
    Configure Discord loggers to use tree-style formatting consistently.

    Sets up custom logging handlers for all Discord.py loggers to ensure
    consistent tree-style formatting throughout the application. Replaces
    default Discord handlers with our custom DiscordTreeHandler.

    Features:
    - Removes default Discord logging handlers
    - Applies custom tree-style formatting
    - Prevents log duplication through propagation control
    - Configures appropriate log levels for each Discord module

    Discord Loggers Configured:
    - discord: Main Discord.py logger
    - discord.client: Client connection and authentication
    - discord.gateway: Gateway connection and session management
    - discord.voice_state: Voice connection state changes
    - discord.player: Audio player events and status
    """
    try:
        # Create our custom handler
        tree_handler = DiscordTreeHandler()
        tree_handler.setLevel(logging.INFO)

        # Configure main Discord loggers
        discord_loggers = [
            "discord",
            "discord.client",
            "discord.gateway",
            "discord.voice_state",
            "discord.player",
        ]

        for logger_name in discord_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.INFO)

            # Remove existing handlers to prevent duplication
            logger.handlers.clear()

            # Add our tree handler
            logger.addHandler(tree_handler)

            # Prevent propagation to avoid duplicate logs
            logger.propagate = False

        log_perfect_tree_section(
            "Discord Logging Configuration",
            [
                ("status", "✅ Tree-style Discord logging configured"),
                ("loggers_configured", len(discord_loggers)),
                ("handler_level", "INFO"),
            ],
            "📡",
        )

    except Exception as e:
        log_error_with_traceback("Error setting up Discord logging", e)


# Initialize Discord logging
setup_discord_logging()

# =============================================================================
# Bot Configuration
# =============================================================================

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)
# commands.Bot already has a command tree, no need to create another one

# Bot metadata - imported from centralized version module
# BOT_NAME and BOT_VERSION now imported from version module

# Environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID") or "0")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID") or "0")
GUILD_ID = int(os.getenv("GUILD_ID") or "0")
PANEL_ACCESS_ROLE_ID = int(os.getenv("PANEL_ACCESS_ROLE_ID") or "1391500136366211243")
DAILY_VERSE_CHANNEL_ID = int(os.getenv("DAILY_VERSE_CHANNEL_ID") or "0")
DEVELOPER_ID = int(os.getenv("DEVELOPER_ID") or "0")
LOGS_CHANNEL_ID = int(os.getenv("LOGS_CHANNEL_ID") or "0")  # VPS Discord logging
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "")  # Dashboard URL for monitoring
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
AUDIO_FOLDER = "audio/Saad Al Ghamdi"

# Audio settings
DEFAULT_RECITER = os.getenv("DEFAULT_RECITER", "Saad Al Ghamdi")
DEFAULT_SHUFFLE = os.getenv("DEFAULT_SHUFFLE", "false").lower() == "true"
DEFAULT_LOOP = os.getenv("DEFAULT_LOOP", "false").lower() == "true"


# =============================================================================
# Configuration Validation
# =============================================================================
def validate_configuration():
    """
    Validate bot configuration and environment variables comprehensively.

    Performs thorough validation of all required configuration parameters
    including Discord credentials, channel IDs, file paths, and external
    dependencies. Provides detailed error reporting and warnings for
    potential issues.

    Validation Categories:
    - Discord Authentication: Token validation and format checking
    - Server Configuration: Guild and channel ID validation
    - File System: Audio folder and FFmpeg executable checks
    - External Dependencies: Rich Presence and audio processing tools

    Returns:
        bool: True if all critical configuration is valid, False otherwise

    Note:
        Warnings are logged but don't prevent bot startup. Only critical
        errors (missing Discord token, invalid IDs) cause startup failure.
    """
    try:

        errors = []
        warnings = []

        # =============================================================================
        # Discord Authentication Validation
        # =============================================================================
        if not DISCORD_TOKEN:
            errors.append("DISCORD_TOKEN is missing from environment variables")
        elif not isinstance(DISCORD_TOKEN, str):
            errors.append("DISCORD_TOKEN must be a string")
        elif len(DISCORD_TOKEN) < 50:
            warnings.append("DISCORD_TOKEN appears to be invalid (too short)")
        else:
            # Modern Discord bot tokens have specific patterns
            # They can be raw tokens or prefixed with "Bot "
            token_to_check = DISCORD_TOKEN
            if DISCORD_TOKEN.startswith("Bot "):
                token_to_check = DISCORD_TOKEN[4:]  # Remove "Bot " prefix
            elif DISCORD_TOKEN.startswith("Bearer "):
                token_to_check = DISCORD_TOKEN[7:]  # Remove "Bearer " prefix
            
            # Discord tokens are typically 59+ characters long
            # Modern tokens may have different patterns, so we'll be more lenient
            if len(token_to_check) < 59:
                warnings.append("DISCORD_TOKEN appears to be too short for a valid Discord token")
            # Remove the character pattern check as it's too restrictive

        # =============================================================================
        # Server Configuration Validation
        # =============================================================================
        if GUILD_ID == 0:
            errors.append("GUILD_ID is missing or invalid in environment variables")
        elif not isinstance(GUILD_ID, int) or GUILD_ID < 0:
            errors.append("GUILD_ID must be a positive integer")

        if TARGET_CHANNEL_ID == 0:
            errors.append(
                "TARGET_CHANNEL_ID is missing or invalid in environment variables"
            )
        elif not isinstance(TARGET_CHANNEL_ID, int) or TARGET_CHANNEL_ID < 0:
            errors.append("TARGET_CHANNEL_ID must be a positive integer")

        if PANEL_CHANNEL_ID == 0:
            warnings.append(
                "PANEL_CHANNEL_ID is missing - control panel will not be created"
            )
        elif not isinstance(PANEL_CHANNEL_ID, int) or PANEL_CHANNEL_ID < 0:
            warnings.append("PANEL_CHANNEL_ID must be a positive integer")

        if PANEL_ACCESS_ROLE_ID == 0:
            warnings.append(
                "PANEL_ACCESS_ROLE_ID is missing - voice channel role management disabled"
            )
        elif not isinstance(PANEL_ACCESS_ROLE_ID, int) or PANEL_ACCESS_ROLE_ID < 0:
            warnings.append("PANEL_ACCESS_ROLE_ID must be a positive integer")

        # =============================================================================
        # File System Validation
        # =============================================================================
        if not AUDIO_FOLDER:
            errors.append("AUDIO_FOLDER is not specified")
        elif not os.path.exists(AUDIO_FOLDER):
            warnings.append(f"Audio folder '{AUDIO_FOLDER}' does not exist")
        elif not os.path.isdir(AUDIO_FOLDER):
            warnings.append(f"Audio folder '{AUDIO_FOLDER}' is not a directory")
        else:
            # Check for audio files in the folder
            try:
                audio_files = glob.glob(os.path.join(AUDIO_FOLDER, "*.mp3"))
                if not audio_files:
                    warnings.append(f"No MP3 files found in '{AUDIO_FOLDER}'")
                else:
                    log_perfect_tree_section(
                        "Audio Files Validation",
                        [
                            ("status", "✅ Audio files found"),
                            ("count", len(audio_files)),
                            ("folder", AUDIO_FOLDER),
                        ],
                        "🎵",
                    )
            except Exception as e:
                warnings.append(f"Error scanning audio folder: {str(e)}")

        # =============================================================================
        # FFmpeg Validation
        # =============================================================================
        if not FFMPEG_PATH:
            errors.append("FFMPEG_PATH is not specified")
        else:
            try:
                import subprocess

                result = subprocess.run(
                    [FFMPEG_PATH, "-version"],
                    capture_output=True,
                    check=True,
                    timeout=10,
                )
                # Check FFmpeg version for compatibility
                version_output = result.stdout.decode("utf-8", errors="ignore")
                if "ffmpeg version" in version_output.lower():
                    version_line = version_output.split("\n")[0]
                    log_perfect_tree_section(
                        "FFmpeg Validation",
                        [
                            ("status", "✅ FFmpeg is accessible"),
                            ("version", version_line.strip()),
                            ("path", FFMPEG_PATH),
                        ],
                        "🎬",
                    )
                else:
                    log_perfect_tree_section(
                        "FFmpeg Validation",
                        [
                            ("status", "✅ FFmpeg is accessible"),
                            ("path", FFMPEG_PATH),
                        ],
                        "🎬",
                    )

            except subprocess.TimeoutExpired:
                warnings.append(f"FFmpeg at '{FFMPEG_PATH}' is not responding")
            except subprocess.CalledProcessError as e:
                warnings.append(
                    f"FFmpeg at '{FFMPEG_PATH}' returned error: {e.returncode}"
                )
            except FileNotFoundError:
                warnings.append(
                    f"FFmpeg not found at '{FFMPEG_PATH}' - audio playback may fail"
                )
            except Exception as e:
                log_error_with_traceback("Error checking FFmpeg availability", e)
                warnings.append(f"Could not validate FFmpeg: {str(e)}")

        # =============================================================================
        # Environment Defaults Validation
        # =============================================================================
        if not DEFAULT_RECITER:
            warnings.append("DEFAULT_RECITER is not specified, using fallback")
        elif not isinstance(DEFAULT_RECITER, str):
            warnings.append("DEFAULT_RECITER should be a string")

        if not isinstance(DEFAULT_SHUFFLE, bool):
            warnings.append("DEFAULT_SHUFFLE should be a boolean (true/false)")

        if not isinstance(DEFAULT_LOOP, bool):
            warnings.append("DEFAULT_LOOP should be a boolean (true/false)")

        # =============================================================================
        # External Dependencies Validation
        # =============================================================================
        try:
            rp_validation = validate_rich_presence_dependencies()
            if isinstance(rp_validation, bool):
                # Function returns bool, not dict - create appropriate response
                if not rp_validation:
                    warnings.append("Rich Presence dependencies validation failed")
            else:
                # Handle dict response if it exists
                warnings.extend(rp_validation.get("warnings", []))
                if rp_validation.get("errors"):
                    warnings.extend(rp_validation["errors"])

        except Exception as e:
            log_error_with_traceback("Error validating Rich Presence dependencies", e)
            warnings.append("Could not validate Rich Presence dependencies")

        # =============================================================================
        # Results Reporting
        # =============================================================================
        if errors:
            error_items = [("error_count", f"Found {len(errors)} critical errors")]
            for i, error in enumerate(errors, 1):
                error_items.append((f"error_{i}", f"❌ {error}"))
            error_items.append(("result", "❌ Configuration validation failed"))

            log_perfect_tree_section(
                "Configuration Validation",
                error_items,
                "🔧",
            )
            return False

        if warnings:
            warning_items = [("warning_count", f"Found {len(warnings)} warnings")]
            for i, warning in enumerate(warnings, 1):
                warning_items.append((f"warning_{i}", f"⚠️ {warning}"))
            warning_items.append(
                ("result", "✅ Configuration validation passed (with warnings)")
            )

            log_perfect_tree_section(
                "Configuration Validation",
                warning_items,
                "🔧",
            )
        else:
            log_perfect_tree_section(
                "Configuration Validation",
                [
                    ("result", "✅ Configuration validation passed"),
                    ("errors", "0"),
                    ("warnings", "0"),
                ],
                "🔧",
            )
        return True

    except Exception as e:
        log_critical_error("Configuration validation failed with exception", e)
        return False


# =============================================================================
# Discord Bot Events
# =============================================================================
@bot.event
async def on_ready():
    """
    Handle Discord bot ready event and initialize all bot systems.

    This is the main initialization event that sets up all bot components
    after successful Discord connection. It handles:
    - State manager initialization and session tracking
    - Rich Presence and Audio Manager setup
    - Configuration validation and error handling
    - Voice channel connection with retry logic
    - Control panel setup and integration
    - Graceful error recovery and logging

    The function implements robust error handling with retry logic for
    voice connections and comprehensive logging for troubleshooting.

    Raises:
        Various exceptions are caught and handled gracefully with appropriate
        logging and cleanup. Critical errors may cause bot shutdown.
    """
    global rich_presence, audio_manager

    try:
        # =============================================================================
        # Control Panel Cleanup
        # =============================================================================
        # Clean up any existing control panels before creating new ones
        log_spacing()
        try:
            from utils.control_panel import cleanup_all_control_panels

            cleanup_all_control_panels()
            log_perfect_tree_section(
                "Control Panel - Startup Cleanup",
                [
                    ("status", "✅ Existing control panels cleaned up"),
                    ("action", "Ready for new panel creation"),
                    ("timing", "Before bot initialization"),
                ],
                "🧹",
            )
        except Exception as e:
            log_error_with_traceback("Error cleaning up control panels on startup", e)

        # =============================================================================
        # State Manager Initialization
        # =============================================================================
        # Mark startup in state manager for session tracking
        state_manager.mark_startup()

        log_perfect_tree_section(
            f"{BOT_NAME} v{BOT_VERSION} Started",
            [
                ("bot_user", f"{bot.user}"),
                ("version", BOT_VERSION),
                ("guild_id", str(GUILD_ID)),
                ("target_channel_id", str(TARGET_CHANNEL_ID)),
                ("startup_time", f"{get_timestamp().strip('[]')}"),
            ],
            "🎯",
        )

        # =============================================================================
        # Manager Initialization
        # =============================================================================
        # Initialize Rich Presence Manager
        log_spacing()
        try:
            rich_presence = RichPresenceManager(bot, "data")
            log_perfect_tree_section(
                "Rich Presence Manager Initialization",
                [
                    ("status", "✅ Rich Presence Manager initialized"),
                    ("ffmpeg_path", FFMPEG_PATH),
                    ("bot_user", str(bot.user)),
                ],
                "🎮",
            )
        except Exception as e:
            log_error_with_traceback("Error initializing Rich Presence Manager", e)
            # Continue without Rich Presence if it fails
            rich_presence = None

        # Initialize Audio Manager with environment defaults
        try:
            audio_manager = AudioManager(
                bot,
                FFMPEG_PATH,
                default_reciter=DEFAULT_RECITER,
                default_shuffle=DEFAULT_SHUFFLE,
                default_loop=DEFAULT_LOOP,
            )
            audio_manager.set_rich_presence(rich_presence)
            log_perfect_tree_section(
                "Audio Manager Initialization",
                [
                    ("status", "✅ Audio Manager initialized"),
                    ("ffmpeg_path", FFMPEG_PATH),
                    ("default_reciter", DEFAULT_RECITER),
                    ("default_shuffle", str(DEFAULT_SHUFFLE)),
                    ("default_loop", str(DEFAULT_LOOP)),
                    (
                        "rich_presence",
                        "✅ Connected" if rich_presence else "❌ Disabled",
                    ),
                ],
                "🎵",
            )
        except Exception as e:
            log_error_with_traceback("Error initializing Audio Manager", e)
            log_critical_error("Cannot continue without Audio Manager")
            await bot.close()
            return

        # =============================================================================
        # Configuration Validation
        # =============================================================================
        # Validate configuration before proceeding
        log_spacing()
        if not validate_configuration():
            log_critical_error("Bot configuration validation failed")
            await bot.close()
            return

        # =============================================================================
        # Discord Server and Channel Setup
        # =============================================================================
        # Get the guild and voice channel
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            log_critical_error(f"Guild with ID {GUILD_ID} not found")
            return

        channel = guild.get_channel(TARGET_CHANNEL_ID)
        if not channel:
            log_critical_error(f"Channel with ID {TARGET_CHANNEL_ID} not found")
            return

        # Validate channel type
        if not isinstance(channel, discord.VoiceChannel):
            log_critical_error(f"Channel {TARGET_CHANNEL_ID} is not a voice channel")
            return

        log_spacing()
        log_perfect_tree_section(
            "Voice Channel Connection Setup",
            [
                ("status", "🔄 Attempting voice connection"),
                ("channel_name", channel.name),
                ("channel_id", str(channel.id)),
                ("channel_type", "Voice Channel"),
                ("guild_name", guild.name),
                ("guild_id", str(guild.id)),
            ],
            "🎤",
        )

        # =============================================================================
        # Voice Connection with Retry Logic
        # =============================================================================
        # Connect to voice channel with retry logic
        max_retries = 3
        retry_delay = 10  # Longer delay to prevent rapid connection attempts
        voice_client = None

        for attempt in range(max_retries):
            try:
                # Clean up any existing voice connections first
                existing_voice_client = guild.voice_client
                if existing_voice_client:
                    log_perfect_tree_section(
                        f"Voice Cleanup - Attempt {attempt + 1}",
                        [
                            ("status", "🧹 Cleaning up existing voice connection"),
                            ("connection_state", "Disconnecting previous session"),
                            ("reason", "Ensuring clean connection"),
                        ],
                        "🧹",
                    )
                    try:
                        await existing_voice_client.disconnect(force=True)
                        await asyncio.sleep(
                            2
                        )  # Give Discord time to process disconnection
                    except Exception as cleanup_error:
                        log_perfect_tree_section(
                            f"Voice Cleanup Warning - Attempt {attempt + 1}",
                            [
                                ("status", "⚠️ Cleanup had issues but continuing"),
                                ("error", str(cleanup_error)),
                            ],
                            "⚠️",
                        )

                # Now establish fresh connection
                voice_client = await channel.connect(reconnect=False, timeout=60)
                log_perfect_tree_section(
                    f"Voice Connection - Attempt {attempt + 1}",
                    [
                        ("status", "✅ Fresh connection established"),
                        ("connection_type", "New"),
                        ("channel", channel.name),
                        ("timeout", "60s"),
                    ],
                    "🎤",
                )

                # =============================================================================
                # Audio System Setup
                # =============================================================================
                # Set up AudioManager with voice client
                try:
                    audio_manager.set_voice_client(voice_client)
                    log_perfect_tree_section(
                        "Audio System Setup",
                        [
                            ("status", "✅ Audio system configured"),
                            ("voice_client", "Connected"),
                            ("audio_manager", "Ready"),
                        ],
                        "🎵",
                    )
                except Exception as e:
                    log_error_with_traceback("Error setting up audio system", e)
                    raise  # Re-raise to trigger retry

                # =============================================================================
                # Control Panel Setup
                # =============================================================================
                # Set up control panel with AudioManager
                if PANEL_CHANNEL_ID != 0:
                    try:
                        await setup_control_panel(bot, PANEL_CHANNEL_ID, audio_manager)
                        log_perfect_tree_section(
                            "Control Panel Setup",
                            [
                                ("status", "✅ Control panel setup successful"),
                                ("panel_channel_id", str(PANEL_CHANNEL_ID)),
                                ("audio_manager", "Connected"),
                            ],
                            "🎛️",
                        )
                    except Exception as e:
                        log_error_with_traceback("Error setting up control panel", e)
                        # Control panel failure is not critical, continue without it

                # =============================================================================
                # Commands Setup (Slash Commands Only)
                # =============================================================================
                # Set up slash commands - prefix commands are disabled
                log_spacing()
                log_perfect_tree_section(
                    "Command System Setup",
                    [
                        ("status", "🔄 Setting up slash commands"),
                        (
                            "prefix_commands",
                            "⚠️ Disabled (only work when bot is mentioned)",
                        ),
                        ("slash_commands", "✅ Enabled"),
                    ],
                    "⚡",
                )

                # =============================================================================
                # Daily Verses System Setup - MUST BE BEFORE COMMAND SETUP
                # =============================================================================
                log_spacing()
                try:
                    if DAILY_VERSE_CHANNEL_ID:
                        await setup_daily_verses(bot, DAILY_VERSE_CHANNEL_ID)
                        log_perfect_tree_section(
                            "Daily Verses System",
                            [
                                ("status", "✅ Daily verses system started"),
                                ("channel_id", str(DAILY_VERSE_CHANNEL_ID)),
                                ("developer_id", str(DEVELOPER_ID)),
                                ("schedule", "Every 3 hours"),
                                ("features", "🤲 Auto dua reaction, bot thumbnail"),
                            ],
                            "📖",
                        )
                    else:
                        missing_vars = []
                        if not DAILY_VERSE_CHANNEL_ID:
                            missing_vars.append("DAILY_VERSE_CHANNEL_ID")
                        if not DEVELOPER_ID:
                            missing_vars.append("DEVELOPER_ID")

                        log_perfect_tree_section(
                            "Daily Verses System",
                            [
                                ("status", "⚠️ Daily verses system disabled"),
                                ("missing_vars", ", ".join(missing_vars)),
                                ("impact", "No automated verse sending"),
                            ],
                            "⚠️",
                        )
                except Exception as daily_verses_error:
                    log_error_with_traceback(
                        "Failed to start daily verses system", daily_verses_error
                    )
                    log_perfect_tree_section(
                        "Daily Verses System Warning",
                        [
                            ("status", "⚠️ Daily verses system failed to start"),
                            ("impact", "No automated verse sending"),
                            ("action", "Check logs for details"),
                        ],
                        "⚠️",
                    )

                # =============================================================================
                # Quiz System Setup - MUST BE AFTER DAILY VERSES SETUP
                # =============================================================================
                log_spacing()
                try:
                    if DAILY_VERSE_CHANNEL_ID:
                        await setup_quiz_system(bot, DAILY_VERSE_CHANNEL_ID)
                        log_perfect_tree_section(
                            "Quiz System",
                            [
                                ("status", "✅ Quiz system started"),
                                ("channel_id", str(DAILY_VERSE_CHANNEL_ID)),
                                ("developer_id", str(DEVELOPER_ID)),
                                ("schedule", "Every 3 hours"),
                                ("features", "🧠 Auto quiz reaction, bot thumbnail"),
                            ],
                            "🧠",
                        )
                    else:
                        missing_vars = []
                        if not DAILY_VERSE_CHANNEL_ID:
                            missing_vars.append("DAILY_VERSE_CHANNEL_ID")
                        if not DEVELOPER_ID:
                            missing_vars.append("DEVELOPER_ID")

                        log_perfect_tree_section(
                            "Quiz System",
                            [
                                ("status", "⚠️ Quiz system disabled"),
                                ("missing_vars", ", ".join(missing_vars)),
                                ("impact", "No automated quiz sending"),
                            ],
                            "⚠️",
                        )
                except Exception as quiz_error:
                    log_error_with_traceback("Failed to start quiz system", quiz_error)
                    log_perfect_tree_section(
                        "Quiz System Warning",
                        [
                            ("status", "⚠️ Quiz system failed to start"),
                            ("impact", "No automated quiz sending"),
                            ("action", "Check logs for details"),
                        ],
                        "⚠️",
                    )

                # =============================================================================
                # Slash Commands Setup - MUST BE AFTER DAILY VERSES SETUP
                # =============================================================================
                log_spacing()
                try:
                    from src.commands import (
                        setup_credits,
                        setup_interval,
                        setup_leaderboard,
                        setup_question,
                        setup_verse,
                    )

                    await setup_credits(bot)
                    await setup_interval(bot)
                    await setup_leaderboard(bot)
                    await setup_question(bot)
                    await setup_verse(bot)

                    # Sync commands to Discord with force sync
                    await bot.tree.sync()
                    log_perfect_tree_section(
                        "Slash Commands Sync",
                        [
                            ("status", "✅ Slash commands synced successfully"),
                            (
                                "available_commands",
                                "/credits, /interval, /leaderboard, /question, /verse",
                            ),
                            ("sync_method", "Discord Tree API"),
                        ],
                        "⚡",
                    )

                except Exception as e:
                    log_error_with_traceback("Error setting up slash commands", e)
                    # Command setup failure is not critical, continue without them

                # =============================================================================
                # Audio Playback Initialization
                # =============================================================================
                # Start playing audio using AudioManager
                try:
                    await audio_manager.start_playback()
                    
                    # Initialize Discord API Monitor
                    try:
                        discord_monitor = initialize_discord_monitor(bot)
                        log_perfect_tree_section(
                            "Discord API Monitor",
                            [
                                ("status", "✅ Discord API monitoring started"),
                                ("tracking", "API response times, rate limits, gateway health"),
                                ("data_retention", "24 hours"),
                                ("dashboard_integration", "✅ Web dashboard endpoints available"),
                                ("alerts", "Rate limit warnings, critical thresholds"),
                            ],
                            "🔗",
                        )
                    except Exception as e:
                        log_error_with_traceback("Error starting Discord API monitor", e)
                    
                    # Start audio monitoring system
                    try:
                        from utils.audio_manager import start_audio_monitoring_task
                        monitoring_task = await start_audio_monitoring_task(audio_manager)
                        log_perfect_tree_section(
                            "Audio Monitoring System",
                            [
                                ("status", "✅ Audio monitoring started"),
                                ("check_interval", "2 minutes"),
                                ("alert_system", "Discord notifications enabled"),
                                ("monitors", "Control panel, audio playback, voice connection"),
                            ],
                            "🔍",
                        )
                    except Exception as e:
                        log_error_with_traceback("Error starting audio monitoring", e)
                    
                    log_perfect_tree_section(
                        "Bot Initialization Complete",
                        [
                            ("status", "✅ Bot initialization successful"),
                            ("audio_playback", "Started"),
                            ("monitoring", "✅ Active"),
                            ("initialization_phase", "Complete"),
                        ],
                        "🎯",
                    )

                    # =============================================================================
                    # Start Automated Backup System
                    # =============================================================================
                    log_spacing()
                    try:
                        start_backup_scheduler()
                        log_perfect_tree_section(
                            "Automated Backup System",
                            [
                                ("status", "✅ EST hour-mark backup system started"),
                                (
                                    "schedule",
                                    "Every hour on EST clock (1:00, 2:00, etc.)",
                                ),
                                ("backup_format", "ZIP files with EST date/time names"),
                                ("backup_location", "backup/ directory"),
                                (
                                    "data_protection",
                                    "Enhanced with automated ZIP backups",
                                ),
                            ],
                            "💾",
                        )
                    except Exception as backup_error:
                        log_error_with_traceback(
                            "Failed to start backup scheduler", backup_error
                        )
                        log_perfect_tree_section(
                            "Backup System Warning",
                            [
                                ("status", "⚠️ Backup scheduler failed to start"),
                                ("impact", "Manual backups still available"),
                                ("data_protection", "Other protection layers active"),
                            ],
                            "⚠️",
                        )

                    # =============================================================================
                    # Check for Existing Users in Voice Channel
                    # =============================================================================
                    # Check if users are already in the Quran voice channel when bot starts
                    log_spacing()
                    try:
                        existing_users = [
                            member for member in channel.members if not member.bot
                        ]
                        if existing_users:
                            log_perfect_tree_section(
                                "Existing Users Detection",
                                [
                                    (
                                        "status",
                                        "🔍 Scanning voice channel for existing users",
                                    ),
                                    ("channel_name", channel.name),
                                    ("channel_id", str(channel.id)),
                                    (
                                        "users_found",
                                        f"{len(existing_users)} users already present",
                                    ),
                                    (
                                        "action",
                                        "Starting time tracking for all existing users",
                                    ),
                                ],
                                "👥",
                            )

                            # Start tracking time for existing users with beautiful logging
                            for member in existing_users:
                                track_voice_join(member.id)

                                # Beautiful tree log for each user that starts tracking
                                log_perfect_tree_section(
                                    "🎧 Listening Time Tracking Started",
                                    [
                                        ("user", f"👤 {member.display_name}"),
                                        ("user_id", f"🆔 {member.id}"),
                                        ("channel", f"🎵 {channel.name}"),
                                        (
                                            "status",
                                            "✅ Time tracking initiated from bot startup",
                                        ),
                                        (
                                            "tracking_start",
                                            f"⏰ {get_timestamp().strip('[]')}",
                                        ),
                                        (
                                            "session_type",
                                            "🔄 Continuation from existing presence",
                                        ),
                                        (
                                            "data_protection",
                                            "💾 Automatically saved to listening stats",
                                        ),
                                    ],
                                    "⏱️",
                                )

                            log_perfect_tree_section(
                                "Existing Users Tracking Summary",
                                [
                                    (
                                        "total_users",
                                        f"✅ {len(existing_users)} users now being tracked",
                                    ),
                                    ("channel", f"🎵 {channel.name}"),
                                    (
                                        "benefit",
                                        "🎯 No listening time lost during bot restart",
                                    ),
                                    (
                                        "persistence",
                                        "💾 Time tracking continues seamlessly",
                                    ),
                                ],
                                "📊",
                            )
                        else:
                            log_perfect_tree_section(
                                "Existing Users Detection",
                                [
                                    ("status", "ℹ️ Voice channel scan complete"),
                                    ("channel_name", channel.name),
                                    ("users_found", "0 users currently in channel"),
                                    ("ready_state", "🎯 Bot ready to track new users"),
                                ],
                                "👥",
                            )
                    except Exception as e:
                        log_error_with_traceback(
                            "Error checking for existing users in voice channel", e
                        )
                        # Continue with bot startup even if this fails

                    # =============================================================================
                    # Leaderboard Auto-Update System - DISABLED
                    # =============================================================================
                    # The leaderboard auto-update system has been disabled to prevent
                    # spamming the control panel channel. Users can still use /leaderboard
                    # command to view the leaderboard when needed.
                    log_spacing()
                    try:
                        log_perfect_tree_section(
                            "Leaderboard Auto-Update System",
                            [
                                ("status", "🚫 Disabled - Prevents panel channel spam"),
                                (
                                    "manual_command",
                                    "✅ /leaderboard command still available",
                                ),
                                ("reason", "Control panel channel is for panels only"),
                            ],
                            "🏆",
                        )
                    except Exception as e:
                        log_error_with_traceback(
                            "Error in leaderboard auto-update setup", e
                        )
                        # Continue with bot startup even if this fails

                    # =============================================================================
                    # Discord Logger Setup for VPS Monitoring
                    # =============================================================================
                    discord_logger = None
                    if LOGS_CHANNEL_ID != 0:
                        try:
                            discord_logger = setup_discord_logger(bot, LOGS_CHANNEL_ID, DASHBOARD_URL)
                            await discord_logger.initialize()
                            log_perfect_tree_section(
                                "Discord Logger Setup",
                                [
                                    ("status", "✅ Discord logger initialized"),
                                    ("log_channel_id", str(LOGS_CHANNEL_ID)),
                                    ("dashboard_url", DASHBOARD_URL if DASHBOARD_URL else "Not configured"),
                                    ("monitoring", "Errors, warnings, and system events"),
                                    ("rate_limit", "10 messages per minute per type"),
                                ],
                                "🔔",
                            )
                            

                            
                        except Exception as e:
                            log_error_with_traceback("Error setting up Discord logger", e)
                            log_perfect_tree_section(
                                "Discord Logger Setup",
                                [
                                    ("status", "❌ Discord logger failed to initialize"),
                                    ("error", str(e)),
                                    ("impact", "VPS monitoring will use console logs only"),
                                ],
                                "⚠️",
                            )
                    else:
                        log_perfect_tree_section(
                            "Discord Logger Setup",
                            [
                                ("status", "⚠️ Discord logger disabled"),
                                ("reason", "LOGS_CHANNEL_ID not configured"),
                                ("impact", "VPS monitoring will use console logs only"),
                            ],
                            "⚠️",
                        )

                    # =============================================================================
                    # Integrated Log Sync Manager
                    # =============================================================================
                    log_spacing()
                    try:
                        from src.utils.log_sync_manager import start_integrated_log_sync
                        
                        # Get VPS host from environment
                        vps_host = os.getenv("VPS_HOST")
                        
                        if vps_host:
                            log_sync_manager = await start_integrated_log_sync(
                                vps_host=vps_host,
                                sync_interval=30  # 30 seconds
                            )
                            
                            if log_sync_manager and log_sync_manager.is_running:
                                log_perfect_tree_section(
                                    "Integrated Log Sync",
                                    [
                                        ("status", "✅ Log sync integrated into bot"),
                                        ("vps_host", vps_host),
                                        ("sync_interval", "30 seconds"),
                                        ("auto_start", "✅ Starts with bot"),
                                        ("auto_stop", "✅ Stops with bot"),
                                    ],
                                    "📡",
                                )
                            else:
                                log_perfect_tree_section(
                                    "Integrated Log Sync",
                                    [
                                        ("status", "❌ Failed to start log sync"),
                                        ("vps_host", vps_host),
                                        ("impact", "Local logs won't sync automatically"),
                                    ],
                                    "📡",
                                )
                        else:
                            log_perfect_tree_section(
                                "Integrated Log Sync",
                                [
                                    ("status", "⚠️ Log sync disabled"),
                                    ("reason", "VPS_HOST not configured in .env"),
                                    ("impact", "Local logs won't sync automatically"),
                                    ("note", "Set VPS_HOST=root@your.vps.ip to enable"),
                                ],
                                "📡",
                            )
                    except Exception as e:
                        log_error_with_traceback("Error starting integrated log sync", e)
                        log_perfect_tree_section(
                            "Integrated Log Sync",
                            [
                                ("status", "❌ Log sync startup failed"),
                                ("error", str(e)),
                                ("impact", "Local logs won't sync automatically"),
                            ],
                            "📡",
                        )

                    # =============================================================================
                    # Bot Startup Complete
                    # =============================================================================
                    log_perfect_tree_section(
                        "Bot Initialization Complete",
                        [
                            ("status", "✅ Bot initialization successful"),
                            ("audio_playback", "Started"),
                            ("discord_logging", "✅ Enabled" if discord_logger and discord_logger.enabled else "❌ Disabled"),
                            ("vps_monitoring", "✅ Ready" if discord_logger and discord_logger.enabled else "Console only"),
                        ],
                        "🎯",
                    )

                except Exception as e:
                    log_error_with_traceback("Error starting audio playback", e)
                    raise  # Re-raise to trigger retry

                break  # Success, exit retry loop

            except discord.errors.ClientException as client_error:
                log_perfect_tree_section(
                    f"Connection Error - Attempt {attempt + 1}",
                    [
                        ("error_type", "Discord Client Exception"),
                        ("error_message", str(client_error)),
                        ("attempt", f"{attempt + 1}/{max_retries}"),
                    ],
                    "❌",
                )

                # Handle different error types
                if "already connected" in str(client_error).lower():
                    # Use existing connection
                    voice_client = guild.voice_client
                    if voice_client and voice_client.is_connected():
                        break
                elif "4006" in str(client_error):
                    # Session invalid - force disconnect and retry
                    try:
                        if guild.voice_client:
                            await guild.voice_client.disconnect(force=True)
                            await asyncio.sleep(3)
                    except:
                        pass

                if attempt < max_retries - 1:
                    log_perfect_tree_section(
                        "Connection Retry",
                        [
                            ("status", f"Waiting {retry_delay} seconds before retry"),
                            ("next_attempt", f"{attempt + 2}/{max_retries}"),
                            ("retry_delay", f"{retry_delay}s"),
                        ],
                        "🔄",
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    log_discord_error(
                        "on_ready", client_error, GUILD_ID, TARGET_CHANNEL_ID
                    )
                    log_perfect_tree_section(
                        "Connection Failed",
                        [
                            ("status", "❌ All connection attempts failed"),
                            ("total_attempts", max_retries),
                            ("final_result", "Bot startup failed"),
                        ],
                        "💥",
                    )
                    return

            except asyncio.TimeoutError:
                log_perfect_tree_section(
                    f"Connection Error - Attempt {attempt + 1}",
                    [
                        ("error_type", "Connection Timeout"),
                        ("timeout_duration", "60s"),
                        ("attempt", f"{attempt + 1}/{max_retries}"),
                    ],
                    "❌",
                )

            except Exception as other_error:
                log_perfect_tree_section(
                    f"Connection Error - Attempt {attempt + 1}",
                    [
                        ("error_type", type(other_error).__name__),
                        ("error_message", str(other_error)),
                        ("attempt", f"{attempt + 1}/{max_retries}"),
                    ],
                    "❌",
                )

                if attempt < max_retries - 1:
                    log_perfect_tree_section(
                        "Connection Retry",
                        [
                            ("status", f"Waiting {retry_delay} seconds before retry"),
                            ("next_attempt", f"{attempt + 2}/{max_retries}"),
                            ("retry_delay", f"{retry_delay}s"),
                        ],
                        "🔄",
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    log_discord_error(
                        "on_ready", other_error, GUILD_ID, TARGET_CHANNEL_ID
                    )
                    log_perfect_tree_section(
                        "Connection Failed",
                        [
                            ("status", "❌ All connection attempts failed"),
                            ("total_attempts", max_retries),
                            ("final_result", "Bot startup failed"),
                        ],
                        "💥",
                    )
                    return

    except Exception as e:
        log_critical_error("Fatal error in on_ready event", e)
        
        # Send critical error to Discord if logger is available
        discord_logger = get_discord_logger()
        if discord_logger:
            try:
                await discord_logger.log_critical_error(
                    "Fatal error in bot startup",
                    e,
                    {
                        "Event": "on_ready",
                        "Impact": "Bot startup failed",
                        "Action": "Attempting graceful shutdown"
                    }
                )
            except:
                pass  # Don't let Discord logging errors crash the bot further
        
        # Attempt graceful shutdown on critical error
        try:
            await bot.close()
        except:
            pass  # Ignore errors during emergency shutdown


# =============================================================================
# Audio Playback Functions
# =============================================================================
async def play_audio(voice_client):
    """Play audio files from the audio folder with Rich Presence"""
    global rich_presence

    try:
        # Get all mp3 files and sort them
        audio_files = sorted(glob.glob(os.path.join(AUDIO_FOLDER, "*.mp3")))

        if not audio_files:
            log_perfect_tree_section(
                "Audio Playback Started",
                [
                    ("audio_folder", AUDIO_FOLDER),
                    ("ffmpeg_path", FFMPEG_PATH),
                    ("error", "No audio files found!"),
                ],
                "🎵",
            )
            return

        log_perfect_tree_section(
            "Audio Playback Started",
            [
                ("audio_folder", AUDIO_FOLDER),
                ("ffmpeg_path", FFMPEG_PATH),
                ("total_files", len(audio_files)),
                ("first_file", os.path.basename(audio_files[0])),
            ],
            "🎵",
        )

        # Play each file
        for i, audio_file in enumerate(audio_files, 1):
            try:
                if not voice_client.is_connected():
                    log_warning_with_context(
                        "Voice client disconnected, stopping playback",
                        f"File {i}/{len(audio_files)}",
                    )
                    break

                filename = os.path.basename(audio_file)

                # Extract Surah number from filename (assumes format like "001.mp3" or "1.mp3")
                try:
                    surah_number = int(filename.split(".")[0])
                    if validate_surah_number(surah_number):
                        surah_display = get_surah_display(surah_number)
                        surah_info = get_surah_info(surah_number)
                        now_playing = format_now_playing(surah_info, "Saad Al Ghamdi")

                        log_progress(i, len(audio_files))

                        # Log the beautiful now playing format
                        now_playing_items = [
                            ("surah", surah_display),
                            ("progress", f"{i}/{len(audio_files)}"),
                        ]
                        for line in now_playing.split("\n"):
                            if line.strip():
                                now_playing_items.append(("info", line.strip()))

                        log_perfect_tree_section(
                            "Now Playing",
                            now_playing_items,
                            "🎵",
                        )

                        # Start Rich Presence tracking
                        if rich_presence:
                            from src.utils.surah_mapper import get_surah_name

                            surah_name = get_surah_name(surah_number)

                            rich_presence.update_presence_with_template(
                                "listening",
                                {
                                    "surah": surah_name,
                                    "verse": "1",
                                    "total": "Unknown",
                                    "reciter": "Saad Al Ghamdi",
                                },
                            )

                    else:
                        # Fallback to filename if not a valid Surah number
                        log_progress(i, len(audio_files))
                        log_perfect_tree_section(
                            "Now Playing",
                            [
                                ("file", filename),
                                ("progress", f"{i}/{len(audio_files)}"),
                            ],
                            "🎵",
                        )

                except (ValueError, IndexError):
                    # Fallback to filename if we can't extract Surah number
                    log_progress(i, len(audio_files))
                    log_perfect_tree_section(
                        "Now Playing",
                        [
                            ("file", filename),
                            ("progress", f"{i}/{len(audio_files)}"),
                        ],
                        "🎵",
                    )

                # Create FFmpeg audio source
                source = discord.FFmpegPCMAudio(
                    audio_file, executable=FFMPEG_PATH, options="-vn"
                )

                # Play the audio
                voice_client.play(source)

                # Wait for playback to finish
                while voice_client.is_playing():
                    await asyncio.sleep(1)

                # Stop Rich Presence for this track
                if rich_presence:
                    rich_presence.clear_presence()

            except Exception as e:
                log_error_with_traceback(f"Error playing {filename}", e)
                # Stop Rich Presence on error
                if rich_presence:
                    rich_presence.clear_presence()
                continue

        log_perfect_tree_section(
            "Audio Playback - Complete",
            [
                ("status", "Finished playing all audio files"),
            ],
            "✅",
        )

    except Exception as e:
        log_async_error("play_audio", e, f"Audio folder: {AUDIO_FOLDER}")
        # Stop Rich Presence on error
        if rich_presence:
            rich_presence.clear_presence()


# =============================================================================
# Voice State Event Handlers
# =============================================================================
@bot.event
async def on_voice_state_update(member, before, after):
    """
    Handle voice state changes with intelligent reconnection logic and role management.

    Monitors voice state changes and implements smart reconnection when the bot
    is disconnected from voice channels. Also manages panel access roles for users
    joining/leaving voice channels.

    Features:
    - Detects bot disconnection from voice channels
    - Implements delay to prevent rapid reconnection loops
    - Automatically restarts audio playback after reconnection
    - Manages panel access roles for voice channel members
    - Comprehensive logging for troubleshooting connection issues

    Args:
        member: Discord member whose voice state changed
        before: Previous voice state
        after: New voice state
    """
    global rich_presence, audio_manager

    try:
        # =============================================================================
        # Bot Voice State Handling (Reconnection Logic)
        # =============================================================================
        if member == bot.user:
            # Detect disconnection (was in channel, now not in channel)
            if before.channel and not after.channel:
                # Stop AudioManager when disconnected to prevent resource leaks
                if audio_manager:
                    try:
                        await audio_manager.stop_playback()
                        audio_cleanup_status = "✅ Audio playback stopped"
                    except Exception as e:
                        log_error_with_traceback(
                            "Error stopping audio during disconnect", e
                        )
                        audio_cleanup_status = "❌ Audio cleanup failed"
                else:
                    audio_cleanup_status = "No audio manager active"

                log_perfect_tree_section(
                    "Bot Disconnected",
                    [
                        ("member", member.display_name),
                        (
                            "before_channel",
                            before.channel.name if before.channel else "None",
                        ),
                        (
                            "after_channel",
                            after.channel.name if after.channel else "None",
                        ),
                        ("audio_cleanup", audio_cleanup_status),
                        (
                            "rich_presence",
                            "✅ Stopped" if rich_presence else "Not active",
                        ),
                    ],
                    "⚠️",
                )

                # Smart reconnection with delay to prevent loops
                guild = before.channel.guild
                channel = before.channel

                # Add delay to prevent rapid reconnection attempts
                log_perfect_tree_section(
                    "Reconnection Preparation",
                    [
                        ("reconnection", "Waiting 5 seconds before reconnection"),
                    ],
                    "🔄",
                )
                await asyncio.sleep(5)

                try:
                    voice_client = await channel.connect(reconnect=False, timeout=60)

                    # Use intelligent auto-restart logic
                    await auto_restart_audio_playback(voice_client)

                    log_perfect_tree_section(
                        "Reconnection Success",
                        [
                            ("reconnect_attempt", f"Reconnecting due to disconnection"),
                            ("reconnect", f"✅ Reconnected to {channel.name}"),
                            (
                                "audio_restart",
                                "✅ Audio playback intelligently restarted",
                            ),
                        ],
                        "✅",
                    )

                except discord.errors.ClientException as e:
                    if "already connected" in str(e).lower():
                        log_perfect_tree_section(
                            "Reconnection Info",
                            [
                                ("reconnect_info", "Already connected to voice"),
                            ],
                            "ℹ️",
                        )
                    else:
                        log_error_with_traceback(
                            "Discord client error during reconnection", e
                        )
                        log_perfect_tree_section(
                            "Reconnection Failed",
                            [
                                ("reconnect_status", "❌ Reconnection failed"),
                            ],
                            "❌",
                        )

                except asyncio.TimeoutError:
                    log_error_with_traceback(
                        "Reconnection timeout", TimeoutError("Connection timeout")
                    )
                    log_perfect_tree_section(
                        "Reconnection Timeout",
                        [
                            ("reconnect_status", "❌ Reconnection timed out"),
                        ],
                        "❌",
                    )

                except Exception as e:
                    log_error_with_traceback("Reconnection failed", e)
                    log_perfect_tree_section(
                        "Reconnection Error",
                        [
                            ("reconnect_status", "❌ Will retry on next disconnect"),
                        ],
                        "❌",
                    )

            # Handle channel switches (moved from one channel to another)
            elif before.channel and after.channel and before.channel != after.channel:
                log_perfect_tree_section(
                    "Bot Channel Switch",
                    [
                        (
                            "channel_switch",
                            f"Moved from {before.channel.name} to {after.channel.name}",
                        ),
                    ],
                    "🔄",
                )

                # Update audio manager with new voice client if needed
                if audio_manager and hasattr(after.channel.guild, "voice_client"):
                    voice_client = after.channel.guild.voice_client
                    if voice_client:
                        audio_manager.set_voice_client(voice_client)
            return

        # =============================================================================
        # User Voice State Handling (Logging & Role Management)
        # =============================================================================

        # Check if this voice state change involves the Quran voice channel
        quran_channel_involved = (
            before.channel and before.channel.id == TARGET_CHANNEL_ID
        ) or (after.channel and after.channel.id == TARGET_CHANNEL_ID)

        # Only log and process role changes if the Quran voice channel is involved
        if quran_channel_involved:
            # User joined the Quran voice channel (from no VC or different VC)
            if (
                not before.channel
                and after.channel
                and after.channel.id == TARGET_CHANNEL_ID
            ):
                # Track listening time - user joined
                track_voice_join(member.id)

                # Cache user info for dashboard display
                try:
                    from src.utils.user_cache import cache_user_from_member
                    cache_user_from_member(member)
                except Exception:
                    pass  # Fail silently to not interfere with voice operations

                log_voice_activity_tree(
                    member.display_name,
                    "join",
                    {
                        "channel_name": after.channel.name,
                        "channel_id": after.channel.id,
                        "previous_channel": "None",
                        "activity": "Joined Quran voice channel",
                        "timestamp": f"{get_timestamp().strip('[]')}",
                    },
                )

                # Log to Discord with user profile picture
                discord_logger = get_discord_logger()
                if discord_logger:
                    try:
                        user_avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                        await discord_logger.log_user_interaction(
                            "voice_join",
                            member.display_name,
                            member.id,
                            f"joined the Quran voice channel",
                            {
                                "Channel": after.channel.name,
                                "Channel ID": str(after.channel.id),
                                "Previous Channel": "None",
                                "Activity": "Joined Quran voice channel"
                            },
                            user_avatar_url
                        )
                    except:
                        pass

            # User joined Quran VC from a different voice channel
            elif (
                before.channel
                and before.channel.id != TARGET_CHANNEL_ID
                and after.channel
                and after.channel.id == TARGET_CHANNEL_ID
            ):
                # Track listening time - user joined
                track_voice_join(member.id)

                log_voice_activity_tree(
                    member.display_name,
                    "move",
                    {
                        "channel_name": after.channel.name,
                        "channel_id": after.channel.id,
                        "previous_channel": before.channel.name,
                        "activity": "Moved to Quran voice channel",
                        "timestamp": f"{get_timestamp().strip('[]')}",
                    },
                )

                # Log to Discord with user profile picture
                discord_logger = get_discord_logger()
                if discord_logger:
                    try:
                        user_avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                        await discord_logger.log_user_interaction(
                            "voice_move",
                            member.display_name,
                            member.id,
                            f"moved to the Quran voice channel from {before.channel.name}",
                            {
                                "Channel": after.channel.name,
                                "Channel ID": str(after.channel.id),
                                "Previous Channel": before.channel.name,
                                "Activity": "Moved to Quran voice channel"
                            },
                            user_avatar_url
                        )
                    except:
                        pass

            # User left the Quran voice channel (to no VC or different VC)
            elif (
                before.channel
                and before.channel.id == TARGET_CHANNEL_ID
                and not after.channel
            ):
                # Track listening time - user left
                track_voice_leave(member.id)

                log_voice_activity_tree(
                    member.display_name,
                    "leave",
                    {
                        "channel_name": before.channel.name,
                        "channel_id": before.channel.id,
                        "new_channel": "None",
                        "activity": "Left Quran voice channel",
                        "timestamp": f"{get_timestamp().strip('[]')}",
                    },
                )

                # Log to Discord with user profile picture
                discord_logger = get_discord_logger()
                if discord_logger:
                    try:
                        user_avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                        await discord_logger.log_user_interaction(
                            "voice_leave",
                            member.display_name,
                            member.id,
                            f"left the Quran voice channel",
                            {
                                "Channel": before.channel.name,
                                "Channel ID": str(before.channel.id),
                                "New Channel": "None",
                                "Activity": "Left Quran voice channel"
                            },
                            user_avatar_url
                        )
                    except:
                        pass

            # User left Quran VC to a different voice channel
            elif (
                before.channel
                and before.channel.id == TARGET_CHANNEL_ID
                and after.channel
                and after.channel.id != TARGET_CHANNEL_ID
            ):
                # Track listening time - user left
                track_voice_leave(member.id)

                log_voice_activity_tree(
                    member.display_name,
                    "move",
                    {
                        "previous_channel": before.channel.name,
                        "channel_name": after.channel.name,
                        "channel_id": after.channel.id,
                        "activity": "Left Quran voice channel for another channel",
                        "timestamp": f"{get_timestamp().strip('[]')}",
                    },
                )

                # Log to Discord with user profile picture
                discord_logger = get_discord_logger()
                if discord_logger:
                    try:
                        user_avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                        await discord_logger.log_user_interaction(
                            "voice_move",
                            member.display_name,
                            member.id,
                            f"left the Quran voice channel for {after.channel.name}",
                            {
                                "Previous Channel": before.channel.name,
                                "New Channel": after.channel.name,
                                "Channel ID": str(after.channel.id),
                                "Activity": "Left Quran voice channel for another channel"
                            },
                            user_avatar_url
                        )
                    except:
                        pass

            # User muted/unmuted or deafened/undeafened in the Quran voice channel
            elif (
                before.channel
                and after.channel
                and before.channel.id == TARGET_CHANNEL_ID
                and after.channel.id == TARGET_CHANNEL_ID
            ):
                status_changes = []

                if before.self_mute != after.self_mute:
                    activity_type = "mute" if after.self_mute else "unmute"
                    log_voice_activity_tree(
                        member.display_name,
                        activity_type,
                        {
                            "channel_name": after.channel.name,
                            "channel_id": after.channel.id,
                            "status_change": f"{'Muted' if after.self_mute else 'Unmuted'}",
                            "timestamp": f"{get_timestamp().strip('[]')}",
                        },
                    )

                    # Log to Discord with user profile picture
                    discord_logger = get_discord_logger()
                    if discord_logger:
                        try:
                            user_avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                            await discord_logger.log_user_interaction(
                                f"voice_{activity_type}",
                                member.display_name,
                                member.id,
                                f"{'muted' if after.self_mute else 'unmuted'} themselves in the Quran voice channel",
                                {
                                    "Channel": after.channel.name,
                                    "Channel ID": str(after.channel.id),
                                    "Status Change": f"{'Muted' if after.self_mute else 'Unmuted'}",
                                    "Type": "Self"
                                },
                                user_avatar_url
                            )
                        except:
                            pass

                if before.self_deaf != after.self_deaf:
                    activity_type = "deafen" if after.self_deaf else "undeafen"
                    log_voice_activity_tree(
                        member.display_name,
                        activity_type,
                        {
                            "channel_name": after.channel.name,
                            "channel_id": after.channel.id,
                            "status_change": f"{'Deafened' if after.self_deaf else 'Undeafened'}",
                            "timestamp": f"{get_timestamp().strip('[]')}",
                        },
                    )

                    # Log to Discord with user profile picture
                    discord_logger = get_discord_logger()
                    if discord_logger:
                        try:
                            user_avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                            await discord_logger.log_user_interaction(
                                f"voice_{activity_type}",
                                member.display_name,
                                member.id,
                                f"{'deafened' if after.self_deaf else 'undeafened'} themselves in the Quran voice channel",
                                {
                                    "Channel": after.channel.name,
                                    "Channel ID": str(after.channel.id),
                                    "Status Change": f"{'Deafened' if after.self_deaf else 'Undeafened'}",
                                    "Type": "Self"
                                },
                                user_avatar_url
                            )
                        except:
                            pass

                # Log server-side mute/deafen changes
                if before.mute != after.mute:
                    log_voice_activity_tree(
                        member.display_name,
                        "mute" if after.mute else "unmute",
                        {
                            "channel_name": after.channel.name,
                            "channel_id": after.channel.id,
                            "status_change": f"Server {'Muted' if after.mute else 'Unmuted'}",
                            "initiated_by": "Server",
                            "timestamp": f"{get_timestamp().strip('[]')}",
                        },
                    )

                if before.deaf != after.deaf:
                    log_voice_activity_tree(
                        member.display_name,
                        "deafen" if after.deaf else "undeafen",
                        {
                            "channel_name": after.channel.name,
                            "channel_id": after.channel.id,
                            "status_change": f"Server {'Deafened' if after.deaf else 'Undeafened'}",
                            "initiated_by": "Server",
                            "timestamp": f"{get_timestamp().strip('[]')}",
                        },
                    )

        # =============================================================================
        # Panel Access Role Management
        # =============================================================================

        # Skip if panel access role management is disabled
        if PANEL_ACCESS_ROLE_ID == 0:
            return

        # Get the panel access role
        guild = member.guild
        panel_role = guild.get_role(PANEL_ACCESS_ROLE_ID)

        if not panel_role:
            log_perfect_tree_section(
                "Panel Access Role - Not Found",
                [
                    (
                        "role_error",
                        f"Panel access role {PANEL_ACCESS_ROLE_ID} not found",
                    ),
                ],
                "❌",
            )
            return

        # Check if user joined a voice channel (wasn't in VC, now is)
        if not before.channel and after.channel:
            # Only assign role if they joined the Quran voice channel specifically
            if after.channel.id == TARGET_CHANNEL_ID:
                await _assign_panel_access_role(member, panel_role, after.channel)

        # Check if user left all voice channels (was in VC, now isn't)
        elif before.channel and not after.channel:
            # Only remove role if they left the Quran voice channel
            if before.channel.id == TARGET_CHANNEL_ID:
                await _remove_panel_access_role(member, panel_role, before.channel)

        # Check if user moved between voice channels
        elif before.channel and after.channel and before.channel != after.channel:
            # If they left the Quran voice channel, remove role
            if before.channel.id == TARGET_CHANNEL_ID:
                await _remove_panel_access_role(member, panel_role, before.channel)

            # If they joined the Quran voice channel, assign role
            if after.channel.id == TARGET_CHANNEL_ID:
                await _assign_panel_access_role(member, panel_role, after.channel)

    except Exception as e:
        log_discord_error("on_voice_state_update", e, GUILD_ID)


async def _assign_panel_access_role(member, panel_role, channel):
    """
    Assign the panel access role to a user who joined a voice channel.

    Args:
        member: Discord member to assign role to
        panel_role: The panel access role object
        channel: Voice channel the user joined
    """
    try:
        # Check if user already has the role
        if panel_role in member.roles:
            log_perfect_tree_section(
                "Panel Access Role - Already Assigned",
                [
                    (
                        "role_skip",
                        f"{member.display_name} already has panel access role",
                    ),
                ],
                "ℹ️",
            )
            return

        # Log the assignment attempt
        log_perfect_tree_section(
            f"Panel Access Role Assignment - {member.display_name}",
            [
                ("user", member.display_name),
                ("user_id", str(member.id)),
                ("channel", channel.name),
                ("channel_id", str(channel.id)),
                ("role", panel_role.name),
                ("role_id", str(panel_role.id)),
                ("action", "ATTEMPTING"),
                ("reason", "Joined voice channel"),
                ("status", "🔄 In progress..."),
            ],
            "🎤",
        )

        # Assign the role with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await member.add_roles(
                    panel_role, reason="Joined voice channel for panel access"
                )
                
                # Verify the role was actually assigned
                # Refresh member data by fetching from guild
                member = await member.guild.fetch_member(member.id)
                if panel_role in member.roles:
                    log_perfect_tree_section(
                        f"Panel Access Role Assignment Success - {member.display_name}",
                        [
                            ("user", member.display_name),
                            ("user_id", str(member.id)),
                            ("action", "GRANTED"),
                            ("attempt", f"{attempt + 1}/{max_retries}"),
                            ("status", "✅ SUCCESS"),
                        ],
                        "✅",
                    )
                    return
                else:
                    # Role assignment appeared to succeed but role not found
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retry
                        continue
                    else:
                        raise Exception("Role assignment succeeded but role not found on member")
                        
            except discord.HTTPException as http_error:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    log_perfect_tree_section(
                        f"Panel Access Role - Retry {attempt + 1}",
                        [
                            ("user", member.display_name),
                            ("error", str(http_error)),
                            ("retry_in", f"{wait_time}s"),
                            ("attempt", f"{attempt + 1}/{max_retries}"),
                        ],
                        "🔄",
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise http_error

    except discord.Forbidden:
        log_perfect_tree_section(
            "Panel Access Role - Permission Error",
            [
                (
                    "role_error",
                    f"❌ No permission to assign panel access role to {member.display_name}",
                ),
                ("user_id", str(member.id)),
                ("role_id", str(panel_role.id)),
            ],
            "❌",
        )
    except discord.HTTPException as e:
        log_perfect_tree_section(
            "Panel Access Role - HTTP Error",
            [
                ("user", member.display_name),
                ("error", str(e)),
                ("status", "❌ FAILED after retries"),
            ],
            "❌",
        )
    except Exception as e:
        log_perfect_tree_section(
            "Panel Access Role - Unexpected Error",
            [
                ("user", member.display_name),
                ("error", str(e)),
                ("status", "❌ FAILED"),
            ],
            "❌",
        )


async def _remove_panel_access_role(member, panel_role, channel):
    """
    Remove the panel access role from a user who left all voice channels.

    Args:
        member: Discord member to remove role from
        panel_role: The panel access role object
        channel: Voice channel the user left
    """
    try:
        # Refresh member data to get current roles
        # Fetch fresh member data from guild
        member = await member.guild.fetch_member(member.id)
        
        # Check if user has the role
        if panel_role not in member.roles:
            log_perfect_tree_section(
                "Panel Access Role - Not Assigned",
                [
                    ("user", member.display_name),
                    ("user_id", str(member.id)),
                    ("role_skip", f"{member.display_name} doesn't have panel access role"),
                    ("reason", "Role was never assigned or already removed"),
                    ("channel_left", channel.name),
                ],
                "ℹ️",
            )
            return

        # Log the removal attempt
        log_perfect_tree_section(
            f"Panel Access Role Removal - {member.display_name}",
            [
                ("user", member.display_name),
                ("user_id", str(member.id)),
                ("channel", channel.name),
                ("action", "ATTEMPTING"),
                ("status", "🔄 Removing role..."),
            ],
            "👋",
        )

        # Remove the role with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await member.remove_roles(
                    panel_role, reason="Left voice channel, removing panel access"
                )
                
                # Verify the role was actually removed
                # Refresh member data by fetching from guild
                member = await member.guild.fetch_member(member.id)
                if panel_role not in member.roles:
                    log_perfect_tree_section(
                        f"Panel Access Role Removal Success - {member.display_name}",
                        [
                            ("user", member.display_name),
                            ("user_id", str(member.id)),
                            ("channel", channel.name),
                            ("channel_id", str(channel.id)),
                            ("role", panel_role.name),
                            ("role_id", str(panel_role.id)),
                            ("action", "REVOKED"),
                            ("reason", "Left voice channel"),
                            ("attempt", f"{attempt + 1}/{max_retries}"),
                            ("status", "✅ SUCCESS"),
                        ],
                        "✅",
                    )
                    return
                else:
                    # Role removal appeared to succeed but role still found
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retry
                        continue
                    else:
                        raise Exception("Role removal succeeded but role still found on member")
                        
            except discord.HTTPException as http_error:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    log_perfect_tree_section(
                        f"Panel Access Role Removal - Retry {attempt + 1}",
                        [
                            ("user", member.display_name),
                            ("error", str(http_error)),
                            ("retry_in", f"{wait_time}s"),
                            ("attempt", f"{attempt + 1}/{max_retries}"),
                        ],
                        "🔄",
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise http_error

    except discord.Forbidden:
        log_perfect_tree_section(
            "Panel Access Role - Permission Error",
            [
                ("user", member.display_name),
                ("user_id", str(member.id)),
                ("role_error", f"❌ No permission to remove panel access role from {member.display_name}"),
                ("role_id", str(panel_role.id)),
            ],
            "❌",
        )
    except discord.HTTPException as e:
        log_perfect_tree_section(
            "Panel Access Role Removal - HTTP Error",
            [
                ("user", member.display_name),
                ("error", str(e)),
                ("status", "❌ FAILED after retries"),
            ],
            "❌",
        )
    except Exception as e:
        log_perfect_tree_section(
            "Panel Access Role Removal - Unexpected Error",
            [
                ("user", member.display_name),
                ("error", str(e)),
                ("status", "❌ FAILED"),
            ],
            "❌",
        )


# =============================================================================
# Discord Error Event Handlers
# =============================================================================
@bot.event
async def on_error(event, *args, **kwargs):
    """
    Handle Discord errors with comprehensive error categorization and recovery.

    Provides centralized error handling for all Discord events with specific
    handling for common error types and automatic recovery mechanisms where
    possible.

    Features:
    - Specific handling for voice connection errors (4006, 4014, etc.)
    - Automatic reconnection for recoverable errors
    - Detailed error logging with context information
    - Graceful degradation for non-critical errors

    Args:
        event: Name of the Discord event that caused the error
        *args: Event arguments
        **kwargs: Event keyword arguments
    """
    try:
        # Get the current exception information
        exc_type, exc_value, exc_traceback = sys.exc_info()

        if exc_value:
            # =============================================================================
            # Voice Connection Error Handling
            # =============================================================================
            if isinstance(exc_value, discord.errors.ConnectionClosed):
                await _handle_voice_connection_error(exc_value, event, kwargs)

            # =============================================================================
            # HTTP Error Handling
            # =============================================================================
            elif isinstance(exc_value, discord.errors.HTTPException):
                await _handle_http_error(exc_value, event, kwargs)

            # =============================================================================
            # Generic Error Handling
            # =============================================================================
            else:
                log_discord_error(
                    f"discord_event_{event}",
                    exc_value,
                    kwargs.get("guild_id"),
                    kwargs.get("channel_id"),
                )
                
                # Send error to Discord logger
                discord_logger = get_discord_logger()
                if discord_logger:
                    try:
                        await discord_logger.log_error(
                            f"Discord event error: {event}",
                            exc_value,
                            {
                                "Event": event,
                                "Guild ID": str(kwargs.get("guild_id", "Unknown")),
                                "Channel ID": str(kwargs.get("channel_id", "Unknown")),
                                "Error Type": type(exc_value).__name__
                            }
                        )
                    except:
                        pass  # Don't let Discord logging errors crash the bot further
        else:
            log_error_with_traceback(f"Unknown error in Discord event: {event}")
            
            # Send unknown error to Discord logger
            discord_logger = get_discord_logger()
            if discord_logger:
                try:
                    await discord_logger.log_error(
                        f"Unknown error in Discord event: {event}",
                        None,
                        {
                            "Event": event,
                            "Error Type": "Unknown"
                        }
                    )
                except:
                    pass

    except Exception as e:
        log_critical_error("Error in error handler", e)
        
        # Send critical error to Discord logger
        discord_logger = get_discord_logger()
        if discord_logger:
            try:
                await discord_logger.log_critical_error(
                    "Error in error handler",
                    e,
                    {
                        "Context": "Main error handler failed",
                        "Impact": "Error handling compromised"
                    }
                )
            except:
                pass


async def _handle_voice_connection_error(exc_value, event, kwargs):
    """
    Handle voice connection specific errors with appropriate recovery actions.

    Args:
        exc_value: The ConnectionClosed exception
        event: Event name that caused the error
        kwargs: Event context information
    """
    global audio_manager

    try:
        error_code = getattr(exc_value, "code", None)

        if error_code == 4006:
            # Voice server not responding
            log_critical_error(
                "Voice server not responding (4006). Attempting reconnect."
            )
            await _attempt_voice_reconnection("Voice server error 4006")

        elif error_code == 4014:
            # Disconnected from voice channel
            log_perfect_tree_section(
                "Voice Connection Error - Disconnected",
                [
                    ("voice_error", "Disconnected from voice channel (4014)"),
                ],
                "⚠️",
            )
            await _attempt_voice_reconnection("Voice disconnection 4014")

        else:
            # Other connection errors
            log_error_with_traceback(f"Voice connection error {error_code}", exc_value)

    except Exception as e:
        log_error_with_traceback("Error handling voice connection error", e)


async def _handle_http_error(exc_value, event, kwargs):
    """
    Handle HTTP errors from Discord API with appropriate responses.

    Args:
        exc_value: The HTTPException
        event: Event name that caused the error
        kwargs: Event context information
    """
    try:
        status_code = getattr(exc_value, "status", None)

        if status_code == 429:
            # Rate limiting - Enhanced with Discord notifications
            retry_after = getattr(exc_value, "retry_after", 60)
            
            log_perfect_tree_section(
                "Discord API - Rate Limited",
                [
                    ("rate_limit", "🚨 Discord API rate limit encountered"),
                    ("event", f"Event: {event}"),
                    ("retry_after", f"Waiting {retry_after} seconds"),
                    ("status_code", "429"),
                    ("timestamp", get_timestamp().strip("[]")),
                ],
                "⏳",
            )
            
            # Send Discord notification about rate limiting
            discord_logger = get_discord_logger()
            if discord_logger:
                try:
                    # Create context information
                    context = {
                        "Status Code": "429",
                        "Timestamp": get_timestamp().strip("[]"),
                        "Error Message": str(exc_value)
                    }
                    
                    # Add additional context from kwargs if available
                    if kwargs:
                        for key, value in kwargs.items():
                            if len(str(value)) < 100:
                                context[f"Context {key.title()}"] = str(value)
                    
                    # Extract endpoint from exception if available
                    endpoint = getattr(exc_value, 'response', {}).get('url', None)
                    if hasattr(exc_value, 'response') and hasattr(exc_value.response, 'url'):
                        endpoint = str(exc_value.response.url)
                    
                    await discord_logger.log_rate_limit(
                        event=event,
                        retry_after=retry_after,
                        endpoint=endpoint,
                        context=context
                    )
                except Exception as log_error:
                    # Don't let Discord logging errors interfere with error handling
                    log_error_with_traceback("Failed to send rate limit notification to Discord", log_error)

        elif status_code == 403:
            # Forbidden - permissions issue
            log_perfect_tree_section(
                "Discord API - Permissions Error",
                [
                    ("permissions_error", "Bot lacks required permissions"),
                    ("event", f"Event: {event}"),
                    ("status_code", "403"),
                ],
                "❌",
            )
            
            # Send Discord notification for permissions issues
            discord_logger = get_discord_logger()
            if discord_logger:
                try:
                    context = {
                        "Event": event,
                        "Status Code": "403", 
                        "Error Message": str(exc_value)
                    }
                    
                    await discord_logger.log_error(
                        f"❌ **Permissions Error**\n\n"
                        f"The bot lacks required permissions for the `{event}` event. "
                        f"Please check bot permissions in the server settings.",
                        exc_value,
                        context
                    )
                except Exception as log_error:
                    log_error_with_traceback("Failed to send permissions error notification to Discord", log_error)

        elif status_code == 404:
            # Not found - channel/guild may have been deleted
            log_perfect_tree_section(
                "Discord API - Not Found",
                [
                    ("not_found", "Discord resource not found (deleted?)"),
                    ("event", f"Event: {event}"),
                    ("status_code", "404"),
                ],
                "❓",
            )

        else:
            # Other HTTP errors
            log_error_with_traceback(f"Discord HTTP error {status_code}", exc_value)
            
            # Send Discord notification for other HTTP errors
            discord_logger = get_discord_logger()
            if discord_logger:
                try:
                    context = {
                        "Event": event,
                        "Status Code": str(status_code),
                        "Error Message": str(exc_value)
                    }
                    
                    await discord_logger.log_error(
                        f"🌐 **Discord HTTP Error {status_code}**\n\n"
                        f"An HTTP error occurred during the `{event}` event.",
                        exc_value,
                        context
                    )
                except Exception as log_error:
                    log_error_with_traceback("Failed to send HTTP error notification to Discord", log_error)

    except Exception as e:
        log_error_with_traceback("Error handling HTTP error", e)


async def _attempt_voice_reconnection(reason):
    """
    Attempt to reconnect to voice channel with error recovery.

    Args:
        reason: Reason for reconnection attempt
    """
    global audio_manager

    try:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            channel = guild.get_channel(TARGET_CHANNEL_ID)
            if channel:
                voice_client = await channel.connect(reconnect=False, timeout=30)

                if audio_manager:
                    audio_manager.set_voice_client(voice_client)
                    # Restart audio playback with resume position to continue where we left off
                    await audio_manager.start_playback(resume_position=True)

                log_perfect_tree_section(
                    "Voice Reconnection - Success",
                    [
                        ("reconnect_attempt", f"Reconnecting due to: {reason}"),
                        ("reconnect", f"✅ Reconnected to {channel.name}"),
                        (
                            "audio_restart",
                            "✅ Audio playback resumed from saved position",
                        ),
                    ],
                    "✅",
                )

    except Exception as reconnect_error:
        log_error_with_traceback(f"Reconnection failed after {reason}", reconnect_error)


@bot.event
async def on_disconnect():
    """
    Handle Discord disconnect events with graceful state management.

    This event is triggered when the bot loses connection to Discord.
    It performs cleanup operations and ensures proper state management
    during disconnection periods.

    Features:
    - Logs disconnect events with timestamps
    - Performs graceful cleanup of active connections
    - Maintains state integrity during connection loss
    - Prepares for automatic reconnection by Discord.py

    Note:
        Discord.py automatically handles reconnection, so this handler
        focuses on cleanup and logging rather than manual reconnection.
    """
    try:
        log_perfect_tree_section(
            "Discord Connection - Disconnected",
            [
                ("status", "⚠️ Bot disconnected from Discord"),
                ("timestamp", get_timestamp().strip("[]")),
                ("reconnection", "🔄 Discord.py will handle automatic reconnection"),
                ("state_management", "💾 Maintaining state during disconnect"),
            ],
            "📡",
        )

        # Send disconnect notification to Discord logger
        discord_logger = get_discord_logger()
        if discord_logger:
            try:
                await discord_logger.log_system_event(
                    "Bot Disconnected",
                    "🔌 **QuranBot has disconnected from Discord**\n\n"
                    "This may be due to network issues, Discord maintenance, or server problems. "
                    "The bot will attempt to reconnect automatically.",
                    {
                        "Disconnect Time": get_timestamp().strip("[]"),
                        "Auto Reconnect": "Enabled",
                        "State Management": "Active"
                    }
                )
            except:
                pass  # Don't let Discord logging errors interfere with disconnect handling

        # Clean up any active voice connections
        if bot.voice_clients:
            for voice_client in bot.voice_clients:
                try:
                    if voice_client.is_connected():
                        await voice_client.disconnect()
                except Exception as e:
                    log_error_with_traceback(
                        f"Error disconnecting voice client during disconnect event", e
                    )

        # Mark disconnect in state manager
        state_manager.mark_disconnect()
        
        # Stop integrated log sync
        try:
            from src.utils.log_sync_manager import stop_integrated_log_sync
            await stop_integrated_log_sync()
        except Exception as e:
            log_error_with_traceback("Error stopping integrated log sync", e)

        log_perfect_tree_section(
            "Discord Disconnect - Cleanup Complete",
            [
                ("voice_cleanup", "✅ Voice connections cleaned up"),
                ("state_marked", "✅ Disconnect marked in state manager"),
                ("log_sync", "✅ Log sync stopped"),
                ("awaiting_reconnect", "⏳ Waiting for automatic reconnection"),
            ],
            "🧹",
        )

    except Exception as e:
        log_error_with_traceback("Error handling disconnect event", e)
        
        # Send error to Discord logger
        discord_logger = get_discord_logger()
        if discord_logger:
            try:
                await discord_logger.log_error(
                    "Error handling disconnect event",
                    e,
                    {
                        "Event": "on_disconnect", 
                        "Impact": "Disconnect handling failed"
                    }
                )
            except:
                pass


@bot.event
async def on_resumed():
    """
    Handle Discord reconnection after temporary disconnection.

    Automatically restarts audio playback when the bot reconnects,
    ensuring seamless continuation from where it left off.
    """
    global rich_presence, audio_manager

    try:
        # Verify voice connection is still active
        voice_status = "No active voice connections"
        voice_clients = []

        if hasattr(bot, "voice_clients"):
            voice_clients = bot.voice_clients
            if voice_clients:
                voice_status = f"Voice connections: {len(voice_clients)}"

        log_perfect_tree_section(
            "Discord Reconnection",
            [
                ("event", "on_resumed"),
                ("status", "Bot reconnected to Discord"),
                ("voice_status", voice_status),
            ],
            "🔄",
        )

        # Send reconnection notification to Discord logger
        discord_logger = get_discord_logger()
        if discord_logger:
            try:
                await discord_logger.log_system_event(
                    "Bot Reconnected",
                    "🔄 **QuranBot has reconnected to Discord**\n\n"
                    "Connection has been restored successfully. Audio playback will resume automatically.",
                    {
                        "Reconnect Time": get_timestamp().strip("[]"),
                        "Voice Status": voice_status,
                        "Auto Restart": "Attempting audio restart"
                    }
                )
            except:
                pass  # Don't let Discord logging errors interfere with reconnection

        # Automatically restart audio playback using intelligent logic
        if voice_clients:
            await auto_restart_audio_playback(voice_clients[0])

    except Exception as e:
        log_error_with_traceback("Error handling resume event", e)


@bot.event
async def on_guild_unavailable(guild):
    """
    Handle guild becoming unavailable due to Discord outages.

    Logs when a guild becomes unavailable, typically due to Discord
    server issues or network problems.

    Args:
        guild: Guild that became unavailable
    """
    try:

        # Check if this is our target guild
        target_guild_status = "Different guild"
        if guild.id == GUILD_ID:
            target_guild_status = "⚠️ Target guild is unavailable"

        log_perfect_tree_section(
            "Guild Unavailable",
            [
                ("guild_id", guild.id),
                ("guild_name", guild.name),
                ("status", "Guild became unavailable"),
                ("target_guild", target_guild_status),
            ],
            "⚠️",
        )

    except Exception as e:
        log_error_with_traceback("Error handling guild unavailable event", e)


@bot.event
async def on_guild_available(guild):
    """
    Handle guild becoming available again after being unavailable.

    Logs when a guild becomes available again and performs any necessary
    reinitialization if it's our target guild.

    Args:
        guild: Guild that became available
    """
    try:

        # Check if this is our target guild
        target_guild_status = "Different guild"
        target_channel_status = "Not applicable"

        if guild.id == GUILD_ID:
            target_guild_status = "✅ Target guild is now available"

            # Verify voice channel is still accessible
            channel = guild.get_channel(TARGET_CHANNEL_ID)
            if channel:
                target_channel_status = (
                    f"✅ Target channel '{channel.name}' is accessible"
                )
            else:
                target_channel_status = "⚠️ Target channel is not accessible"

        log_perfect_tree_section(
            "Guild Available",
            [
                ("guild_id", guild.id),
                ("guild_name", guild.name),
                ("status", "Guild became available"),
                ("target_guild", target_guild_status),
                ("target_channel", target_channel_status),
            ],
            "✅",
        )

    except Exception as e:
        log_error_with_traceback("Error handling guild available event", e)


# =============================================================================
# Helper Functions for Auto-Restart Logic
# =============================================================================


def should_auto_restart_audio() -> bool:
    """
    Determine if audio playback should automatically restart after reconnection.

    Checks the saved state to see if audio was playing when the bot disconnected
    and if there's a valid resume position.

    Returns:
        bool: True if audio should auto-restart, False otherwise
    """
    try:
        if not audio_manager:
            return False

        # Get resume info from state manager
        resume_info = state_manager.get_resume_info()

        # Check if we have a valid resume position or if audio was previously playing
        saved_state = state_manager.load_playback_state()
        was_playing = saved_state.get("is_playing", False)
        has_position = resume_info.get("should_resume", False)

        # Auto-restart if audio was playing OR if we have a saved position
        return was_playing or has_position

    except Exception as e:
        log_error_with_traceback("Error checking auto-restart conditions", e)
        return False


async def auto_restart_audio_playback(voice_client=None) -> bool:
    """
    Automatically restart audio playback with intelligent resume logic.

    Args:
        voice_client: Optional voice client to use (will detect if None)

    Returns:
        bool: True if restart was successful, False otherwise
    """
    global audio_manager

    try:
        if not audio_manager:
            log_perfect_tree_section(
                "Auto-Restart Check",
                [
                    ("status", "❌ No audio manager available"),
                ],
                "❌",
            )
            return False

        # Check if we should auto-restart
        if not should_auto_restart_audio():
            log_perfect_tree_section(
                "Auto-Restart Check",
                [
                    ("status", "ℹ️ No auto-restart needed"),
                    ("reason", "Audio was not playing when disconnected"),
                ],
                "ℹ️",
            )
            return False

        # Get voice client if not provided
        if not voice_client and hasattr(bot, "voice_clients") and bot.voice_clients:
            voice_client = bot.voice_clients[0]

        if not voice_client or not voice_client.is_connected():
            log_perfect_tree_section(
                "Auto-Restart Failed",
                [
                    ("status", "❌ No voice client available"),
                ],
                "❌",
            )
            return False

        # Update audio manager with voice client
        if (
            not audio_manager.voice_client
            or not audio_manager.voice_client.is_connected()
        ):
            audio_manager.set_voice_client(voice_client)

        # Check if already playing
        if audio_manager.is_playing:
            log_perfect_tree_section(
                "Auto-Restart Check",
                [
                    ("status", "✅ Audio already playing"),
                    ("current_surah", audio_manager.current_surah),
                ],
                "✅",
            )
            return True

        # Get resume info for logging
        resume_info = state_manager.get_resume_info()

        log_perfect_tree_section(
            "Auto-Restart Audio Playback",
            [
                ("status", "🔄 Restarting audio after reconnection"),
                ("resume_surah", resume_info["surah"]),
                ("resume_position", f"{resume_info['position']:.1f}s"),
                ("resume_reciter", resume_info["reciter"]),
            ],
            "🎵",
        )

        # Log voice reconnection to Discord
        from src.utils.discord_logger import get_discord_logger
        discord_logger = get_discord_logger()
        if discord_logger:
            try:
                await discord_logger.log_bot_activity(
                    "voice_reconnect",
                    f"automatically restarted audio playback after voice reconnection",
                    {
                        "Resume Surah": f"{resume_info['surah']}. {resume_info.get('surah_name', 'Unknown')}",
                        "Resume Position": f"{resume_info['position']:.1f}s",
                        "Resume Reciter": resume_info["reciter"],
                        "Action": "Auto-restart after reconnection",
                        "Trigger": "Voice connection restored"
                    }
                )
            except:
                pass

        # Restart audio playback with resume position
        await audio_manager.start_playback(resume_position=True)

        log_perfect_tree_section(
            "Auto-Restart Complete",
            [
                ("status", "✅ Audio playback restarted successfully"),
                ("current_surah", audio_manager.current_surah),
                ("reciter", audio_manager.current_reciter),
                ("is_playing", audio_manager.is_playing),
            ],
            "✅",
        )

        return True

    except Exception as e:
        log_error_with_traceback("Error in auto-restart audio playback", e)
        log_perfect_tree_section(
            "Auto-Restart Failed",
            [
                ("status", "❌ Failed to restart audio automatically"),
                ("error", str(e)),
            ],
            "❌",
        )
        return False


# =============================================================================
# Bot Export for Main Entry Point
# =============================================================================
# This module exports the bot configuration and instance for use by main.py
