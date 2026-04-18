"""
Kingdom AI Redis Quantum Nexus Channel Definitions - SOTA 2026
================================================================
Centralized channel naming for consistent communication across all services.

All services should import channels from this file to ensure consistency.

Usage:
    from core.redis_channels import ImageChannels, VideoChannels, EventBusChannels
    
    # Redis publish
    redis_client.publish(ImageChannels.REQUEST, json.dumps(data))
    
    # EventBus publish  
    event_bus.publish(EventBusChannels.VISUAL_REQUEST, data)
"""

# =============================================================================
# REDIS CONFIGURATION
# =============================================================================

REDIS_HOST = 'localhost'
REDIS_PORT = 6380
REDIS_PASSWORD = 'QuantumNexus2025'


# =============================================================================
# IMAGE GENERATION CHANNELS (creation_engine_service.py)
# =============================================================================

class ImageChannels:
    """Redis channels for image generation via creation_engine_service."""
    
    # Request channels (services listen on these)
    REQUEST = 'creation.request'
    
    # Response channels (services publish to these)
    RESPONSE = 'creation.response'
    PROGRESS = 'creation.progress'
    
    # Alternative namespaced channels
    KINGDOM_REQUEST = 'kingdom:image:request'
    KINGDOM_RESPONSE = 'kingdom:image:response'


# =============================================================================
# VIDEO GENERATION CHANNELS (redis_video_service.py)
# =============================================================================

class VideoChannels:
    """Redis channels for video generation via redis_video_service."""
    
    # Request channels (services listen on these)
    REQUEST = 'video.generate'
    KINGDOM_REQUEST = 'kingdom:video:request'
    VISUAL_REQUEST = 'visual.generation.request'
    
    # Response channels (services publish to these)
    RESPONSE = 'video.generated'
    KINGDOM_RESPONSE = 'kingdom:video:response'
    VISUAL_COMPLETED = 'visual.generation.completed'
    
    # Status channel
    STATUS = 'video.status'
    KINGDOM_STATUS = 'kingdom:video:status'


# =============================================================================
# GENIE 3 WORLD MODEL CHANNELS (creation_engine_service.py)
# =============================================================================

class WorldChannels:
    """Redis channels for Genie 3 world generation."""
    
    # Request channels
    REQUEST = 'genie3.world.request'
    STEP = 'genie3.world.step'
    
    # Response channels
    RESPONSE = 'genie3.world.response'


# =============================================================================
# VOICE SERVICE CHANNELS (redis_voice_service.py)
# =============================================================================

class VoiceChannels:
    """Redis channels for voice generation via redis_voice_service."""
    
    # Request channels
    REQUEST = 'voice.speak'
    AI_VOICE = 'ai.voice.command'
    
    # Response channels
    RESPONSE = 'voice.complete'
    STATUS = 'voice.status'
    
    # Alternative namespaced channels
    KINGDOM_REQUEST = 'kingdom:voice:request'
    KINGDOM_RESPONSE = 'kingdom:voice:response'


# =============================================================================
# EVENTBUS CHANNELS (Internal GUI/Brain communication)
# =============================================================================

class EventBusChannels:
    """EventBus channels for internal communication within Kingdom AI."""
    
    # Visual/Creation requests
    VISUAL_REQUEST = 'visual.request'
    BRAIN_VISUAL_REQUEST = 'brain.visual.request'
    VISUAL_GENERATE_REQUEST = 'visual.generate.request'
    
    # Visual/Creation responses
    VISUAL_GENERATED = 'visual.generated'
    VISUAL_GENERATION_STARTED = 'visual.generation.started'
    VISUAL_GENERATION_PROGRESS = 'visual.generation.progress'
    VISUAL_GENERATION_ERROR = 'visual.generation.error'
    VISUAL_GENERATION_COMPLETED = 'visual.generation.completed'
    
    # AI/Brain channels
    AI_REQUEST = 'ai.request'
    AI_RESPONSE = 'ai.response'
    BRAIN_RESPONSE = 'brain.response'
    
    # Voice channels
    VOICE_SPEAK = 'voice.speak'
    VOICE_COMPLETE = 'voice.complete'


# =============================================================================
# UNIFIED CHANNEL LISTS (for subscribing to multiple channels)
# =============================================================================

def get_all_image_channels():
    """Get all channels that handle image generation requests."""
    return [
        ImageChannels.REQUEST,
        ImageChannels.KINGDOM_REQUEST
    ]


def get_all_video_channels():
    """Get all channels that handle video generation requests."""
    return [
        VideoChannels.REQUEST,
        VideoChannels.KINGDOM_REQUEST,
        VideoChannels.VISUAL_REQUEST
    ]


def get_all_world_channels():
    """Get all channels that handle Genie 3 world requests."""
    return [
        WorldChannels.REQUEST,
        WorldChannels.STEP
    ]


# =============================================================================
# CHANNEL DOCUMENTATION
# =============================================================================

CHANNEL_DOCS = """
Kingdom AI Redis Channel Documentation
======================================

IMAGE GENERATION (creation_engine_service.py):
  Request:  creation.request, kingdom:image:request
  Response: creation.response, creation.progress

VIDEO GENERATION (redis_video_service.py):
  Request:  video.generate, kingdom:video:request, visual.generation.request
  Response: video.generated, kingdom:video:response, visual.generation.completed
  Status:   video.status, kingdom:video:status

GENIE 3 WORLD (creation_engine_service.py):
  Request:  genie3.world.request, genie3.world.step
  Response: genie3.world.response

VOICE (redis_voice_service.py):
  Request:  voice.speak, ai.voice.command, kingdom:voice:request
  Response: voice.complete, kingdom:voice:response, voice.status

EVENTBUS (Internal):
  Visual:   visual.request, brain.visual.request, visual.generated
  Progress: visual.generation.started, visual.generation.progress
  AI:       ai.request, ai.response, brain.response
"""

if __name__ == "__main__":
    print(CHANNEL_DOCS)
