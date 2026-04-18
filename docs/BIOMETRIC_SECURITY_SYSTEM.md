# Kingdom AI Biometric Security System - SOTA 2026

## Overview

Kingdom AI now features a comprehensive biometric security system that uses **face recognition** and **voice recognition** to ensure only authorized users can control the system. The system is designed for the creator **Isaiah Wright** and authorized family members.

---

## 🔐 Security Features

### Face Recognition
- **128-dimensional face encodings** using dlib/FaceNet
- **Webcam-based enrollment** with multiple samples for accuracy
- **Continuous authentication** via webcam monitoring
- **Adaptive learning** to handle day-to-day appearance changes (lighting, glasses, hair)

### Voice Recognition  
- **MFCC feature extraction** for voice biometrics
- **GMM (Gaussian Mixture Model)** speaker verification
- **Voice print enrollment** from microphone
- **Adaptive thresholds** for natural voice variations

### Security Levels
| Level | Access | Description |
|-------|--------|-------------|
| `OWNER` | Full | Isaiah Wright - Creator |
| `ADMIN` | Full | Trusted family members |
| `USER` | Limited | Regular users |
| `GUEST` | View Only | Observers |
| `LOCKED` | None | No access |

---

## 🚀 Auto-Startup Behavior

On Kingdom AI bootup, the biometric security system:

1. **Auto-initializes** the security manager
2. **Starts webcam monitoring** for face detection
3. **Listens for voice** to identify the user
4. **Does NOT lock automatically** - system stays open
5. **Recognizes you** and shows "Welcome, [Name]!" in status bar
6. **Only locks when you say "lock"** - explicit user control

---

## 👑 Creator Setup (Isaiah Wright)

The creator is automatically registered on first run. To enroll biometrics:

### Enroll Your Face
```python
from core.biometric_security_manager import get_biometric_security_manager

security = get_biometric_security_manager()
security.enroll_face("creator_isaiah_wright", capture_from_webcam=True, num_samples=10)
```

Or say: **"Enroll my face"** or **"Learn my face"**

### Enroll Your Voice
```python
security.enroll_voice("creator_isaiah_wright", capture_from_mic=True, duration=10.0)
```

Or say: **"Enroll my voice"** or **"Learn my voice"**

---

## 👨‍👩‍👧‍👦 Adding Family Members

### Add Your Father
```python
from core.biometric_security_manager import SecurityLevel

security.add_family_member("Dad's Full Name", "father", SecurityLevel.ADMIN)
security.enroll_face("family_dads_full_name_father", capture_from_webcam=True)
security.enroll_voice("family_dads_full_name_father", capture_from_mic=True)
```

### Add Your Daughters
```python
# Daughter 1
security.add_family_member("Daughter 1 Name", "daughter", SecurityLevel.ADMIN)
security.enroll_face("family_daughter_1_name_daughter", capture_from_webcam=True)

# Daughter 2
security.add_family_member("Daughter 2 Name", "daughter", SecurityLevel.ADMIN)
security.enroll_face("family_daughter_2_name_daughter", capture_from_webcam=True)

# Daughter 3
security.add_family_member("Daughter 3 Name", "daughter", SecurityLevel.ADMIN)
security.enroll_face("family_daughter_3_name_daughter", capture_from_webcam=True)
```

---

## 🎤 Voice Commands

### Security Commands
| Command | Action |
|---------|--------|
| "Enroll my face" | Start face enrollment via webcam |
| "Learn my face" | Same as above |
| "Enroll my voice" | Start voice enrollment via microphone |
| "Learn my voice" | Same as above |
| "Verify me" | Verify your identity |
| "Who am I" | Check current authenticated user |
| "Security status" | Show authentication status |
| "Lock system" | Lock Kingdom AI |
| "List users" | Show authorized users |
| "Who has access" | Same as above |

### Navigation Commands
| Command | Action |
|---------|--------|
| "Go to trading" | Switch to Trading tab |
| "Go to mining" | Switch to Mining tab |
| "Go to wallet" | Switch to Wallet tab |
| "Go to dashboard" | Switch to Dashboard tab |
| "Go to thoth" | Switch to Thoth AI tab |
| "Go to settings" | Switch to Settings tab |

### UI Control Commands
| Command | Action |
|---------|--------|
| "Scroll up" | Scroll current view up |
| "Scroll down" | Scroll current view down |
| "Fullscreen" | Toggle fullscreen mode |
| "Minimize" | Minimize window |
| "Refresh" | Refresh current view |

### Trading Commands
| Command | Action |
|---------|--------|
| "Buy" | Place buy order |
| "Sell" | Place sell order |
| "Show portfolio" | Display portfolio |
| "Whale tracking" | Enable whale alerts |

### Mining Commands
| Command | Action |
|---------|--------|
| "Start mining" | Begin mining |
| "Stop mining" | Stop mining |
| "Mine bitcoin" | Mine BTC |
| "Show hashrate" | Display hashrate |

### Visual Canvas Commands
| Command | Action |
|---------|--------|
| "Open visual" | Open Visual Creation Canvas |
| "Plot function" | Plot mathematical function |
| "Draw fractal" | Generate fractal |

---

## 🧠 Adaptive Recognition

The system uses **adaptive learning** to handle natural human variations:

### Face Recognition Adaptation
- **Multiple enrollment samples** (5-10 recommended)
- **Different angles and lighting** during enrollment
- **With/without glasses** if applicable
- **Automatic threshold adjustment** based on confidence history

### Voice Recognition Adaptation
- **Extended enrollment duration** (10+ seconds recommended)
- **Natural speech patterns** during enrollment
- **GMM model updates** over time
- **Noise-adaptive thresholds**

### Preventing Confusion
The system maintains stability by:
1. **Core biometric templates** are preserved (never overwritten)
2. **Confidence scoring** rejects low-quality matches
3. **Lockout protection** after 3 failed attempts
4. **Re-enrollment requires owner confirmation**

---

## 📁 Data Storage

All biometric data is stored securely:

```
data/biometric_security/
├── user_registry.json      # Authorized users list
├── face_encodings.pkl      # Face recognition templates
├── voice_prints.pkl        # Voice recognition models
└── auth_history.log        # Authentication history
```

---

## 🔧 Configuration

### Security Settings
```python
security.face_match_threshold = 0.6      # Lower = stricter (0.4-0.7)
security.voice_match_threshold = 0.7     # Lower = stricter (0.5-0.8)
security.max_auth_attempts = 3           # Attempts before lockout
security.lockout_duration = 300          # Lockout time in seconds
security.continuous_auth = True          # Enable continuous verification
security._auth_cache_duration = 60       # Re-verify every N seconds
```

### Disable Security (Development Only)
```python
security.authentication_required = False  # DANGEROUS - disable auth
security._require_biometric_auth = False  # In voice command manager
```

---

## 📡 Event Bus Topics

The system publishes these events:

| Topic | Description |
|-------|-------------|
| `security.authenticated` | User authenticated successfully |
| `security.face.enrolled` | Face enrollment complete |
| `security.voice.enrolled` | Voice enrollment complete |
| `security.face.verified` | Face verified in continuous auth |
| `security.voice.verified` | Voice verified |
| `security.lockout` | System locked due to failed attempts |
| `command.denied` | Command blocked - not authenticated |

---

## 🛠️ Troubleshooting

### "Face not recognized"
1. Ensure good lighting
2. Face the camera directly
3. Re-enroll with more samples: `security.enroll_face(user_id, num_samples=10)`

### "Voice not recognized"
1. Reduce background noise
2. Speak clearly for 10+ seconds during enrollment
3. Re-enroll: `security.enroll_voice(user_id, duration=15.0)`

### "System locked"
Wait 5 minutes or restart the application. Owner can reset:
```python
security._lockout_until = None
security._failed_attempts = 0
```

### Dependencies Missing
```bash
pip install face_recognition opencv-python librosa scikit-learn deepface dlib
```

---

## 🔒 Security Best Practices

1. **Enroll in good lighting** for face recognition
2. **Enroll in quiet environment** for voice recognition
3. **Use multiple samples** (10+ for face, 15+ seconds for voice)
4. **Re-enroll periodically** if recognition degrades
5. **Keep enrollment data backed up** securely
6. **Never share biometric data files**

---

## 📞 Quick Reference

### Check Who's Authenticated
```python
user = security.get_current_user()
if user:
    print(f"Logged in as: {user.name} ({user.security_level.value})")
```

### Verify Someone
```python
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
result = security.verify_face(frame)
print(f"Match: {result.success}, User: {result.user.name if result.user else 'Unknown'}")
cap.release()
```

### List All Users
```python
for user in security.list_authorized_users():
    print(f"{user['name']} - {user['relationship']} - {user['security_level']}")
```

---

*Kingdom AI Biometric Security System v1.0 - SOTA 2026*
*Creator: Isaiah Wright*
