#!/bin/bash
# Audio Configuration for Kingdom AI
# On native Linux: ensure PulseAudio is running normally
# On WSL: route audio through Windows PulseAudio server

if grep -qi microsoft /proc/version 2>/dev/null; then
    # WSL environment — route to Windows host
    WINDOWS_HOST=$(ip route | grep default | awk '{print $3}')

    export PULSE_SERVER="tcp:${WINDOWS_HOST}"
    export DISPLAY="${WINDOWS_HOST}:0.0"

    mkdir -p ~/.config/pulse
    cat > ~/.config/pulse/client.conf << PULSECONF
default-server = tcp:${WINDOWS_HOST}:4713
autospawn = no
daemon-binary = /bin/true
enable-shm = false
PULSECONF

    echo "✅ WSL audio configured to use Windows host at ${WINDOWS_HOST}"
    echo "   Make sure PulseAudio is running on Windows"
else
    # Native Linux — ensure PulseAudio is running with autospawn
    mkdir -p ~/.config/pulse

    # Remove any WSL-specific config that disables autospawn
    if [ -f ~/.config/pulse/client.conf ]; then
        if grep -q "autospawn = no" ~/.config/pulse/client.conf 2>/dev/null; then
            cat > ~/.config/pulse/client.conf << PULSECONF
autospawn = yes
PULSECONF
            echo "✅ Reset PulseAudio client config for native Linux"
        fi
    fi

    # Start PulseAudio if not running
    if ! pulseaudio --check 2>/dev/null; then
        pulseaudio --start --daemonize=yes 2>/dev/null || true
    fi

    echo "✅ Native Linux audio configured (PulseAudio)"
    echo "   Test with: paplay /usr/share/sounds/freedesktop/stereo/bell.oga"
fi
