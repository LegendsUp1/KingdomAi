"""
Kingdom AI Wallet Creator Dialog
GUI for creating and importing cryptocurrency wallets.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTextEdit, QMessageBox, QRadioButton,
    QButtonGroup, QGroupBox, QCheckBox, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QTextCursor

from core.wallet_creator import WalletCreator

logger = logging.getLogger("KingdomAI.WalletCreatorDialog")


class WalletCreatorDialog(QDialog):
    """Dialog for creating and importing wallets."""
    
    wallet_created = pyqtSignal(dict)  # Emitted when wallet is created
    
    def __init__(self, parent=None, event_bus=None):
        """Initialize wallet creator dialog."""
        super().__init__(parent)
        self.event_bus = event_bus
        self.wallet_creator = WalletCreator(event_bus=event_bus)
        
        self.setWindowTitle("🔐 Kingdom AI Wallet Creator")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Title
        title = QLabel("🔐 Create or Import Cryptocurrency Wallet")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Mode selection
        mode_group = QGroupBox("Select Mode")
        mode_layout = QVBoxLayout()
        
        self.mode_group = QButtonGroup()
        self.create_radio = QRadioButton("Create New Wallet")
        self.import_radio = QRadioButton("Import Existing Wallet")
        self.create_radio.setChecked(True)
        
        self.mode_group.addButton(self.create_radio)
        self.mode_group.addButton(self.import_radio)
        
        mode_layout.addWidget(self.create_radio)
        mode_layout.addWidget(self.import_radio)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Connect mode change
        self.create_radio.toggled.connect(self.on_mode_changed)
        
        # Wallet details
        details_group = QGroupBox("Wallet Details")
        details_layout = QVBoxLayout()
        
        # Wallet name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Wallet Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., My Main Wallet")
        name_layout.addWidget(self.name_input)
        details_layout.addLayout(name_layout)
        
        # Blockchain selection
        blockchain_layout = QHBoxLayout()
        blockchain_layout.addWidget(QLabel("Blockchain:"))
        self.blockchain_combo = QComboBox()
        self.blockchain_combo.addItems(["ETH (Ethereum)", "BTC (Bitcoin)", "SOL (Solana)"])
        blockchain_layout.addWidget(self.blockchain_combo)
        details_layout.addLayout(blockchain_layout)
        
        # Word count (for creation only)
        self.word_count_layout = QHBoxLayout()
        self.word_count_layout.addWidget(QLabel("Seed Phrase Length:"))
        self.word_count_combo = QComboBox()
        self.word_count_combo.addItems(["12 words (Standard)", "24 words (Extra Secure)"])
        self.word_count_layout.addWidget(self.word_count_combo)
        details_layout.addLayout(self.word_count_layout)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Import seed phrase (for import only)
        self.import_group = QGroupBox("Import Seed Phrase")
        import_layout = QVBoxLayout()
        
        import_layout.addWidget(QLabel("Enter your existing seed phrase (12 or 24 words):"))
        self.seed_input = QTextEdit()
        self.seed_input.setPlaceholderText("word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12")
        self.seed_input.setMaximumHeight(100)
        import_layout.addWidget(self.seed_input)
        
        self.import_group.setLayout(import_layout)
        self.import_group.setVisible(False)
        layout.addWidget(self.import_group)
        
        # Warning message
        warning = QLabel("⚠️ IMPORTANT: Write down your seed phrase on paper and store it safely!")
        warning.setStyleSheet("color: #ff6b6b; font-weight: bold; padding: 10px; background: #2a2a2a; border-radius: 5px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.create_button = QPushButton("🔐 Create Wallet")
        self.create_button.setStyleSheet("""
            QPushButton {
                background: #00d4aa;
                color: black;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #00ffcc;
            }
        """)
        self.create_button.clicked.connect(self.on_create_wallet)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background: #444;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #555;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(self.create_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_mode_changed(self):
        """Handle mode change between create and import."""
        is_create = self.create_radio.isChecked()
        
        # Show/hide word count selection
        for i in range(self.word_count_layout.count()):
            widget = self.word_count_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(is_create)
        
        # Show/hide import group
        self.import_group.setVisible(not is_create)
        
        # Update button text
        if is_create:
            self.create_button.setText("🔐 Create Wallet")
        else:
            self.create_button.setText("📥 Import Wallet")
    
    def on_create_wallet(self):
        """Handle wallet creation or import."""
        # Validate inputs
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a wallet name")
            return
        
        # Get blockchain
        blockchain_text = self.blockchain_combo.currentText()
        blockchain = blockchain_text.split()[0]  # Extract "ETH", "BTC", "SOL"
        
        if self.create_radio.isChecked():
            # Create new wallet
            self.create_new_wallet(name, blockchain)
        else:
            # Import wallet
            self.import_existing_wallet(name, blockchain)
    
    def create_new_wallet(self, name: str, blockchain: str):
        """Create a new wallet."""
        try:
            # Get word count
            word_count = 12 if "12" in self.word_count_combo.currentText() else 24
            
            # Show progress
            self.create_button.setEnabled(False)
            self.create_button.setText("Creating...")
            
            # Create wallet (async)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.wallet_creator.create_wallet(name, blockchain, word_count)
            )
            loop.close()
            
            if result.get("success"):
                # Show seed phrase dialog
                self.show_seed_phrase_dialog(result)
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create wallet: {result.get('error', 'Unknown error')}"
                )
            
        except Exception as e:
            logger.error(f"Wallet creation error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create wallet: {str(e)}")
        finally:
            self.create_button.setEnabled(True)
            self.create_button.setText("🔐 Create Wallet")
    
    def import_existing_wallet(self, name: str, blockchain: str):
        """Import an existing wallet."""
        try:
            # Get seed phrase
            seed_phrase = self.seed_input.toPlainText().strip()
            if not seed_phrase:
                QMessageBox.warning(self, "Error", "Please enter your seed phrase")
                return
            
            # Validate word count
            words = seed_phrase.split()
            if len(words) not in [12, 24]:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Invalid seed phrase. Must be 12 or 24 words (you entered {len(words)})"
                )
                return
            
            # Show progress
            self.create_button.setEnabled(False)
            self.create_button.setText("Importing...")
            
            # Import wallet (async)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.wallet_creator.import_wallet(name, seed_phrase, blockchain)
            )
            loop.close()
            
            if result.get("success"):
                QMessageBox.information(
                    self,
                    "Success",
                    f"✅ Wallet imported successfully!\n\n"
                    f"Name: {result.get('name')}\n"
                    f"Blockchain: {result.get('blockchain')}\n"
                    f"Address: {result.get('address')}"
                )
                self.wallet_created.emit(result)
                self.accept()
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to import wallet: {result.get('error', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(f"Wallet import error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to import wallet: {str(e)}")
        finally:
            self.create_button.setEnabled(True)
            self.create_button.setText("📥 Import Wallet")
    
    def show_seed_phrase_dialog(self, wallet_info: Dict[str, Any]):
        """Show seed phrase in a secure dialog."""
        dialog = SeedPhraseDialog(wallet_info, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.wallet_created.emit(wallet_info)
            self.accept()


class SeedPhraseDialog(QDialog):
    """Dialog to display seed phrase with security warnings."""
    
    def __init__(self, wallet_info: Dict[str, Any], parent=None):
        """Initialize seed phrase dialog."""
        super().__init__(parent)
        self.wallet_info = wallet_info
        
        self.setWindowTitle("⚠️ YOUR SEED PHRASE - WRITE IT DOWN NOW!")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Critical warning
        warning = QLabel("🚨 CRITICAL: WRITE DOWN YOUR SEED PHRASE NOW! 🚨")
        warning.setStyleSheet("""
            background: #ff0000;
            color: white;
            font-size: 16px;
            font-weight: bold;
            padding: 15px;
            border-radius: 5px;
        """)
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning)
        
        # Instructions
        instructions = QLabel(
            "This is your ONLY chance to see your seed phrase!\n\n"
            "✅ Write it down on paper\n"
            "✅ Store it in a safe place\n"
            "✅ Make multiple copies\n"
            "❌ NEVER store it digitally\n"
            "❌ NEVER share it with anyone"
        )
        instructions.setStyleSheet("padding: 10px; background: #2a2a2a; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Wallet info
        info = QLabel(
            f"Wallet Name: {self.wallet_info.get('name')}\n"
            f"Blockchain: {self.wallet_info.get('blockchain')}\n"
            f"Address: {self.wallet_info.get('address')}"
        )
        info.setStyleSheet("padding: 10px; background: #1a1a1a; border-radius: 5px;")
        layout.addWidget(info)
        
        # Seed phrase display
        seed_label = QLabel("YOUR SEED PHRASE (Write it down NOW!):")
        seed_label.setStyleSheet("font-weight: bold; color: #00d4aa;")
        layout.addWidget(seed_label)
        
        seed_display = QTextEdit()
        seed_display.setPlainText(self.wallet_info.get('seed_phrase', ''))
        seed_display.setReadOnly(True)
        seed_display.setStyleSheet("""
            QTextEdit {
                background: #000;
                color: #00ff00;
                font-size: 16px;
                font-weight: bold;
                padding: 15px;
                border: 2px solid #00d4aa;
                border-radius: 5px;
                font-family: monospace;
            }
        """)
        seed_display.setMaximumHeight(100)
        layout.addWidget(seed_display)
        
        # Confirmation checkbox
        self.confirm_checkbox = QCheckBox("✅ I have written down my seed phrase on paper")
        self.confirm_checkbox.setStyleSheet("font-weight: bold; color: #00d4aa;")
        self.confirm_checkbox.stateChanged.connect(self.on_confirm_changed)
        layout.addWidget(self.confirm_checkbox)
        
        # Final warning
        final_warning = QLabel(
            "⚠️ If you lose your seed phrase, you CANNOT recover your wallet!\n"
            "⚠️ Your funds will be LOST FOREVER!\n"
            "⚠️ No one can help you recover it!"
        )
        final_warning.setStyleSheet("""
            color: #ff6b6b;
            font-weight: bold;
            padding: 10px;
            background: #2a0000;
            border-radius: 5px;
        """)
        final_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(final_warning)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.continue_button = QPushButton("✅ I Have Written It Down - Continue")
        self.continue_button.setEnabled(False)
        self.continue_button.setStyleSheet("""
            QPushButton {
                background: #00d4aa;
                color: black;
                font-weight: bold;
                padding: 15px 30px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #00ffcc;
            }
            QPushButton:disabled {
                background: #444;
                color: #888;
            }
        """)
        self.continue_button.clicked.connect(self.accept)
        
        button_layout.addStretch()
        button_layout.addWidget(self.continue_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_confirm_changed(self, state):
        """Enable continue button when confirmed."""
        self.continue_button.setEnabled(state == Qt.CheckState.Checked.value)


# Export
__all__ = ["WalletCreatorDialog", "SeedPhraseDialog"]
