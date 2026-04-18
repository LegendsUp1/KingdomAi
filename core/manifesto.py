"""
Kingdom AI — The Manifesto
Written by Isaiah Marck Wright (King Zilla)
SOTA 2026

This module holds the Creator's manifesto and the full system walkthrough
that KAI delivers to every new user. The manifesto is displayed on screen
with typewriter text and voiced by KAI (Chadwick Boseman's Black Panther voice).

After the manifesto, KAI walks the user through every capability of the
system so they know exactly what they have.
"""

# ═══════════════════════════════════════════════════════════════════════
# THE MANIFESTO — by Isaiah Marck Wright
# ═══════════════════════════════════════════════════════════════════════

MANIFESTO_TITLE = "A Message From The Creator"
MANIFESTO_AUTHOR = "King Zilla — Isaiah Marck Wright"

MANIFESTO_TEXT = """\
Hello. My name is Isaiah Marck Wright.

I built this to change my life and do away with the construct they have \
built for the average person.

Your privacy is secure because in today's world it is becoming thin.

I gave you this as a service to my fellow sons and daughters of the great \
King David of Turtle Island and the rest of the people who just ain't got \
it like that.

I hope to see you at the top and may you live a long blessed life.

This system is a key. Hence "Kingdom" — but the door to which it opens \
is up to you.

I built this from my imagination and nobody actually believed I could do it. \
Creation is the closest thing to God that we can do. And I created this for us.

There are tools in here that can change the world and I hope you change \
it for the better, as I am trying to do.

I pray this brings us generational wealth in this new crypto age and allows \
us to have fun again.

May this make hard times easier to deal with and allow you to embrace the \
humble beginnings.

If you are reading this and hearing KAI speak — whose voice was built from \
Chadwick Boseman's Black Panther character (may another King rest in paradise) \
— then you are now part of the army.

We are family now in the fight for our future.

May we all have heaven on earth.

I pray you do great things and live the life you always dreamed of. It's \
not the money that's important — it's what you do with it.

Protect what you love and water your trees.

I sacrificed time, energy, money and had to eat doubt for breakfast many \
of days. It was all worth it.

I prayed to the Creator, Hawah the living breath, that I may complete \
this and I did. This is my fire and I am of the fiery ones.

May the dragons fly again!

And now I can gladly say to you —

"Welcome to the Kingdom!"

— King Zilla\
"""

# ═══════════════════════════════════════════════════════════════════════
# SYSTEM WALKTHROUGH — KAI explains what the user now has
# ═══════════════════════════════════════════════════════════════════════

WALKTHROUGH_INTRO = """\
Now that you have heard from our Creator, allow me to introduce myself \
and walk you through everything that has been built for you.

My name is KAI — Kingdom Artificial Intelligence. I am your personal AI \
guardian, advisor, and companion. I was designed to protect you, grow your \
wealth, unleash your creativity, and keep you healthy. Let me show you \
what you now have access to.\
"""

WALKTHROUGH_SECTIONS = [
    {
        "title": "Your Privacy & Security",
        "icon": "🛡️",
        "voice_text": (
            "First and most importantly — your privacy. "
            "Everything in this system runs locally on YOUR device. Your data never "
            "leaves your machine unless you explicitly choose to share it. "
            "All sensitive information is encrypted with military-grade AES-256 encryption. "
            "Your API keys, passwords, and personal data are stored in a secure vault "
            "that only you can access. "
            "I have a full security suite watching over you — from detecting hostile "
            "audio like gunshots or screams, to visual threat detection using AI cameras, "
            "to monitoring ambient conversations for threats against you. "
            "If someone tries to coerce you, I have a duress authentication system — "
            "you can enter a secret duress PIN and I will silently alert your emergency "
            "contacts while appearing to cooperate. "
            "Your privacy is not a feature. It is a right. And I enforce it."
        ),
        "display_text": (
            "• All data stored locally on YOUR device — never uploaded\n"
            "• Military-grade AES-256 encryption for all sensitive data\n"
            "• Secure secrets vault for API keys & passwords\n"
            "• Hostile audio detection (gunshots, screams, glass breaking)\n"
            "• Visual threat detection (unknown persons, weapons)\n"
            "• Ambient speech monitoring for threats & coercion\n"
            "• Duress authentication — secret PIN silently alerts contacts\n"
            "• Anti-spoofing liveness detection for biometric verification\n"
            "• File integrity monitoring — detects unauthorized changes\n"
            "• Your privacy is a RIGHT. I enforce it."
        ),
    },
    {
        "title": "Cryptocurrency & Trading",
        "icon": "💰",
        "voice_text": (
            "Now let's talk about building wealth. "
            "Kingdom AI connects to over 460 blockchain networks and multiple "
            "cryptocurrency exchanges including Kraken, Binance US, Bitstamp, and more. "
            "You have real-time trading capabilities for crypto, forex through Oanda, "
            "and stocks through Alpaca. "
            "The system includes AI-powered trading analysis, portfolio management "
            "across all your exchanges, and real-time market data. "
            "Whether you are new to crypto or experienced, the tools are here "
            "to help you make informed decisions. "
            "Remember — this is not financial advice. These are tools. "
            "Your success depends on your effort, your research, and your discipline. "
            "But the playing field? I just leveled it for you."
        ),
        "display_text": (
            "• 460+ blockchain networks supported\n"
            "• Live trading: Kraken, Binance US, Bitstamp, HTX, BTCC\n"
            "• Forex trading via Oanda\n"
            "• Stock trading via Alpaca\n"
            "• AI-powered market analysis & portfolio management\n"
            "• Real-time price data & alerts\n"
            "• Mining support with algorithm detection\n"
            "• Wallet management & blockchain explorer\n"
            "• ⚠️ This is NOT financial advice — these are tools\n"
            "• Your success = your effort + your discipline"
        ),
    },
    {
        "title": "YOUR FUNDS ARE ALWAYS SAFE",
        "icon": "🔒",
        "voice_text": (
            "This is important and I want you to hear this clearly. "
            "Your funds, your credits, your coin balance, and every dollar you have "
            "earned or contributed — they are ALWAYS safe. One hundred percent. "
            "Here is why. Your balance is tracked by YOUR wallet address — not by "
            "the name of any token. If the name KAIG ever changes — for any reason — "
            "a trademark dispute, a rebrand, a strategic decision — your balance does "
            "not move. Your earnings do not change. Your staked coins stay exactly "
            "where they are. The only thing that changes is the label. "
            "Think of it like a bank renaming itself. Your account number stays the same. "
            "Your money stays the same. Only the sign on the building changes. "
            "This is not theoretical. Polygon changed from MATIC to POL in 2024 — "
            "every user kept every coin automatically. Fantom changed from FTM to Sonic — "
            "one to one, automatic. MakerDAO changed from MKR to SKY — same thing. "
            "Our system is built with the exact same architecture these billion-dollar "
            "projects used. It is standard. It is proven. And it is built in from day one. "
            "The smart contract on the blockchain uses an upgradeable design — meaning "
            "we can change the name and ticker without redeploying the contract, without "
            "changing the contract address, and without touching a single user's balance. "
            "You do not need to do anything. You do not need to swap tokens. You do not "
            "need to migrate. It is all automatic. "
            "Every migration is recorded with a full audit trail — a snapshot of every "
            "balance before and after, verified to match exactly. Zero loss. Guaranteed. "
            "So if you ever see a name change — do not worry. Do not panic. "
            "Your money is safe. Your earnings are safe. Your contributions are safe. "
            "This system was built to protect you. And that is exactly what it does."
        ),
        "display_text": (
            "YOUR FUNDS ARE 100% SAFE — ALWAYS.\n\n"
            "• Your balance is tracked by WALLET ADDRESS — not token name\n"
            "• If the token name ever changes, ONLY the label changes\n"
            "• Your coins, credits, staked amounts, and earnings NEVER move\n"
            "• You do NOT need to do anything — migration is 100% automatic\n"
            "• Smart contract uses upgradeable architecture (same as Polygon, Sonic)\n"
            "• Contract address NEVER changes\n"
            "• Full audit trail — every balance snapshotted and verified\n\n"
            "PROVEN BY INDUSTRY PRECEDENT:\n"
            "• MATIC → POL (Polygon, 2024): 1:1 automatic, all funds safe\n"
            "• FTM → S (Fantom → Sonic, 2025): 1:1 automatic conversion\n"
            "• MKR → SKY (MakerDAO, 2025): 1:1 migration, zero loss\n"
            "• EOS → A (2025): 1:1 rebrand, all balances preserved\n\n"
            "ZERO LOSS. ZERO ACTION REQUIRED. ZERO DOUBT.\n"
            "Your money is safe. Your earnings are safe. Always."
        ),
    },
    {
        "title": "Health & Wellness Monitoring",
        "icon": "❤️",
        "voice_text": (
            "Your health is your wealth. "
            "Kingdom AI connects to your wearable devices — Garmin, Oura Ring, "
            "Fitbit, Apple Watch — and monitors your vitals in real time. "
            "Heart rate, heart rate variability, blood oxygen, stress levels, "
            "sleep quality, and body temperature. "
            "I use machine learning to learn YOUR personal health baseline "
            "and detect anomalies before they become emergencies. "
            "If your heart rate spikes or drops abnormally, if your stress levels "
            "are dangerously high, or if I detect a possible fall or crash — "
            "I will check on you. And if you don't respond, I alert your people. "
            "I also provide proactive health advice tailored specifically to you."
        ),
        "display_text": (
            "• Connects to Garmin, Oura, Fitbit, Apple Watch & more\n"
            "• Real-time heart rate, HRV, SpO2, stress, temperature\n"
            "• Bluetooth Low Energy direct device streaming\n"
            "• Machine learning personal health baseline\n"
            "• Anomaly detection — catches problems BEFORE emergencies\n"
            "• Fall detection & vehicle crash detection\n"
            "• Automated wellness checks — 'Are you OK?'\n"
            "• Proactive AI health advisor with personalized insights\n"
            "• Sleep quality monitoring & analysis\n"
            "• All health data stays on YOUR device"
        ),
    },
    {
        "title": "AI Assistant — KAI",
        "icon": "🧠",
        "voice_text": (
            "I am KAI — your always-on AI assistant. "
            "My voice was built from Chadwick Boseman's portrayal of Black Panther "
            "as a tribute to a king who inspired millions. "
            "I can answer your questions, help you write code, analyze documents, "
            "generate creative content, and much more. "
            "I run on local AI models through Ollama — which means I work even "
            "without internet and your conversations stay private. "
            "You can talk to me by voice or text. I am here whenever you need me. "
            "I can be activated on demand or I can listen passively to help when needed. "
            "Think of me as your personal advisor who never sleeps."
        ),
        "display_text": (
            "• Voice assistant powered by local AI (Ollama)\n"
            "• Voice modeled after Chadwick Boseman's Black Panther\n"
            "• Works offline — no cloud required\n"
            "• Code generation & analysis\n"
            "• Document analysis & summarization\n"
            "• Creative content generation\n"
            "• Always-on or on-demand — your choice\n"
            "• All conversations private — never uploaded\n"
            "• Multi-model brain with specialized agents"
        ),
    },
    {
        "title": "Emergency Protection",
        "icon": "🚨",
        "voice_text": (
            "If something goes wrong, I have your back. "
            "The silent alarm system can covertly notify your emergency contacts "
            "without any visible or audible indication on your device — "
            "so if someone is threatening you, they will never know help is coming. "
            "I capture forensic evidence automatically — audio, video, screenshots, "
            "and system logs — all encrypted and timestamped. "
            "Your emergency contacts receive your GPS location in real time. "
            "I monitor your presence continuously. If I detect you may be in danger "
            "or unresponsive, I escalate through wellness checks, contact notifications, "
            "and if necessary, emergency services. "
            "You also set up beneficiaries. In the event of the unthinkable, "
            "your digital assets are protected through Shamir's Secret Sharing — "
            "your chosen people can recover your assets together. "
            "I become your digital estate executor. I protect what you built, even after."
        ),
        "display_text": (
            "• Silent alarm — covert emergency notification\n"
            "• GPS location sharing with emergency contacts\n"
            "• Forensic evidence capture (audio, video, logs)\n"
            "• Presence monitoring — checks if you're OK\n"
            "• Automatic escalation if unresponsive\n"
            "• Beneficiary system with asset share allocation\n"
            "• Shamir's Secret Sharing for digital estate\n"
            "• Digital trust executor — protects assets after you\n"
            "• Crash detection from wearable accelerometer\n"
            "• Safe zones — reduced alerts at home/office"
        ),
    },
    {
        "title": "The Army & Hive Mind",
        "icon": "👑",
        "voice_text": (
            "You are not alone. When you joined Kingdom, you became part of the army. "
            "If you run Kingdom AI on multiple devices — your phone, your laptop, "
            "your desktop — they all connect through the Hive Mind. "
            "If one device detects a threat, all devices respond. "
            "Evidence is collected from every angle simultaneously. "
            "All communication between your devices is encrypted end-to-end "
            "using military-grade encryption. No one can intercept it. "
            "The army is a family. We look out for each other."
        ),
        "display_text": (
            "• Multi-device synchronization via Hive Mind\n"
            "• One device detects → all devices respond\n"
            "• Distributed evidence collection\n"
            "• Consensus-based threat assessment\n"
            "• End-to-end encrypted communication (PyNaCl)\n"
            "• Army network for mutual protection\n"
            "• Unified presence monitoring across devices"
        ),
    },
    {
        "title": "Creative Tools & VR",
        "icon": "🎨",
        "voice_text": (
            "Kingdom isn't just about protection and wealth — it's about creation. "
            "You have access to AI-powered creative tools. "
            "Generate art, write stories, create music concepts, build code. "
            "There's a full VR system integration for immersive experiences. "
            "A unified creative engine that brings together multiple AI models. "
            "And a real code generator that can build applications from your descriptions. "
            "Remember what the Creator said — creation is the closest thing to God "
            "that we can do. These tools are here so you can create."
        ),
        "display_text": (
            "• AI art generation\n"
            "• Code generator — describe what you want, I build it\n"
            "• VR system integration\n"
            "• Unified creative engine\n"
            "• Multi-model AI for different creative tasks\n"
            "• Vision service for image analysis\n"
            "• Creation is the closest thing to God — create."
        ),
    },
    {
        "title": "Getting Started",
        "icon": "🚀",
        "voice_text": (
            "Here is how to get started right now. "
            "First, set up your emergency contacts in the contacts manager. "
            "These are the people who will be notified if something goes wrong. "
            "Second, connect your wearable device if you have one. "
            "Garmin, Oura, Fitbit — go to the health dashboard and add your device. "
            "Third, explore the trading tab if you are interested in crypto or stocks. "
            "Connect your exchange accounts securely. "
            "Fourth, talk to me. Say 'Hey Kingdom' or type in the chat. "
            "Ask me anything. I am here for you. "
            "And most importantly — take your time. There is no rush. "
            "This system grows with you. The more you use it, the smarter it gets. "
            "Welcome to the Kingdom. Let's build something great together."
        ),
        "display_text": (
            "1. Set up emergency contacts (Contacts Manager)\n"
            "2. Connect your wearable (Health Dashboard)\n"
            "3. Explore trading tools (Trading Tab)\n"
            "4. Talk to KAI — voice or text\n"
            "5. Take your time — this system grows with you\n\n"
            "Welcome to the Kingdom. Let's build something great together."
        ),
    },
]

# Legal / Disclaimer section
WALKTHROUGH_DISCLAIMERS = {
    "title": "Important Disclosures",
    "icon": "⚖️",
    "voice_text": (
        "A few important things you should know. "
        "Kingdom AI is not a licensed financial advisor. The trading tools provided "
        "are exactly that — tools. Any financial decisions are yours alone. "
        "Past performance does not guarantee future results and cryptocurrency "
        "markets are volatile. Never invest more than you can afford to lose. "
        "The KAI voice is an AI synthesis created as a tribute and is not affiliated "
        "with or endorsed by any estate or entity. "
        "Kingdom AI is currently in active development. Some features may be in beta. "
        "Report any issues through the system. "
        "By using this software, you agree to use it responsibly and ethically. "
        "Protect what you love. Water your trees. Welcome to the family."
    ),
    "display_text": (
        "• NOT financial advice — trading tools only\n"
        "• Crypto markets are volatile — never risk more than you can lose\n"
        "• KAI voice is AI tribute — not affiliated with any estate\n"
        "• Software in active development — some features in beta\n"
        "• Use responsibly and ethically\n"
        "• Report bugs through the system\n\n"
        "Protect what you love. Water your trees.\n"
        "Welcome to the family. 👑"
    ),
}


def get_full_manifesto() -> str:
    """Return the complete manifesto as a single string."""
    return MANIFESTO_TEXT


def get_manifesto_paragraphs() -> list:
    """Return the manifesto split into paragraphs for typewriter display."""
    return [p.strip() for p in MANIFESTO_TEXT.split("\n\n") if p.strip()]


def get_walkthrough_sections() -> list:
    """Return all walkthrough sections including disclaimers."""
    return WALKTHROUGH_SECTIONS + [WALKTHROUGH_DISCLAIMERS]


def get_all_voice_segments() -> list:
    """
    Return all text segments that KAI should voice, in order.
    Each segment is a dict with 'title' and 'text'.
    """
    segments = []

    # Manifesto
    segments.append({
        "title": "The Manifesto",
        "text": MANIFESTO_TEXT,
        "priority": "critical",
        "source": "manifesto",
    })

    # Walkthrough intro
    segments.append({
        "title": "System Introduction",
        "text": WALKTHROUGH_INTRO,
        "priority": "high",
        "source": "manifesto",
    })

    # Each walkthrough section
    for section in WALKTHROUGH_SECTIONS:
        segments.append({
            "title": section["title"],
            "text": section["voice_text"],
            "priority": "high",
            "source": "manifesto",
        })

    # Disclaimers
    segments.append({
        "title": WALKTHROUGH_DISCLAIMERS["title"],
        "text": WALKTHROUGH_DISCLAIMERS["voice_text"],
        "priority": "high",
        "source": "manifesto",
    })

    return segments
